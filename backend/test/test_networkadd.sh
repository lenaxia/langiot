#!/bin/bash

# Test networkadd.sh functionality

# Mock wpa_supplicant.conf file for testing
MOCK_WPA_CONF="../mock_wpa_supplicant.conf"
MOCK_LOG_FILE="../mock_wifi_network_management.log"
echo "" > $MOCK_WPA_CONF
echo "" > $MOCK_LOG_FILE
# Mock wpa_supplicant.conf file for testing
MOCK_WPA_CONF="../mock_wpa_supplicant.conf"
MOCK_LOG_FILE="../mock_wifi_network_management.log"
echo "" > $MOCK_WPA_CONF
echo "" > $MOCK_LOG_FILE

# Function to add a network
add_network() {
    SSID=$1
    PSK=$2
    KEY_MGMT=$3
    LOG_FILE=$MOCK_LOG_FILE bash ../networkadd.sh $SSID $PSK $KEY_MGMT $MOCK_WPA_CONF
}

# Test adding a network
test_add_network() {
    # Test adding a valid network
    LOG_FILE=$MOCK_LOG_FILE add_network "TestSSID" "TestPSK" "WPA-PSK"
    add_network "TestSSID" "TestPSK" "WPA-PSK"
    grep -q "TestSSID" $MOCK_WPA_CONF
    if [ $? -eq 0 ]; then
        echo "Test add network: PASS"
    else
        echo "Test add network: FAIL"
    fi

    # Test adding a network with empty SSID
    add_network "" "TestPSK" "WPA-PSK"
    if grep -q 'ssid=""' $MOCK_WPA_CONF; then
        echo "Test add network with empty SSID: FAIL"
    else
        echo "Test add network with empty SSID: PASS"
    fi

    # Test adding a network with empty PSK
    add_network "TestSSID2" "" "WPA-PSK"
    if grep -q 'psk=""' $MOCK_WPA_CONF; then
        echo "Test add network with empty PSK: FAIL"
    else
        echo "Test add network with empty PSK: PASS"
    fi

    # Test adding a network with special characters in SSID
    add_network "TestSSID!@#$%^&*()" "TestPSK" "WPA-PSK"
    if grep -q 'TestSSID!@#$%^&*()' $MOCK_WPA_CONF; then
        echo "Test add network with special characters in SSID: PASS"
    else
        echo "Test add network with special characters in SSID: FAIL"
    fi
}

# Run tests
test_add_network

# Cleanup
rm $MOCK_WPA_CONF
rm $MOCK_LOG_FILE
rm $MOCK_LOG_FILE
