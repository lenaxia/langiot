import board
import busio
from digitalio import DigitalInOut
from adafruit_pn532.i2c import PN532_I2C
import pygame
import time

i2c = busio.I2C(board.SCL, board.SDA)
reset_pin = DigitalInOut(board.D6)  # Adjust as per your connection
pn532 = PN532_I2C(i2c, reset=reset_pin)

def read_nfc_data(pn532):
    # Start reading from the first user page
    start_page = 4
    end_page = 134  # Adjust this depending on your NFC tag's capacity

    tag_data = bytearray()
    for page in range(start_page, end_page + 1):
        try:
            data = pn532.ntag2xx_read_block(page)
            if data is not None:
                tag_data.extend(data)
            else:
                print(f"Failed to read page {page}")
                break
        except Exception as e:
            print(f"Error reading page {page}: {e}")
            break

    return tag_data

def test_nfc():
    i2c = busio.I2C(board.SCL, board.SDA)
    reset_pin = DigitalInOut(board.D6)  # Adjust as per your connection
    pn532 = PN532_I2C(i2c, reset=reset_pin)

    ic, ver, rev, support = pn532.firmware_version
    print(f"Found PN532 with firmware version: {ver}.{rev}")

    pn532.SAM_configuration()

    print("Waiting for an NFC tag...")
    while True:
        uid = pn532.read_passive_target(timeout=0.5)
        if uid is not None:
            print(f"Found card with UID: {uid.hex()}")
            # Read NFC tag data
            tag_data = read_nfc_data(pn532)
            try:
                # Attempt to decode the data as a UTF-8 string
                tag_str = tag_data.decode('utf-8').strip('\x00')
                print("Tag data:", tag_str)
            except UnicodeDecodeError:
                print("Tag data could not be decoded as a UTF-8 string.")
            break


def test_audio():
    # Initialize Pygame Mixer
    pygame.mixer.init()
    pygame.mixer.music.load('/path/to/test.wav')  # Replace with the path to your WAV file

    # Play Audio
    print("Playing Test Audio")
    pygame.mixer.music.play()

    # Wait for the audio to finish playing
    while pygame.mixer.music.get_busy():
        time.sleep(1)

    print("Audio Playback Complete")