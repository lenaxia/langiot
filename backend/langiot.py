from pydub.exceptions import CouldNotDecodeError
import requests
import time
from pydub import AudioSegment
from pydub.playback import play
import numpy as np
import json
import re
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
import subprocess

# Set SDL to use the dummy audio driver so pygame doesn't require an actual sound device
#os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['TESTMODE'] = 'False'

# Set default values for environment variables
DEFAULT_CONFIG_PATH = '/config/config.ini'
DEFAULT_WEB_APP_PATH = '/app/web'

WIFI_CONFIG_PATH = '/etc/wpa_supplicant/wpa_supplicant.conf'


# Use environment variables if they are set, otherwise use the default values
CONFIG_FILE_PATH = os.getenv('CONFIG_FILE_PATH', DEFAULT_CONFIG_PATH)
WEB_APP_PATH = os.getenv('WEB_APP_PATH', DEFAULT_WEB_APP_PATH)

# Declare read_thread as a global variable
read_thread = None
config = configparser.ConfigParser()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Flask application setup
app = Flask(__name__, static_folder=os.path.join(WEB_APP_PATH, 'static'))
CORS(app)

logger.info(f"Config File: {CONFIG_FILE_PATH}")
logger.info(f"Web App Path: {WEB_APP_PATH}")

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
    if os.environ['TESTMODE'] == 'True':
      logger.info("Initializing NFC Reader (Mock Implementation)")
      return MockPN532()

    logger.info("Initializing NFC Reader")
    i2c = busio.I2C(board.SCL, board.SDA)
    reset_pin = DigitalInOut(board.D6)  # Adjust as per your connection
    pn532 = PN532_I2C(i2c, reset=reset_pin)
    pn532.SAM_configuration()
    return pn532

pn532 = init_nfc_reader()

@app.before_request
def log_request_info():
    logger.info(f"Request URL: {request.url}")


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
        app.logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "details": str(e)}), 500

# Route for static files
react_build_directory = os.path.abspath(WEB_APP_PATH)

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
    return send_file(
        io.BytesIO(result),
        mimetype="audio/mpeg",
        as_attachment=True,
        attachment_filename="audio.mp3"
    )

@app.route('/play_audio', methods=['POST'])
def play_audio_endpoint():
    audio_file = request.files.get('audioData')
    if audio_file:
        play_audio(audio_file.read())
        return jsonify({"message": "Audio playback initiated"}), 200
    else:
        return jsonify({"error": "No audio data received"}), 400


@app.route('/handle_write', methods=['POST'])
def handle_write_endpoint():
    json_str = request.json.get('json_str')
    handle_write_request(json_str)
    return jsonify({"message": "Write to NFC tag initiated"}), 200

@app.route('/get_config', methods=['GET'])
def get_config():
    load_configuration()
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

@app.route('/wifi-networks', methods=['GET'])
def list_networks():
    try:
        networks = get_networks()
        return jsonify(networks)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/wifi-networks', methods=['POST'])
def add_network():
    try:
        ssid = request.json.get('ssid')
        psk = request.json.get('psk')
        key_mgmt = request.json.get('key_mgmt', 'WPA-PSK')

        if not ssid or not psk:
            logging.warning("Attempt to add a network without providing both SSID and PSK.")
            return jsonify({"error": "SSID and PSK are required"}), 400

        result = subprocess.run(['sudo', './networkadd.sh', ssid, psk, key_mgmt], capture_output=True, text=True)

        if result.returncode != 0:
            logging.error(f"Script error when adding network {ssid}: {result.stderr}")
            return jsonify({"error": "Failed to add network, please check system logs"}), 500

        logging.info(f"Successfully added network: {ssid}")
        return jsonify({"message": "Network added"}), 201
    except Exception as e:
        logging.exception(f"Unexpected error adding Wi-Fi network: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/wifi-networks', methods=['DELETE'])
def delete_network():
    try:
        ssid_to_delete = request.json.get('ssid')
        if not ssid_to_delete:
            logging.warning("Attempt to delete a network without specifying SSID.")
            return jsonify({"error": "SSID is required for deletion"}), 400

        result = subprocess.run(['sudo', './networkdelete.sh', ssid_to_delete], capture_output=True, text=True)

        if result.returncode != 0:
            logging.error(f"Script error when deleting network {ssid_to_delete}: {result.stderr}")
            return jsonify({"error": "Failed to delete network, please check system logs"}), 500

        logging.info(f"Successfully deleted network: {ssid_to_delete}")
        return jsonify({"message": "Network deleted"}), 200
    except Exception as e:
        logging.exception(f"Unexpected error deleting Wi-Fi network: {e}")
        return jsonify({"error": "Internal server error"}), 500


def get_active_network():
    try:
        # Using 'iwgetid' to get the current network SSID
        ssid = subprocess.check_output(['iwgetid', '-r']).strip()
        return ssid.decode('utf-8') if ssid else None
    except Exception as e:
        logging.error(f"Error getting active network: {e}")
        return None

def get_networks():
    try:
        networks = parse_wpa_supplicant_conf(WIFI_CONFIG_PATH)
        active_ssid = get_active_network()
        return [{"ssid": network.get('ssid', ''),
                 "psk": network.get('psk', ''),
                 "key_mgmt": network.get('key_mgmt', 'NONE'),  # Assume 'NONE' if not present
                 "isConnected": (network.get('ssid', '') == active_ssid)}
                for network in networks]
    except Exception as e:
        logging.error(f"Error reading Wi-Fi configurations: {e}")
        raise

def parse_wpa_supplicant_conf(file_path):
    networks = []
    with open(file_path, 'r') as file:
        content = file.read()
    
    # Simple state machine to parse networks
    in_network_block = False
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('network='):
            in_network_block = True
            current_network = {}
        elif line == '}' and in_network_block:
            networks.append(current_network)
            in_network_block = False
        elif in_network_block:
            key, _, value = line.partition('=')
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]  # Strip quotes
            current_network[key] = value
    
    return networks


