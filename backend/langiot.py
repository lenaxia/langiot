from pathlib import Path
from io import BytesIO
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
import wave
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
import queue
from piper import PiperVoice
from piper.download import ensure_voice_exists, get_voices, find_voice

audio_queue = queue.Queue()
audio_thread = None

# Set SDL to use the dummy audio driver so pygame doesn't require an actual sound device
#os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['TESTMODE'] = 'False'
home_dir = os.path.expanduser("$HOME")

# Set default values for environment variables
DEFAULT_CONFIG_PATH = '/config/config.ini'
DEFAULT_WEB_APP_PATH = '/app/web'

HEADERS = {"Content-Type": "application/json"}
HEALTH_CHECK_INTERVAL = 600  # 5 minutes in seconds
CONNECTED_TO_SERVER = False

# Use environment variables if they are set, otherwise use the default values
CONFIG_FILE_PATH = os.getenv('CONFIG_FILE_PATH', DEFAULT_CONFIG_PATH)
WEB_APP_PATH = os.getenv('WEB_APP_PATH', DEFAULT_WEB_APP_PATH)


# Configure the paths
PIPER_MODEL_NAME = "en_US-lessac-medium"
PIPER_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), ".piper", "downloads")
PIPER_DATA_DIRS = [PIPER_DOWNLOAD_DIR]  # No data directories specified

# Set synthesis parameters
PIPER_SYNTHESIS_ARGS = {
    "speaker_id": 0,
    "length_scale": 1.0,
    "noise_scale": 0.667,
    "noise_w": 0.8,
    "sentence_silence": 0.0,
}

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
        # Using 'nmcli' to get the current network SSID
        cmd = "nmcli device show wlan0 | grep GENERAL.CONNECTION | awk -F' ' '{print $2}'"
        ssid = subprocess.check_output(cmd, shell=True).strip()
        return ssid.decode('utf-8') if ssid else None
    except Exception as e:
        logging.error(f"Error getting active network: {e}")
        return None

