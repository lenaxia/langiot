import dbus
import subprocess
import os
import sys

# Configuration
ADHOC_NETWORK_NAME = "LangClient-Setup"
ADHOC_NETWORK_PASS = "langclient"
ADHOC_NETWORK_INTERFACE = "wlan0"
ADHOC_NETWORK_IP = "192.168.42.1"
ADHOC_NETWORK_SUBNET = "192.168.42.0/24"

# Check and install required dependencies
required_packages = ["hostapd", "dnsmasq"]
for package in required_packages:
    try:
        subprocess.run(["dpkg", "-s", package], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print(f"Installing {package}...")
        subprocess.run(["apt-get", "install", "-y", package])

# Check if an ad-hoc network has been previously configured
try:
    subprocess.run(["cat", "/etc/hostapd/hostapd.conf"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    adhoc_network_configured = True
except subprocess.CalledProcessError:
    adhoc_network_configured = False

# Configure the ad-hoc network if not already configured
if not adhoc_network_configured:
    print("Configuring ad-hoc network...")
    os.makedirs("/etc/hostapd", exist_ok=True)
    with open("/etc/hostapd/hostapd.conf", "w") as f:
        f.write(f"interface={ADHOC_NETWORK_INTERFACE}\n")
        f.write("driver=nl80211\n")
        f.write("ssid={ADHOC_NETWORK_NAME}\n")
        f.write("hw_mode=g\n")
        f.write("channel=6\n")
        f.write("ieee80211n=1\n")
        f.write("wmm_enabled=0\n")
        f.write("ht_capab=[HT40][SHORT-GI-20][DSSS_CCK-40]\n")
        f.write("macaddr_acl=0\n")
        f.write("auth_algs=1\n")
        f.write("ignore_broadcast_ssid=0\n")
        f.write("wpa=2\n")
        f.write("wpa_passphrase={ADHOC_NETWORK_PASS}\n")
        f.write("wpa_key_mgmt=WPA-PSK\n")
        f.write("wpa_pairwise=CCMP\n")
        f.write("rsn_pairwise=CCMP\n")

    with open("/etc/dnsmasq.conf", "w") as f:
        f.write("interface={ADHOC_NETWORK_INTERFACE}\n")
        f.write(f"dhcp-range={ADHOC_NETWORK_SUBNET},192.168.42.50,192.168.42.150,12h\n")

# Start the ad-hoc network if the Raspberry Pi is offline
def start_adhoc_network():
    subprocess.run(["systemctl", "stop", "hostapd"])
    subprocess.run(["systemctl", "stop", "dnsmasq"])
    subprocess.run(["systemctl", "start", "hostapd"])
    subprocess.run(["systemctl", "start", "dnsmasq"])
    subprocess.run(["ifconfig", ADHOC_NETWORK_INTERFACE, ADHOC_NETWORK_IP])

# Stop the ad-hoc network
def stop_adhoc_network():
    subprocess.run(["systemctl", "stop", "hostapd"])
    subprocess.run(["systemctl", "stop", "dnsmasq"])

# Monitor NetworkManager's D-Bus signals
def handle_network_state_change(state):
    if state == NetworkManager.State.CONNECTED:
        print("Connected to a network. Stopping ad-hoc network.")
        stop_adhoc_network()
    else:
        print("Not connected to a network. Starting ad-hoc network.")
        start_adhoc_network()

if __name__ == "__main__":
    # Connect to NetworkManager's D-Bus interface
    bus = dbus.SystemBus()
    network_manager = bus.get_object("org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager")
    network_manager = dbus.Interface(network_manager, "org.freedesktop.NetworkManager")

    # Check the initial network state
    state = network_manager.state()
    handle_network_state_change(state)

    # Monitor network state changes
    network_manager.connect_to_signal("StateChanged", handle_network_state_change)

    try:
        loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        loop.run()
    except KeyboardInterrupt:
        sys.exit(0)