def load_configuration():
    global SERVER_NAME, API_TOKEN, HEADERS

    config.read(CONFIG_FILE_PATH)

    SERVER_NAME = config['DEFAULT'].get('ServerName', '')
    API_TOKEN = config['DEFAULT'].get('ApiToken', '')
    HEADERS = {
        "Content-Type": "application/json",
        "Authorization": API_TOKEN
    }

def update_configuration(new_config):
    try:
        # Update with new values
        if 'ServerName' in new_config:
            config['DEFAULT']['ServerName'] = new_config['ServerName']
        if 'ApiToken' in new_config:
            config['DEFAULT']['ApiToken'] = new_config['ApiToken']

        # Write changes back to the config file
        with open(CONFIG_FILE_PATH, 'w') as configfile:
            config.write(configfile)

        # Reload configuration
        load_configuration()

        return {"message": "Configuration updated successfully"}
    except Exception as e:
        logger.error(f"Failed to update configuration: {e}")
        return {"error": str(e)}


def handle_write_request(json_str):
    read_pause_event.set()  # Pause the read loop
    time.sleep(1)  # Allow time for read loop to pause
    write_nfc(pn532, json_str)  # Perform the write operation
    beep_sound = generate_beep(frequency=1000, duration=0.1, volume=0.5)
    play(beep_sound)
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
        response = requests.post(SERVER_NAME, headers=HEADERS, json=content, timeout=10, stream=True)
        logger.info(f"Response status code: {response.status_code}")
        response.raise_for_status()
        logger.info("Request successful.")
        return response.content  # Directly return the binary content of the response
    except requests.RequestException as e:
        logger.error(f"HTTP request error: {e}")
        return None


def play_audio(audio_data, volume_change_dB=-5):  # Default volume reduction by 10 dB
    def audio_playback_thread(audio_data):
        try:
            logger.info("Loading audio data into stream.")
            audio_stream = io.BytesIO(audio_data)
            audio = AudioSegment.from_file(audio_stream, format='mp3')
            silence = AudioSegment.silent(duration=100)  # 100 milliseconds of silence
            audio = silence + audio

            # Adjust volume
            if volume_change_dB < 0:
                logger.info(f"Reducing volume by {-volume_change_dB} dB.")
                audio = audio - (-volume_change_dB)
            elif volume_change_dB > 0:
                logger.info(f"Increasing volume by {volume_change_dB} dB.")
                audio = audio.apply_gain(volume_change_dB)

            audio = audio.set_channels(2)
            audio = audio.set_frame_rate(22050)

            logger.info("Audio data loaded, starting playback.")
            play(audio)
            logger.info("Audio playback finished.")
        except Exception as e:
            logger.error(f"Error playing audio: {e}")

    try:
        playback_thread = threading.Thread(target=audio_playback_thread, args=(audio_data,))
        playback_thread.daemon = True
        playback_thread.start()
        logger.info("Audio playback thread started.")
    except Exception as e:
        logger.error(f"Error creating audio playback thread: {e}")

