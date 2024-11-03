import dbus
import dbus.mainloop.glib
from dbus.mainloop.glib import DBusGMainLoop
from NetworkManager import NetworkManager, AccessPoint, Device
import subprocess
import sys

# Configuration
ADHOC_NETWORK_INTERFACE = "wlan0"
ADHOC_NETWORK_IP = "192.168.42.1"

# Start the ad-hoc network
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

# Monitor NetworkManager's signals
def handle_network_state_change(state):
    if state == NetworkManager.State.CONNECTED:
        print("Connected to a network. Stopping ad-hoc network.")
        stop_adhoc_network()
    else:
        print("Not connected to a network. Starting ad-hoc network.")
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
