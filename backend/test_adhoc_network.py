#!/usr/bin/env python3

import os
import subprocess
import time
import threading
from flask import Flask, jsonify

# Configuration
ADHOC_NETWORK_INTERFACE = "wlan0"
ADHOC_NETWORK_IP = "192.168.42.1"
ADHOC_NETWORK_SSID = "LangClient-Setup"
ADHOC_NETWORK_PASS = "langclient"
ADHOC_NETWORK_TIMEOUT = 300  # 5 minutes in seconds

# Flask application setup
app = Flask(__name__)

@app.route('/')
def hello_world():
    return "Hello World!"

def start_adhoc_network():
    try:
        subprocess.run(["systemctl", "stop", "hostapd"])
        subprocess.run(["systemctl", "stop", "dnsmasq"])
        configure_adhoc_network()
        subprocess.run(["systemctl", "start", "hostapd"])
        subprocess.run(["systemctl", "start", "dnsmasq"])
        subprocess.run(["ifconfig", ADHOC_NETWORK_INTERFACE, ADHOC_NETWORK_IP])
        print(f"Ad-hoc network '{ADHOC_NETWORK_SSID}' started with password '{ADHOC_NETWORK_PASS}'")
    except subprocess.CalledProcessError as e:
        print(f"Error starting ad-hoc network: {e}")

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

        print("Ad-hoc network configuration completed")
    except Exception as e:
        print(f"Error configuring ad-hoc network: {e}")

def stop_adhoc_network():
    try:
        subprocess.run(["systemctl", "stop", "hostapd"])
        subprocess.run(["systemctl", "stop", "dnsmasq"])
        subprocess.run(["ifconfig", ADHOC_NETWORK_INTERFACE, "down"])
        print("Ad-hoc network stopped")
    except subprocess.CalledProcessError as e:
        print(f"Error stopping ad-hoc network: {e}")

def is_connected_to_wifi():
    try:
        result = subprocess.run(["nmcli", "device", "status"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if "wlan0" in line and "connected" in line:
                return True
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error checking Wi-Fi connection: {e}")
        return False

def main():
    print("Waiting for Wi-Fi connection...")
    while not is_connected_to_wifi():
        time.sleep(1)

    print("Connected to Wi-Fi. Waiting 30 seconds before starting ad-hoc network...")
    time.sleep(30)

    start_adhoc_network()

    # Start the Flask web server
    web_server_thread = threading.Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": 8080})
    web_server_thread.start()

    print("Ad-hoc network started. Web server running on port 8080.")

    # Wait for 5 minutes
    time.sleep(ADHOC_NETWORK_TIMEOUT)

    stop_adhoc_network()
    print("Ad-hoc network stopped. Reconnecting to original Wi-Fi network...")

if __name__ == "__main__":
    main()
