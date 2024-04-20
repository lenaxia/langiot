#!/bin/bash

# Define log file
LOG_FILE="/var/log/wifi_network_management.log"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> $LOG_FILE
}

SSID="$1"

if [[ -z "$SSID" ]]; then
    log_message "SSID not provided for network deletion."
    exit 1
fi

CONFIG_FILE="/etc/wpa_supplicant/wpa_supplicant.conf"
TEMP_FILE="/tmp/wpa_supplicant.conf.tmp"

awk -v ssid="$SSID" '
BEGIN {skip=0}
/network={/ {block=""; skip=0}
{
    if (skip == 0) {
        block=block ORS $0
    }
}
/ssid="'"'"'"/ {
    if ($0 ~ "ssid=\"'"'"'" ssid "'"'"'\"") {
        skip=1
    }
}
/}/ {
    if (skip == 0) {
        print block
    }
}
' $CONFIG_FILE > $TEMP_FILE

if [ $? -eq 0 ]; then
    mv $TEMP_FILE $CONFIG_FILE
    log_message "Successfully deleted network $SSID."
else
    log_message "Failed to delete network $SSID."
    exit 2
fi
