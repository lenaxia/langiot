import subprocess
import sys
import logging
import random
import string
import os
import time

import time
import subprocess
import logging
from NetworkManager import NetworkManager
from langiot import generate_tts

# Configuration
ADHOC_NETWORK_INTERFACE = "wlan0"
ADHOC_NETWORK_IP = "192.168.42.1"
ADHOC_NETWORK_SSID = "LangClient-Setup"
ADHOC_NETWORK_PASS = "langclient"
ADHOC_NETWORK_TIMEOUT = 60  # Timeout in seconds before switching to ad-hoc network

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def start_adhoc_network():
    try:
        subprocess.run(["systemctl", "stop", "hostapd"])
        subprocess.run(["systemctl", "stop", "dnsmasq"])
        configure_adhoc_network()
        subprocess.run(["systemctl", "start", "hostapd"])
        subprocess.run(["systemctl", "start", "dnsmasq"])
        subprocess.run(["ifconfig", ADHOC_NETWORK_INTERFACE, ADHOC_NETWORK_IP])
        logger.info(f"Ad-hoc network '{ADHOC_NETWORK_SSID}' started with password '{ADHOC_NETWORK_PASS}'")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error starting ad-hoc network: {e}")

def configure_adhoc_network():
    try:
        os.makedirs("/etc/hostapd", exist_ok=True)
        with open("/etc/hostapd/hostapd.conf", "w") as f:
            f.write(f"interface={ADHOC_NETWORK_INTERFACE}\n")
            f.write("driver=nl80211\n")
            f.write(f"ssid={ADHOC_NETWORK_SSID}\n")
            f.write("hw_mode=g\n")
            f.write("channel=6\n")
            f.write("ieee80211n=1\n")
            f.write("wmm_enabled=0\n")
            f.write("ht_capab=[HT40][SHORT-GI-20][DSSS_CCK-40]\n")
            f.write("macaddr_acl=0\n")
            f.write("auth_algs=1\n")
            f.write("ignore_broadcast_ssid=0\n")
            f.write("wpa=2\n")
            f.write(f"wpa_passphrase={ADHOC_NETWORK_PASS}\n")
            f.write("wpa_key_mgmt=WPA-PSK\n")
            f.write("wpa_pairwise=CCMP\n")
            f.write("rsn_pairwise=CCMP\n")

        with open("/etc/dnsmasq.conf", "w") as f:
            f.write(f"interface={ADHOC_NETWORK_INTERFACE}\n")
            f.write(f"dhcp-range={ADHOC_NETWORK_IP},192.168.42.50,192.168.42.150,12h\n")

        logger.info("Ad-hoc network configuration completed")
    except Exception as e:
        logger.error(f"Error configuring ad-hoc network: {e}")

if __name__ == "__main__":
    nm = NetworkManager()
    start_time = time.time()

    while time.time() - start_time < ADHOC_NETWORK_TIMEOUT:
        state = nm.state()
        if state == NetworkManager.State.CONNECTED:
            logger.info("Connected to a network. Ad-hoc network not needed.")
            break
        time.sleep(1)
    else:
        logger.info(f"No network connection found within {ADHOC_NETWORK_TIMEOUT} seconds. Starting ad-hoc network.")
        generate_tts(f"No Wi-Fi network found, starting ad-hoc network {ADHOC_NETWORK_SSID}", "en")
        start_adhoc_network()
