import requests
import time
import pygame # pip install pygame
import json
import io
import os
import signal
import sys
import board
import busio
import logging
import configparser
import threading
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from digitalio import DigitalInOut
from adafruit_pn532.i2c import PN532_I2C  # pip install adafruit-blinka adafruit-circuitpython-pn532

# Set SDL to use the dummy audio driver so pygame doesn't require an actual sound device
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['TESTMODE'] = 'True'

# Load configuration and schemas
config = configparser.ConfigParser()
config.read('config.ini')

# Environment and Configuration
SERVER_NAME = config['DEFAULT'].get('ServerName', "https://lang.thekao.cloud/generate-speech")
API_TOKEN = config['DEFAULT'].get('ApiToken', "test123")
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": API_TOKEN
}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Flask application setup
app = Flask(__name__)
CORS(app)

# Initialize audio
pygame.init()
pygame.mixer.init()

# Define threading event
read_pause_event = threading.Event()

class MockPN532:
    def __init__(self):
        self.uid = "MockUID1234"

    def read_passive_target(self, timeout=0.5):
        # Simulate reading an NFC tag
        return self.uid

    # Add other methods as needed for your script

# Initialize the PN532 NFC reader
def init_nfc_reader():
    if os.environ['TESTMODE']:
      logger.info("Initializing NFC Reader (Mock Implementation)")
      return MockPN532()

    i2c = busio.I2C(board.SCL, board.SDA)
    reset_pin = DigitalInOut(board.D6)  # Adjust as per your connection
    pn532 = PN532_I2C(i2c, reset=reset_pin)
    pn532.SAM_configuration()
    return pn532

pn532 = init_nfc_reader()

# Flask Endpoints
@app.route('/healthz', methods=['GET'])
def health_check():
    try:
        # Perform a basic health check. For example, you can:
        # - Make a simple database query
        # - Check if critical services (like external APIs) are reachable
        # - Return a simple "OK" if basic app functions are working
        return jsonify({"status": "healthy"}), 200
    except Exception as e:
        current_app.logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "details": str(e)}), 500

react_build_directory = os.path.abspath("./build")

@app.route('/static/<path:path>')
def serve_admin_static(path):
    return send_from_directory(os.path.join(react_build_directory, 'static'), path)

@app.route('/<filename>')
def serve_admin_root_files(filename):
    if filename in ['manifest.json', 'favicon.ico', 'logo192.png', 'logo512.png']:
        return send_from_directory(react_build_directory, filename)
    # Forward to the catch-all route for other paths
    return serve_admin(filename)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_admin(path):
    return send_from_directory(react_build_directory, 'index.html')

@app.route('/perform_http_request', methods=['POST'])
def perform_http_request_endpoint():
    data = request.json
    result = perform_http_request(data)
    return jsonify({"content": result}), 200

@app.route('/play_audio', methods=['POST'])
def play_audio_endpoint():
    audio_data = request.data
    play_audio(audio_data)
    return jsonify({"message": "Audio playback initiated"}), 200

@app.route('/handle_write', methods=['POST'])
def handle_write_endpoint():
    json_str = request.json.get('json_str')
    handle_write_request(json_str)
    return jsonify({"message": "Write to NFC tag initiated"}), 200

@app.route('/get_config', methods=['GET'])
def get_config():
    current_config = {
        'ServerName': config['DEFAULT'].get('ServerName', ''),
        'ApiToken': config['DEFAULT'].get('ApiToken', '')
    }
    return jsonify(current_config), 200

@app.route('/update_config', methods=['POST'])
def update_config():
    new_config = request.json
    update_result = update_configuration(new_config)
    return jsonify(update_result), 200

