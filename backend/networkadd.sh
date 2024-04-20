#!/bin/bash

# Define log file
LOG_FILE="/var/log/wifi_network_management.log"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> $LOG_FILE
}

CONFIG_FILE="${3:-/etc/wpa_supplicant/wpa_supplicant.conf}"

SSID="$1"
PSK="$2"
KEY_MGMT="${4:-WPA-PSK}"

if [[ -n "$SSID" && -n "$PSK" ]]; then
    {
        echo -e "\nnetwork={"
        echo "    ssid=\"$SSID\""
        echo "    psk=\"$PSK\""
        echo "    key_mgmt=$KEY_MGMT"
        echo -e "}\n"
    } >> $CONFIG_FILE
    if wpa_cli -i wlan0 reconfigure >> $LOG_FILE 2>&1; then
        log_message "Successfully added network $SSID and reloaded Wi-Fi settings."
    else
        log_message "Failed to reload Wi-Fi settings for $SSID."
        exit 3
    fi
else
    log_message "SSID or PSK not provided for network addition."
    exit 1
fi
} >> $CONFIG_FILE

if [ $? -eq 0 ]; then
    wpa_cli -i wlan0 reconfigure
    if [ $? -eq 0 ]; then
        log_message "Wi-Fi settings reloaded successfully."
    else
        log_message "Failed to reload Wi-Fi settings."
        exit 3
    fi
    log_message "Successfully added network $SSID."
else
    log_message "Failed to add network $SSID."
    exit 2
fi
