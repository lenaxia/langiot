#!/bin/bash

# Define log file
LOG_FILE="${LOG_FILE:-/var/log/wifi_network_management.log}"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> $LOG_FILE
}

SSID="$1"

if [[ -n "$SSID" ]]; then
    nmcli con down "$SSID" && \
    nmcli con delete "$SSID" && \
    log_message "Successfully deleted network $SSID." || \
    { log_message "Failed to delete network $SSID."; exit 1; }
else
    log_message "SSID not provided for network deletion."
    exit 1
fi
