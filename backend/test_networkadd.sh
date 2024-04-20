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
    echo "Adding network with SSID: $SSID, PSK: $PSK, KEY_MGMT: $KEY_MGMT"
    LOG_FILE=$MOCK_LOG_FILE bash networkadd.sh $SSID $PSK $KEY_MGMT $MOCK_WPA_CONF
}

# Test adding a network
test_add_network() {
    echo "Starting test_add_network"
    # Test adding a valid network
    LOG_FILE=$MOCK_LOG_FILE add_network "TestSSID" "TestPSK" "WPA-PSK"
    grep -q "TestSSID" $MOCK_WPA_CONF
    if [ $? -eq 0 ]; then
        echo "Valid network added successfully."
        echo "Test add network: PASS"
    else
        echo "Failed to add valid network."
        echo "Test add network: FAIL"
    fi

    # Test adding a network with empty SSID
    echo "Testing addition of network with empty SSID."
    add_network "" "TestPSK" "WPA-PSK"
    if grep -q 'ssid=""' $MOCK_WPA_CONF; then
        echo "Network with empty SSID should not be added."
        echo "Test add network with empty SSID: FAIL"
    else
        echo "Correctly handled network with empty SSID."
        echo "Test add network with empty SSID: PASS"
    fi

    # Test adding a network with empty PSK
    echo "Testing addition of network with empty PSK."
    add_network "TestSSID2" "" "WPA-PSK"
    if grep -q 'psk=""' $MOCK_WPA_CONF; then
        echo "Network with empty PSK should not be added."
        echo "Test add network with empty PSK: FAIL"
    else
        echo "Correctly handled network with empty PSK."
        echo "Test add network with empty PSK: PASS"
    fi

    # Test adding a network with special characters in SSID
    echo "Testing addition of network with special characters in SSID."
    add_network "TestSSID!@#$%^&*()" "TestPSK" "WPA-PSK"
    if grep -q 'TestSSID!@#$%^&*()' $MOCK_WPA_CONF; then
        echo "Network with special characters in SSID added successfully."
        echo "Test add network with special characters in SSID: PASS"
    else
        echo "Failed to add network with special characters in SSID."
        echo "Test add network with special characters in SSID: FAIL"
    fi
    echo "Finished test_add_network"
}

# Run tests
echo "Running network addition tests..."
test_add_network
echo "Network addition tests completed."

# Cleanup
echo "Cleaning up test environment..."
rm $MOCK_WPA_CONF
rm -f $MOCK_LOG_FILE
echo "Cleanup completed."
