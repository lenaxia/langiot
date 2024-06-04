#!/bin/bash

# Define log file
LOG_FILE="${LOG_FILE:-/var/log/wifi_network_management.log}"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> $LOG_FILE
}

# Function to clean up networks
cleanup_networks() {
    log_message "Cleaning up networks..."
    NEW_NETWORKS=$(mktemp)
    nmcli con show | awk '/wifi/ {print $1}' | grep -v -F "$EXISTING_NETWORKS" > "$NEW_NETWORKS"
    while read -r line; do
        nmcli con down id "$line"
        nmcli con delete id "$line"
    done < "$NEW_NETWORKS"
    rm "$NEW_NETWORKS"
}

# Get the list of existing networks before running tests
EXISTING_NETWORKS=$(nmcli con show | awk '/wifi/ {print $1}')

# Test case 1: Provide valid SSID and PSK
log_message "Test case 1: Provide valid SSID and PSK"
./backend/networkadd.sh "MyNetwork" "MyPassword"
if nmcli con show "MyNetwork" >/dev/null 2>&1; then
    log_message "Test case 1 passed"
else
    log_message "Test case 1 failed"
fi
cleanup_networks

# Test case 2: Provide empty SSID
log_message "Test case 2: Provide empty SSID"
./backend/networkadd.sh "" "MyPassword" 2>&1 | grep -q "SSID not provided"
if [ $? -eq 0 ]; then
    log_message "Test case 2 passed"
else
    log_message "Test case 2 failed"
fi

# Test case 3: Provide empty PSK
log_message "Test case 3: Provide empty PSK"
./backend/networkadd.sh "MyNetwork" "" 2>&1 | grep -q "SSID or PSK not provided"
if [ $? -eq 0 ]; then
    log_message "Test case 3 passed"
else
    log_message "Test case 3 failed"
fi

# Test case 4: Provide non-existent SSID
log_message "Test case 4: Provide non-existent SSID"
./backend/networkadd.sh "NonExistentNetwork" "MyPassword" 2>&1 | grep -q "Failed to add network"
if [ $? -eq 0 ]; then
    log_message "Test case 4 passed"
else
    log_message "Test case 4 failed"
fi

# Test case 5: Provide invalid characters in SSID
log_message "Test case 5: Provide invalid characters in SSID"
./backend/networkadd.sh "Invalid!@#$%SSID" "MyPassword" 2>&1 | grep -q "Failed to add network"
if [ $? -eq 0 ]; then
    log_message "Test case 5 passed"
else
    log_message "Test case 5 failed"
fi

# Test case 6: Provide invalid characters in PSK
log_message "Test case 6: Provide invalid characters in PSK"
./backend/networkadd.sh "MyNetwork" "Invalid!@#$%PSK" 2>&1 | grep -q "Failed to add network"
if [ $? -eq 0 ]; then
    log_message "Test case 6 passed"
else
    log_message "Test case 6 failed"
fi

# Test case 7: Provide SSID and PSK with leading/trailing spaces
log_message "Test case 7: Provide SSID and PSK with leading/trailing spaces"
./backend/networkadd.sh "  MyNetwork  " "  MyPassword  "
if nmcli con show "  MyNetwork  " >/dev/null 2>&1; then
    log_message "Test case 7 passed"
else
    log_message "Test case 7 failed"
fi
cleanup_networks

# Test case 8: Provide SSID and PSK with maximum allowed lengths
log_message "Test case 8: Provide SSID and PSK with maximum allowed lengths"
MAX_SSID_LENGTH=32
MAX_PSK_LENGTH=63
SSID=$(head /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w $MAX_SSID_LENGTH | head -n 1)
PSK=$(head /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w $MAX_PSK_LENGTH | head -n 1)
./backend/networkadd.sh "$SSID" "$PSK"
if nmcli con show "$SSID" >/dev/null 2>&1; then
    log_message "Test case 8 passed"
else
    log_message "Test case 8 failed"
fi
cleanup_networks

# Test case 9: Provide SSID and PSK exceeding maximum allowed lengths
log_message "Test case 9: Provide SSID and PSK exceeding maximum allowed lengths"
LONG_SSID=$(head /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 33 | head -n 1)
LONG_PSK=$(head /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1)
./backend/networkadd.sh "$LONG_SSID" "$LONG_PSK" 2>&1 | grep -q "Failed to add network"
if [ $? -eq 0 ]; then
    log_message "Test case 9 passed"
else
    log_message "Test case 9 failed"
fi

# Test case 10: Attempt to add an already existing network
log_message "Test case 10: Attempt to add an already existing network"
./backend/networkadd.sh "MyNetwork" "MyPassword"
./backend/networkadd.sh "MyNetwork" "MyPassword" 2>&1 | grep -q "Successfully added network"
if [ $? -eq 0 ]; then
    log_message "Test case 10 passed"
else
    log_message "Test case 10 failed"
fi
cleanup_networks

# Restore the existing networks after running tests
for network in $EXISTING_NETWORKS; do
    nmcli con add type wifi ifname wlan0 con-name "$network" ssid "$network"
done

log_message "Test cases completed"