def update_configuration(new_config):
    config_path = '/config/config.ini'
    try:
        # Read the current configuration
        config.read(config_path)

        # Update with new values
        if 'ServerName' in new_config:
            config['DEFAULT']['ServerName'] = new_config['ServerName']
        if 'ApiToken' in new_config:
            config['DEFAULT']['ApiToken'] = new_config['ApiToken']

        # Write changes back to the config file
        with open(config_path, 'w') as configfile:
            config.write(configfile)

        # Optionally, reload configuration in the application if needed
        # (e.g., update global variables SERVER_NAME and API_TOKEN)

        return {"message": "Configuration updated successfully"}
    except Exception as e:
        logger.error(f"Failed to update configuration: {e}")
        return {"error": str(e)}


def handle_write_request(json_str):
    read_pause_event.set()  # Pause the read loop
    time.sleep(1)  # Allow time for read loop to pause
    write_nfc(json_str, pn532)  # Perform the write operation
    read_pause_event.clear()  # Resume the read loop

def is_valid_json(json_str):
    try:
        json.loads(json_str)
        return True
    except json.JSONDecodeError:
        return False

def perform_http_request(data):
    try:
        if 'memory_data' in data:
            content = json.loads(data['memory_data'])
            logger.info(f"Content parsed from memory_data: {content}")
        else:
            content = data
            logger.info(f"Using provided data as content: {content}")

        logger.info(f"Sending data to server: {content}")
        response = requests.post(SERVER_NAME, headers=HEADERS, json=content, timeout=10)
        logger.info(f"Response status code: {response.status_code}")
        response.raise_for_status()
        logger.info("Request successful.")
        return response.content
    except requests.RequestException as e:
        logger.error(f"HTTP request error: {e}")
        return None


def play_audio(audio_data):
    try:
        logger.info("Loading audio data into stream.")
        audio_stream = io.BytesIO(audio_data)
        pygame.mixer.music.load(audio_stream)
        logger.info("Audio data loaded, starting playback.")
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(1)
        logger.info("Audio playback finished.")
    except Exception as e:
        logger.error(f"Error playing audio: {e}")


def is_valid_schema(data, schema_section):
    if not config.has_section(schema_section):
        logger.error(f"Schema section '{schema_section}' not found in configuration.")
        return False

    if not isinstance(data, dict):
        logger.error("Data is not a dictionary.")
        return False

    schema = config[schema_section]
    for key, value_type in schema.items():
        if key not in data:
            logger.error(f"Key '{key}' not found in data.")
            return False

        if not hasattr(__builtins__, value_type):
            logger.error(f"Invalid type '{value_type}' in schema.")
            return False

        expected_type = getattr(__builtins__, value_type)
        if not isinstance(data[key], expected_type):
            logger.error(f"Data type for '{key}' does not match. Expected {value_type}, got {type(data[key]).__name__}.")
            return False

    logger.info(f"Data validated successfully against schema '{schema_section}'.")
    return True

def validate_json_data(hex_data):
    try:
        json_str = bytes.fromhex(hex_data).decode('utf-8')
        data = json.loads(json_str)

        if is_valid_schema(data, 'Schema_Localization') or is_valid_schema(data, 'Schema_Translation'):
            return data
    except (ValueError, json.JSONDecodeError, TypeError):
        logger.error("Invalid JSON data")

    return {"text": "No valid json found", "language": "en", "translations": []}

def parse_tag_data(tag_data):
    try:
        if isinstance(tag_data, bytearray):
            data_hex = ''.join(['{:02x}'.format(x) for x in tag_data])
        elif isinstance(tag_data, str):
            data_hex = tag_data  # If it's already a string, use it as is
        else:
            logger.error("Unsupported data type for tag data")
            return None

        logger.info(f"Tag Memory Data: {data_hex}")
        return {"memory_data": data_hex}
    except Exception as e:
        logger.error(f"Error processing tag data: {e}")
        return None


def is_valid_json(json_str):
    try:
        json.loads(json_str)
        return True
    except json.JSONDecodeError:
        return False

