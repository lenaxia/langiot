#!/bin/bash

# Test configurations
APP_DIR="$PWD/.."
LOG_FILE="$APP_DIR/test_update.log"
TARBALL_DIR="$APP_DIR/tarballs"
SERVICE_NAME="test_langiot_service"

# Path to the update script
UPDATE_SCRIPT="$APP_DIR/update.sh"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'  # No Color

# Test result variables
tests_passed=0
tests_failed=0

# Create necessary directories for testing
mkdir -p "$TARBALL_DIR"

# Function to run a test
run_test() {
    echo -e "${GREEN}--------------------------------${NC}"
    echo -e "${GREEN}Running test: $1${NC}"
    if bash "$UPDATE_SCRIPT" -d "$APP_DIR" -l "$LOG_FILE" -t "$TARBALL_DIR" -n "$SERVICE_NAME" "${@:2}"; then
        echo -e "${GREEN}Test passed: $1${NC}"
        ((tests_passed++))
    else
        echo -e "${RED}Test failed: $1${NC}"
        ((tests_failed++))
    fi
    echo -e "${GREEN}--------------------------------${NC}"
}

# Cleanup function
cleanup() {
    echo -e "${GREEN}Cleaning up test environment...${NC}"
    rm -f "$LOG_FILE"  # Remove the test-specific log file
    rm -rf "$TARBALL_DIR"/*  # Remove tarballs created during the test
    # Remove any other temporary files or services created during the tests
}

# Ensure cleanup is performed even if the script exits prematurely
trap cleanup EXIT

# Start testing
echo -e "${GREEN}Starting update script tests...${NC}"

# Test 1: Override current and latest tags to simulate an update
run_test "Version Update Test" -c "v0.9" -e "v1.0"

# Test 2: Simulate log rotation
echo "Filling up log to simulate rotation"
truncate -s 900K "$LOG_FILE"  # Make the log file large, but not over the limit
run_test "Log Rotation Test" -c "v0.9" -e "v1.1"

# Test 3: Simulate service failure and rollback
run_test "Service Failure and Rollback Test" -c "v1.1" -e "v1.2" -f

# Test 4: Cleanup old tarballs
touch "$TARBALL_DIR"/{old1,old2,old3}.tar.gz
run_test "Cleanup Old Tarballs Test" -c "v1.2" -e "v1.3"

# Test 5: No update needed
run_test "No Update Needed Test" -c "v1.3" -e "v1.3"

# Final cleanup
cleanup

# Print test results
echo -e "${GREEN}--------------------------------${NC}"
echo -e "Tests completed."
echo -e "${GREEN}Tests passed: $tests_passed${NC}"
if [ $tests_failed -gt 0 ]; then
    echo -e "${RED}Tests failed: $tests_failed${NC}"
else
    echo -e "${GREEN}Tests failed: $tests_failed${NC}"
fi

