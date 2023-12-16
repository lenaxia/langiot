import busio
import board
from digitalio import DigitalInOut
from adafruit_pn532.i2c import PN532_I2C
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

def init_nfc_reader():
    i2c = busio.I2C(board.SCL, board.SDA)
    reset_pin = DigitalInOut(board.D6)  # Adjust as per your connection
    pn532 = PN532_I2C(i2c, reset=reset_pin)
    pn532.SAM_configuration()
    return pn532

def read_nfc_tag_memory(pn532, start_page=4):
    # Read the length bytes first (2 bytes)
    length_data = pn532.ntag2xx_read_block(start_page)
    length = int.from_bytes(length_data[:2], 'big')

    # Adjust for the page size
    page_size = 4
    total_bytes_to_read = length + 2  # Including the 2 bytes for length
    total_pages_to_read = -(-total_bytes_to_read // page_size)  # Ceiling division

    tag_data = bytearray()
    for i in range(total_pages_to_read):
        data = pn532.ntag2xx_read_block(start_page + i)
        if data is not None:
            tag_data.extend(data)
        else:
            break

    # Skip the first 2 bytes (length bytes) and return the actual data
    return tag_data[2:2+length]


def main():
    pn532 = init_nfc_reader()
    logger.info("Waiting for an NFC tag...")
    while True:
        uid = pn532.read_passive_target(timeout=0.5)
        if uid is not None:
            logger.info(f"Found card with UID: {uid.hex()}")
            tag_data = read_nfc_tag_memory(pn532)

            # Attempt to decode the data as a UTF-8 string
            try:
                tag_str = tag_data.decode('utf-8').rstrip('\x00')
                logger.info("Tag data (decoded as string):")
                print(tag_str)
            except UnicodeDecodeError:
                logger.error("Tag data could not be decoded as a UTF-8 string.")

                # Additional Handling: Display raw bytes or hex representation
                logger.info("Displaying raw tag data:")
                print(tag_data)
                logger.info("Displaying tag data in hexadecimal format:")
                print(tag_data.hex())

            break


if __name__ == "__main__":
    main()
