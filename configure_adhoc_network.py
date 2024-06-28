import os
import subprocess

# Configuration
ADHOC_NETWORK_NAME = "LangClient-Setup"
ADHOC_NETWORK_PASS = "langclient"
ADHOC_NETWORK_INTERFACE = "wlan0"
ADHOC_NETWORK_IP = "192.168.42.1"
ADHOC_NETWORK_SUBNET = "192.168.42.0/24"

# Install required dependencies
required_packages = ["hostapd", "dnsmasq"]
for package in required_packages:
    try:
        subprocess.run(["dpkg", "-s", package], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print(f"Installing {package}...")
        subprocess.run(["apt-get", "install", "-y", package])

# Configure the ad-hoc network
print("Configuring ad-hoc network...")
os.makedirs("/etc/hostapd", exist_ok=True)
with open("/etc/hostapd/hostapd.conf", "w") as f:
    f.write(f"interface={ADHOC_NETWORK_INTERFACE}\n")
    f.write("driver=nl80211\n")
    f.write(f"ssid={ADHOC_NETWORK_NAME}\n")
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
    f.write(f"dhcp-range={ADHOC_NETWORK_SUBNET},192.168.42.50,192.168.42.150,12h\n")

print("Ad-hoc network configuration completed.")