def generate_beep(frequency=1000, duration=0.2, volume=0.5, sample_rate=44100):
    # Generate a sine wave
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave = np.sin(2 * np.pi * frequency * t)

    # Scale to the desired volume and convert to 16-bit format
    wave = (volume * wave * 32767).astype(np.int16)

    # Create a stereo sound (2 channels)
    stereo_wave = np.vstack((wave, wave)).T

    # Convert the NumPy array to bytes
    wave_bytes = stereo_wave.tobytes()

    # Create an AudioSegment from the raw audio data
    beep_sound = AudioSegment(
        data=wave_bytes,
        sample_width=2,  # 16-bit audio
        frame_rate=sample_rate,
        channels=2
    )

    return beep_sound

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

def write_nfc(pn532, json_str, start_page=4):
    # Convert string to bytes
    byte_data = json_str.encode()

    # Prepend the length of byte_data using 2 bytes
    length_bytes = len(byte_data).to_bytes(2, 'big')  # 2 bytes for up to 65535
    byte_data = length_bytes + byte_data

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
        write_to_nfc_tag(pn532, page, list(chunk))

    logger.info("JSON string written to NFC tag")


def write_to_nfc_tag(pn532, page, data):
    if not isinstance(page, int) or not (0 <= page <= 134):
        logger.error("Invalid page number for NFC tag write operation.")
        return
    if not isinstance(data, (list, tuple)) or len(data) != 4 or not all(isinstance(x, int) and 0 <= x < 256 for x in data):
        logger.error("Data must be a list or tuple of 4 bytes.")
        return

    try:
        pn532.ntag2xx_write_block(page, data)
        logger.info(f"Data written to NFC tag at page {page}")
    except Exception as e:
        logger.error(f"Error writing to NFC tag: {e}")


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


def is_valid_audio_file(file_path):
    try:
        # Attempt to load the file with pydub to check if it's a valid audio file
        audio = AudioSegment.from_file(file_path)
        return True  # The file is a valid audio file
    except CouldNotDecodeError:
        logger.error(f"Invalid audio file format: {file_path}")
        return False
    except Exception as e:
        logger.error(f"Error validating audio file: {e}")
        return False

def cleanup_downloaded_audio_file():
    file_path = '/tmp/local_audio.mp3'  # Path where the audio file is downloaded
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Successfully deleted temporary audio file: {file_path}")
        else:
            logger.info(f"No temporary audio file found to delete at: {file_path}")
    except Exception as e:
        logger.error(f"Error deleting temporary audio file at {file_path}: {e}")


def main():
    global read_thread
    last_uid = None
    logger.info("Script started, waiting for NFC tag.")
    beep_sound = generate_beep(frequency=1000, duration=0.1, volume=0.5)
    play(beep_sound)

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
                    beep_sound = generate_beep(frequency=1000, duration=0.1, volume=0.5)
                    play(beep_sound)

                    if full_memory:
                        parsed_data = parse_tag_data(full_memory.decode('utf-8').rstrip('\x00'))
                        if parsed_data:
                            logger.info(f"Parsed data: {parsed_data}")

                            sound_file_thread = None
                            sound_file_url = parsed_data.get('soundFileUrl')
                            if sound_file_url:
                                sound_file_thread = threading.Thread(target=download_sound_file, args=(sound_file_url,))
                                sound_file_thread.start()

                            server_audio_data = perform_http_request(parsed_data)
                            if server_audio_data:
                                logger.info("Server audio data received, starting playback.")
                                play_audio(server_audio_data)

                            if sound_file_thread:
                                sound_file_thread.join()
                                local_audio_file_path = '/tmp/local_audio.mp3'  # Path where the audio file is downloaded
                                if is_valid_audio_file(local_audio_file_path):
                                    local_audio_data = get_downloaded_audio_data()
                                    if local_audio_data:
                                        logger.info("Local audio data validated and available, starting playback.")
                                        play_audio(local_audio_data)
                                else:
                                    logger.warning("Downloaded audio file is not valid and will not be played.")

                                cleanup_downloaded_audio_file()

                elif not nfc_data:
                    last_uid = None

            except Exception as e:
                logger.error(f"An error occurred: {e}")
            time.sleep(1)

    read_thread = threading.Thread(target=read_loop)
    read_thread.start()


def signal_handler(sig, frame):
    global read_thread
    logger.info(f"Signal handler called with signal: {sig}")

    if read_thread is not None:
        logger.info("Joining the read thread...")
        read_thread.join()
        logger.info("Read thread joined successfully.")
    else:
        logger.info("No read thread to join.")

    logger.info("Exiting system...")
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

load_configuration()
main()

def run_flask_app():
    app.run(host='0.0.0.0', port=5000)

if __name__ == "__main__":

    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.start()

    main()
