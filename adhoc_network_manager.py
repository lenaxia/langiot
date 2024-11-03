import dbus
import dbus.mainloop.glib
from dbus.mainloop.glib import DBusGMainLoop
from NetworkManager import NetworkManager, AccessPoint, Device
import subprocess
import sys
import logging
import random
import string
import os  # Import the os module

# Configuration
ADHOC_NETWORK_INTERFACE = "wlan0"
ADHOC_NETWORK_IP = "192.168.42.1"

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Generate a random SSID and password
def generate_random_string(length):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

ADHOC_NETWORK_SSID = f"LangClient-{generate_random_string(4)}"
ADHOC_NETWORK_PASS = generate_random_string(8)

# Start the ad-hoc network
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

# Stop the ad-hoc network
def stop_adhoc_network():
    try:
        subprocess.run(["systemctl", "stop", "hostapd"])
        subprocess.run(["systemctl", "stop", "dnsmasq"])
        logger.info("Ad-hoc network stopped")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error stopping ad-hoc network: {e}")

# Configure the ad-hoc network
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

# Monitor NetworkManager's signals
def handle_network_state_change(state):
    if state == NetworkManager.State.CONNECTED:
        logger.info("Connected to a network. Stopping ad-hoc network.")
        stop_adhoc_network()
    else:
        logger.info("Not connected to a network. Starting ad-hoc network.")
        start_adhoc_network()

if __name__ == "__main__":
    # Set up the D-Bus main loop
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    nm = NetworkManager()

    # Check the initial network state
    state = nm.state()
    handle_network_state_change(state)

    # Monitor network state changes
    nm.state_changed_signal.connect(handle_network_state_change)

    try:
        nm.loop.run()
    except KeyboardInterrupt:
        sys.exit(0)
