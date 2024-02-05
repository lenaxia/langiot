#!/bin/bash

# Define log file
LOG_FILE="/var/log/wifi_network_management.log"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> $LOG_FILE
}

SSID="$1"
PSK="$2"
KEY_MGMT="${3:-WPA-PSK}"

if [[ -z "$SSID" || -z "$PSK" ]]; then
    log_message "SSID or PSK not provided for network addition."
    exit 1
fi

{
    echo -e "\nnetwork={"
    echo "    ssid=\"$SSID\""
    echo "    psk=\"$PSK\""
    echo "    key_mgmt=$KEY_MGMT"
    echo "}"
} >> /etc/wpa_supplicant/wpa_supplicant.conf

if [ $? -eq 0 ]; then
    log_message "Successfully added network $SSID."
else
    log_message "Failed to add network $SSID."
    exit 2
fi
