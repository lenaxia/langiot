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

# Test case 1: Provide valid SSID
log_message "Test case 1: Provide valid SSID"
./backend/networkadd.sh "MyNetwork" "MyPassword"
./backend/networkdelete.sh "MyNetwork"
if ! nmcli con show "MyNetwork" >/dev/null 2>&1; then
    log_message "Test case 1 passed"
else
    log_message "Test case 1 failed"
fi
cleanup_networks

# Test case 2: Provide empty SSID
log_message "Test case 2: Provide empty SSID"
./backend/networkdelete.sh "" 2>&1 | grep -q "SSID not provided"
if [ $? -eq 0 ]; then
    log_message "Test case 2 passed"
else
    log_message "Test case 2 failed"
fi

# Test case 3: Provide non-existent SSID
log_message "Test case 3: Provide non-existent SSID"
./backend/networkdelete.sh "NonExistentNetwork" 2>&1 | grep -q "Failed to delete network"
if [ $? -eq 0 ]; then
    log_message "Test case 3 passed"
else
    log_message "Test case 3 failed"
fi

# Test case 4: Provide SSID with leading/trailing spaces
log_message "Test case 4: Provide SSID with leading/trailing spaces"
./backend/networkadd.sh "  MyNetwork  " "MyPassword"
./backend/networkdelete.sh "  MyNetwork  "
if ! nmcli con show "  MyNetwork  " >/dev/null 2>&1; then
    log_message "Test case 4 passed"
else
    log_message "Test case 4 failed"
fi
cleanup_networks

# Test case 5: Provide SSID with maximum allowed length
log_message "Test case 5: Provide SSID with maximum allowed length"
MAX_SSID_LENGTH=32
SSID=$(head /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w $MAX_SSID_LENGTH | head -n 1)
./backend/networkadd.sh "$SSID" "MyPassword"
./backend/networkdelete.sh "$SSID"
if ! nmcli con show "$SSID" >/dev/null 2>&1; then
    log_message "Test case 5 passed"
else
    log_message "Test case 5 failed"
fi
cleanup_networks

# Test case 6: Provide SSID exceeding maximum allowed length
log_message "Test case 6: Provide SSID exceeding maximum allowed length"
LONG_SSID=$(head /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 33 | head -n 1)
./backend/networkdelete.sh "$LONG_SSID" 2>&1 | grep -q "Failed to delete network"
if [ $? -eq 0 ]; then
    log_message "Test case 6 passed"
else
    log_message "Test case 6 failed"
fi

# Test case 7: Attempt to delete a non-existent network
log_message "Test case 7: Attempt to delete a non-existent network"
./backend/networkdelete.sh "NonExistentNetwork" 2>&1 | grep -q "Failed to delete network"
if [ $? -eq 0 ]; then
    log_message "Test case 7 passed"
else
    log_message "Test case 7 failed"
fi

# Restore the existing networks after running tests
for network in $EXISTING_NETWORKS; do
    nmcli con add type wifi ifname wlan0 con-name "$network" ssid "$network"
done

log_message "Test cases completed"
