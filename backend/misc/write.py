import logging
from adafruit_pn532.i2c import PN532_I2C # pip install adafruit-blinka adafruit-circuitpython-pn532
from digitalio import DigitalInOut
import os
import signal
import sys
import busio
import board
import json
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

def is_valid_json(json_str):
    try:
        json.loads(json_str)
        return True
    except json.JSONDecodeError:
        return False


def check_for_nfc_tag(pn532):
    uid = pn532.read_passive_target(timeout=0.5)
    if uid is not None:
        logger.info("NFC tag detected")
        return uid
    return None

def init_nfc_reader():
    i2c = busio.I2C(board.SCL, board.SDA)

    reset_pin_number = int(os.getenv('RESET_PIN', '6'))  # Default to pin 6 if not set
    req_pin_number = int(os.getenv('REQ_PIN', '12'))    # Default to pin 12 if not set

    reset_pin = DigitalInOut(getattr(board, f'D{reset_pin_number}'))
    req_pin = DigitalInOut(getattr(board, f'D{req_pin_number}'))

    pn532 = PN532_I2C(i2c, debug=False, reset=reset_pin, req=req_pin)
    pn532.SAM_configuration()

    return pn532

def write_json_string_to_nfc(pn532, json_str, start_page=4):
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


def main():
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Write JSON string to NFC tag.')
    parser.add_argument('json_string', type=str, help='A JSON string to write to the NFC tag')

    # Parse arguments
    args = parser.parse_args()

    # Extract the JSON string from arguments
    json_string = args.json_string

    # Initialize NFC reader
    pn532 = init_nfc_reader()

    # Check for NFC tag and write when ready
    logger.info("Waiting for NFC tag to write to...")
    while True:
        nfc_data = check_for_nfc_tag(pn532)
        if nfc_data:
            logger.info("NFC tag detected, writing data...")
            write_json_string_to_nfc(pn532, json_string)
            break
        time.sleep(1)

# Execute the main function when the script is run
if __name__ == "__main__":
    main()