def get_networks():
    try:
        networks = []
        # Using 'nmcli' to get all Wi-Fi networks
        cmd = "nmcli --terse --fields TYPE,NAME con show | awk -F: '$1 == \"802-11-wireless\" {print $2}'"
        for network in subprocess.check_output(cmd, shell=True).decode('utf-8').split('\n'):
            if network:
                networks.append({"ssid": network})
        active_ssid = get_active_network()
        return [{"ssid": network.get('ssid', ''),
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
    beep_sound = generate_beep(frequency=1000, duration=0.1, volume=0.1)
    play(beep_sound)
    read_pause_event.clear()  # Resume the read loop




def play_audio(audio_data, volume_change_dB=-5):
    global audio_queue, audio_thread

    def audio_playback_worker():
        while True:
            try:
                audio_data = audio_queue.get(block=True)
                logger.info("Loading audio data into stream.")
                audio_stream = io.BytesIO(audio_data)

                # Determine the audio format
                try:
                    with wave.open(audio_stream, 'r') as wav:
                        audio_format = 'wav'
                except wave.Error:
                    audio_stream.seek(0)
                    audio_format = 'mp3'

                audio_stream.seek(0)
                audio = AudioSegment.from_file(audio_stream, format=audio_format)
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
                if audio_format == 'wav':
                    audio = audio.set_frame_rate(22050)

                logger.info("Audio data loaded, starting playback.")
                play(audio)
                logger.info("Audio playback finished.")
                audio_queue.task_done()
            except Exception as e:
                logger.error(f"Error playing audio: {e}")
                audio_queue.task_done()

    if audio_thread is None or not audio_thread.is_alive():
        audio_thread = threading.Thread(target=audio_playback_worker, daemon=True)
        audio_thread.start()

    audio_queue.put(audio_data)

def generate_beep(frequency=1000, duration=0.2, volume=0.1, sample_rate=44100):
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
        audio = AudioSegment.from_file(file_path)
        return True  # The file is a valid audio file
    except Exception as e:
        logger.error(f"Error loading audio file: {e}")
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

def get_system_uptime_seconds():
    with open("/proc/uptime", "r") as f:
        uptime_seconds = float(f.readline().split()[0])
    return uptime_seconds


def perform_http_request(data, prefix="generate-speech"):
    try:
        url = f"{SERVER_NAME}/{prefix}"
        if prefix == "healthz":
            response = requests.get(url, timeout=10)
        else:
            if 'memory_data' in data:
                content = json.loads(data['memory_data'])
                logger.info(f"Content parsed from memory_data: {content}")
            else:
                content = data
                logger.info(f"Using provided data as content: {content}")

            response = requests.post(url, headers=HEADERS, json=content, timeout=10, stream=True)

        logger.info(f"Response status code: {response.status_code}")
        response.raise_for_status()
        logger.info("Request successful.")
        return response.content  # Directly return the binary content of the response
    except requests.RequestException as e:
        logger.error(f"HTTP request error: {e}")
        return None

def check_server_health():
    global CONNECTED_TO_SERVER
    while True:
        try:
            response = perform_http_request({}, "healthz")
            if response and json.loads(response) == {"status": "healthy"}:
                CONNECTED_TO_SERVER = True
                logger.info("Health check to server successful.")
            else:
                CONNECTED_TO_SERVER = False
                logger.info("Health check to server unsuccessful. Disconnected from server.")
        except Exception as e:
            logger.error(f"Error checking server health: {e}")
            CONNECTED_TO_SERVER = False

        time.sleep(HEALTH_CHECK_INTERVAL)

def main():
    global read_thread
    last_uid = None
    tag_cleared = False  # State to track if we have seen an empty cycle
    logger.info("Script started, waiting for NFC tag.")

    # Start server health check thread
    health_check_thread = threading.Thread(target=check_server_health)
    health_check_thread.start()

    # Announce connection status
    #if CONNECTED_TO_SERVER:
    #    generate_tts("Connected to server", "en")
    #else:
    #    generate_tts("Not connected to server, only English Text to Speech is available", "en")

    def read_loop():
        nonlocal last_uid, tag_cleared
        while True:
            try:
                nfc_data = check_for_nfc_tag(pn532)

                # Check if no tag is present and update the tag_cleared state
                if not nfc_data:
                    last_uid = None
                    tag_cleared = True

                # Proceed if a new NFC tag is detected and the reader has been cleared at least once
                elif nfc_data and nfc_data != last_uid and tag_cleared:
                    last_uid = nfc_data
                    logger.info("New NFC tag detected, processing.")
                    full_memory = read_tag_memory(pn532, start_page=4)
                    logger.info("Tag memory read, processing data.")
                    beep_sound = generate_beep(frequency=1000, duration=0.1, volume=0.1)
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

                            try:
                                server_audio_data = perform_http_request(parsed_data, "audio")
                                if server_audio_data:
                                    logger.info("Server audio data received, starting playback.")
                                    play_audio(server_audio_data)
                            except requests.Timeout:
                                logger.warning("HTTP request timed out")

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
            except Exception as e:
                logger.error(f"An error occurred: {e}")
            time.sleep(1)


    read_thread = threading.Thread(target=read_loop)
    read_thread.start()

# Load the Piper voice model
#def load_voice_model():
#    # Create the required directories if they don't exist
#    piper_download_dir = Path(PIPER_DOWNLOAD_DIR)
#    piper_download_dir.mkdir(parents=True, exist_ok=True)
#
#    voices_info = get_voices(PIPER_DOWNLOAD_DIR, update_voices=True)
#    ensure_voice_exists(PIPER_MODEL_NAME, [PIPER_DOWNLOAD_DIR], PIPER_DOWNLOAD_DIR, voices_info)
#    model_path, config_path = find_voice(PIPER_MODEL_NAME, [PIPER_DOWNLOAD_DIR])
#    voice = PiperVoice.load(str(model_path), config_path=str(config_path), use_cuda=False)
#    return voice
#
#def generate_tts(text, locale="en"):
#    logger.info(f"Generate TTS: [{locale}] {text}")
#    if locale != "en":
#        text = "Only English is currently supported for offline text to speech."
#
#    try:
#        audio_fp = io.BytesIO()
#        with wave.open(audio_fp, "wb") as wav_file:
#            voice.synthesize(text, wav_file, **synthesis_args)
#        audio_fp.seek(0)
#        logger.info(f"Generate TTS finished")
#        return audio_fp.read()
#    except Exception as e:
#        raise Exception(f"Local TTS: Failed to generate speech: {text} {locale} {e}")
#
#def text_to_speech(text, language):
#    logger.info(f"Local TTS: [{language}] {text}")
#    combined_mp3 = io.BytesIO()
#    tts_audio_bytes = generate_tts(localized_text, "en")
#    combined_mp3.write(tts_audio_bytes)
#    combined_mp3.seek(0)
#    play_audio(combined_mp3.getvalue())
#    logger.info(f"Local TTS finished")
#
#def handle_local_tts(parsed_data):
#    logger.info(f"handle_local_tts start: {parsed_data}")
#    try:
#        combined_mp3 = io.BytesIO()
#
#        memory_data_str = parsed_data.get("memory_data")
#        if memory_data_str:
#            memory_data = json.loads(memory_data_str)
#            text = memory_data.get("text")
#            language = memory_data.get("language", "en")
#        else:
#            text = "No valid data found"
#            language = "en"
#
#        if text and language:
#            tts_audio_bytes = generate_tts(text, language)
#            combined_mp3.write(tts_audio_bytes)
#
#        # We currently do not iterate through translations because piper only supports english
#
#        if localizations:
#            logger.info(f"handle_local_tts localizations start")
#            if "en" in localizations:
#                localized_text = localizations["en"]
#                logger.info(f"Localized TTS: [en] {localized_text}")
#                tts_audio_bytes = generate_tts(localized_text, "en")
#                combined_mp3.write(tts_audio_bytes)
#            else:
#                logger.info(f"localization enslish not found, so sending in a random language")
#                tts_audio_bytes = generate_tts(localized_text, "zh")
#                combined_mp3.write(tts_audio_bytes)
#
#        combined_mp3.seek(0)
#        play_audio(combined_mp3.getvalue())
#        logger.info("handle_local_tts finished")
#
#    except Exception as e:
#        logger.error(f"Error in generate-speech: {e}")
#        return jsonify({"error": "Text-to-Speech conversion failed", "details": str(e)}), 500

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
voice = load_voice_model()
main()

def run_flask_app():
    app.run(host='0.0.0.0', port=5000)

if __name__ == "__main__":

    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.start()

    main()
