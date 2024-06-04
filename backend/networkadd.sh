#!/bin/bash

# Define log file
LOG_FILE="${LOG_FILE:-/var/log/wifi_network_management.log}"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> $LOG_FILE
}

SSID="$1"
PSK="$2"

if [[ -n "$SSID" && -n "$PSK" ]]; then
    nmcli --ask --wait 30 dev wifi connect "$SSID" password "$PSK" && \
    log_message "Successfully added network $SSID." || \
    { log_message "Failed to add network $SSID."; exit 1; }
else
    log_message "SSID or PSK not provided for network addition."
    exit 1
fi
