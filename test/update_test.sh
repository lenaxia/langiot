#!/bin/bash

# Test configurations
REPO_URL="https://github.com/lenaxia/langiot.git"  # Replace with your actual repository URL
APP_DIR="$PWD/.."
LOG_FILE="$APP_DIR/test_update.log"
TARBALL_DIR="$APP_DIR/tarballs"
SERVICE_NAME="test_langiot_service"
MAX_LOG_SIZE=1048576  # 1MB in bytes

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

# Fetch the most recent tags from the GitHub repository
get_latest_tags() {
    echo "Fetching latest tags from the repository..." >&2

    # Fetch tags from the remote repository
    remote_tags=$(git ls-remote --tags "$REPO_URL")
    echo "Raw tags from repository:" >&2
    echo "$remote_tags" >&2

    # Filter out the lines containing the tags, remove refs/tags/ prefix, and sort them
    tags=()
    while IFS= read -r line; do
        echo "Processing line: $line" >&2
        if [[ $line =~ refs/tags/(.*) ]]; then
            tag="${BASH_REMATCH[1]}"
            echo "Found tag: $tag" >&2
            # Skip dereferenced tags (those ending with ^{})
            if [[ $tag != *'^{}'* ]]; then
                tags+=("$tag")
                echo "Added tag: $tag" >&2
            else
                echo "Skipped dereferenced tag: $tag" >&2
            fi
        fi
    done <<< "$remote_tags"

    echo "Unsorted tags:" >&2
    printf '%s\n' "${tags[@]}" >&2

    # Sort the tags and get the latest 3
    IFS=$'\n' sorted_tags=($(sort -V <<< "${tags[*]}"))
    unset IFS

    echo "Sorted tags:" >&2
    printf '%s\n' "${sorted_tags[@]}" >&2

    # Get the last 3 elements of the sorted tags array
    latest_tags=("${sorted_tags[@]: -3}")
    echo "Latest 3 tags:" >&2
    printf '%s\n' "${latest_tags[@]}" >&2

    # Return the latest tags
    echo "${latest_tags[@]}"
}



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

# Dynamically fetch the latest tags and run tests based on them
tags=($(get_latest_tags))
echo "Latest tags for testing: ${tags[*]}"

if [ ${#tags[@]} -ge 2 ]; then
    # Test using the latest two tags
    run_test "Version Update Test, current: ${tags[1]}, latest: ${tags[0]}" -c "${tags[1]}" -e "${tags[0]}"
fi

if [ ${#tags[@]} -ge 3 ]; then
    # Additional tests can be added as needed, using the third-latest tag as an example
    run_test "Service Failure and Rollback Test" -c "${tags[2]}" -e "${tags[1]}" -f
fi

# Log Rotation Test
truncate -s $(($MAX_LOG_SIZE - 100)) "$LOG_FILE"  # Reduce log size slightly below max
run_test "Log Rotation Test"

# Cleanup of Old Tarballs Test
touch "$TARBALL_DIR"/{test1.tar.gz,test2.tar.gz,test3.tar.gz}
run_test "Cleanup Old Tarballs Test"

# Error Handling Test
run_test "Error Handling Test" -e "nonexistent-tag"

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