def write_nfc_combined(pn532, json_str, start_page=4):
    # Check if the string is valid JSON
    try:
        json.loads(json_str)
    except json.JSONDecodeError:
        logger.error("Invalid JSON string")
        return

    # Convert string to bytes
    byte_data = json_str.encode()

    # Define the page size (typically 4 bytes for NFC tags)
    page_size = 4

    # Calculate the number of pages needed
    num_pages = len(byte_data) // page_size + (len(byte_data) % page_size > 0)

    # Write data to NFC tag
    for i in range(num_pages):
        # Calculate page index
        page = start_page + i

        # Get the byte chunk to write
        chunk = byte_data[i*page_size:(i+1)*page_size]

        # Pad the chunk with zeros if it's less than the page size
        while len(chunk) < page_size:
            chunk += b'\x00'

        # Write the chunk to the tag
        if not isinstance(page, int) or not (0 <= page <= 134):
            logger.error("Invalid page number for NFC tag write operation.")
            return
        if not isinstance(chunk, (list, tuple)) or len(chunk) != 4 or not all(isinstance(x, int) and 0 <= x < 256 for x in chunk):
            logger.error("Data must be a list or tuple of 4 bytes.")
            return

        try:
            pn532.ntag2xx_write_block(page, list(chunk))
            logger.info(f"Data written to NFC tag at page {page}")
        except Exception as e:
            logger.error(f"Error writing to NFC tag: {e}")
            return

    logger.info("JSON string written to NFC tag")


def read_tag_memory(pn532, start_page=4):
    try:
        logger.info("Reading length data from NFC tag.")
        length_data = pn532.ntag2xx_read_block(start_page)
        if length_data is None:
            logger.error("Failed to read length data from NFC tag")
            return None

        length = int.from_bytes(length_data[:2], 'big')
        logger.info(f"Data length: {length}")

        page_size = 4
        total_bytes_to_read = length + 2
        total_pages_to_read = (total_bytes_to_read + page_size - 1) // page_size
        tag_data = bytearray()
        logger.info("Beginning to read tag memory.")
        for i in range(total_pages_to_read):
            data = pn532.ntag2xx_read_block(start_page + i)
            if data is None:
                logger.error(f"Failed to read page {start_page + i}")
                break
            tag_data.extend(data)
        logger.info("Tag memory reading completed.")
        return tag_data[2:2 + length]
    except Exception as e:
        logger.error(f"Error while reading NFC tag memory: {e}")
        return None


def check_for_nfc_tag(pn532):
    uid = pn532.read_passive_target(timeout=0.5)
    if uid is not None:
        logger.debug("NFC tag detected")
        return uid
    return None


# Main function for NFC tag reading loop
def main():
    last_uid = None
    logger.info("Script started, waiting for NFC tag.")

    def read_loop():
        nonlocal last_uid
        while True:
            try:
                nfc_data = check_for_nfc_tag(pn532)
                if nfc_data and nfc_data != last_uid:
                    last_uid = nfc_data
                    logger.info("New NFC tag detected, processing.")
                    full_memory = read_tag_memory(pn532, start_page=4)
                    logger.info("Tag memory read, processing data.")

                    if full_memory:
                        parsed_data = parse_tag_data(full_memory.decode('utf-8').rstrip('\x00'))
                        if parsed_data:
                            logger.info(f"Parsed data: {parsed_data}")
                            audio_data = perform_http_request(parsed_data)
                            if audio_data:
                                logger.info("Audio data received, starting playback.")
                                play_audio(audio_data)
                elif not nfc_data:
                    last_uid = None
            except Exception as e:
                logger.error(f"An error occurred: {e}")
            time.sleep(1)

    read_thread = threading.Thread(target=read_loop)
    read_thread.start()

    try:
        while True:
            # Main thread can handle other tasks
            time.sleep(1)
    except KeyboardInterrupt:
        read_thread.join()


def signal_handler(sig, frame):
    logger.info("Gracefully shutting down")
    read_pause_event.set()  # Ensure the read thread exits
    read_thread.join()  # Wait for the read thread to finish
    pygame.quit()
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def run_flask_app():
    app.run(host='0.0.0.0', port=5000)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.start()

    main()


