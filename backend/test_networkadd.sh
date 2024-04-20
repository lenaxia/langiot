#!/bin/bash

# Test networkadd.sh functionality

# Mock wpa_supplicant.conf file for testing
MOCK_WPA_CONF="./mock_wpa_supplicant.conf"
echo "" > $MOCK_WPA_CONF

# Function to add a network
add_network() {
    SSID=$1
    PSK=$2
    KEY_MGMT=$3
    ./networkadd.sh $SSID $PSK $KEY_MGMT
}

# Test adding a network
test_add_network() {
    add_network "TestSSID" "TestPSK" "WPA-PSK"
    grep -q "TestSSID" $MOCK_WPA_CONF
    if [ $? -eq 0 ]; then
        echo "Test add network: PASS"
    else
        echo "Test add network: FAIL"
    fi
}

# Run tests
test_add_network

# Cleanup
rm $MOCK_WPA_CONF
