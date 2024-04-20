#!/bin/bash

# Test networkdelete.sh functionality

# Mock wpa_supplicant.conf file for testing
MOCK_WPA_CONF="./mock_wpa_supplicant.conf"
echo "" > $MOCK_WPA_CONF

# Function to add a network for setup
add_network() {
    SSID=$1
    PSK=$2
    KEY_MGMT=$3
    echo -e "\nnetwork={\n    ssid=\"$SSID\"\n    psk=\"$PSK\"\n    key_mgmt=$KEY_MGMT\n}" >> $MOCK_WPA_CONF
}

# Function to delete a network
delete_network() {
    SSID=$1
    ./networkdelete.sh $SSID
}

# Setup: Add a network to delete
add_network "TestSSID" "TestPSK" "WPA-PSK"

# Test deleting a network
test_delete_network() {
    delete_network "TestSSID"
    grep -q "TestSSID" $MOCK_WPA_CONF
    if [ $? -eq 0 ]; then
        echo "Test delete network: FAIL"
    else
        echo "Test delete network: PASS"
    fi
}

# Run tests
test_delete_network

# Cleanup
rm $MOCK_WPA_CONF
