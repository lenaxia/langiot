#!/bin/bash

# Default Configuration Variables
USER="yin"
APP_NAME="langiot"
REPO_URL="https://github.com/lenaxia/langiot.git"
APP_DIR="/home/$USER/$APP_NAME"
LOG_FILE="$APP_DIR/update.log"
MAX_LOG_SIZE=1048576  # 1MB in bytes
TARBALL_DIR="$APP_DIR/tarballs"
LATEST_TARBALL="$TARBALL_DIR/$APP_NAME-latest.tar.gz"
PREVIOUS_TARBALL="$TARBALL_DIR/$APP_NAME-previous.tar.gz"
SERVICE_NAME="${APP_NAME}.service"
CURRENT_TAG=""
LATEST_TAG=""
SIMULATE_FAILURE=false

# Help message
show_help() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "-u <user>                Set the user name."
    echo "-a <app_name>            Set the application name."
    echo "-r <repo_url>            Set the repository URL."
    echo "-d <app_dir>             Set the application directory."
    echo "-l <log_file>            Set the log file path."
    echo "-s <max_log_size>        Set the maximum log file size."
    echo "-t <tarball_dir>         Set the tarball directory."
    echo "-p <latest_tarball>      Set the path for the latest tarball."
    echo "-n <service_name>        Set the service name."
    echo "-c <current_tag>         Override the current tag (for testing)."
    echo "-e <latest_tag>          Override the latest tag (for testing)."
    echo "-f                       Simulate a service failure (for testing)."
    echo "-h                       Show this help message."
    echo ""
    exit 0
}

# Function to log messages
log_message() {
    # Check if log file size exceeds the max limit and rotate if necessary
    if [ -f "$LOG_FILE" ] && [ "$(stat -c%s "$LOG_FILE")" -ge $MAX_LOG_SIZE ]; then
        mv "$LOG_FILE" "$LOG_FILE.old"
        touch "$LOG_FILE"
    fi
    echo "$(date): $1" | tee -a "$LOG_FILE"
}

# Cleanup function to retain only the newest two tarballs
cleanup_old_tarballs() {
    log_message "Cleaning up old tarballs..."
    cd "$TARBALL_DIR" || exit
    ls -t *.tar.gz | tail -n +3 | while read -r old_tarball; do
        log_message "Removing old tarball: $old_tarball"
        rm "$old_tarball"
    done
}

# Function to check and restart the service
restart_service() {
    if [ "$SIMULATE_FAILURE" = false ]; then
        sudo systemctl restart "$SERVICE_NAME"
    fi
    if [ "$SIMULATE_FAILURE" = true ] || ! systemctl is-active --quiet "$SERVICE_NAME"; then
        log_message "Simulating service failure or service failed to start..."
        return 1
    fi
    return 0
}

# Parse command-line options
while getopts ":u:a:r:d:l:s:t:p:n:c:e:fh" opt; do
  case $opt in
    u) USER="$OPTARG" ;;
    a) APP_NAME="$OPTARG" ;;
    r) REPO_URL="$OPTARG" ;;
    d) APP_DIR="$OPTARG" ;;
    l) LOG_FILE="$OPTARG" ;;
    s) MAX_LOG_SIZE="$OPTARG" ;;
    t) TARBALL_DIR="$OPTARG" ;;
    p) LATEST_TARBALL="$OPTARG" ;;
    n) SERVICE_NAME="$OPTARG" ;;
    c) CURRENT_TAG="$OPTARG" ;;
    e) LATEST_TAG="$OPTARG" ;;
    f) SIMULATE_FAILURE=true ;;
    h) show_help ;;
    \?) echo "Invalid option -$OPTARG" >&2; exit 1 ;;
  esac
done

# Start the script logic
if [ "$#" -eq 0 ]; then
    show_help
fi

# Ensure necessary directories and files exist
mkdir -p "$TARBALL_DIR"
touch "$LOG_FILE"

log_message "Starting update check..."

# Get the current and latest tags (if not overridden)
if [ -z "$CURRENT_TAG" ]; then
    CURRENT_TAG=$(git -C "$APP_DIR" describe --tags `git rev-list --tags --max-count=1`)
fi
if [ -z "$LATEST_TAG" ]; then
    LATEST_TAG=$(git ls-remote --tags "$REPO_URL" | cut -d/ -f3 | sort -V | tail -n1)
fi

log_message "Current version: $CURRENT_TAG"
log_message "Latest version: $LATEST_TAG"

# Update process
if [ "$LATEST_TAG" != "$CURRENT_TAG" ]; then
    log_message "New version detected: $LATEST_TAG. Starting update process..."

    cd "$APP_DIR" || exit

    # Prepare for update: back up the current tarball
    if [ -f "$LATEST_TARBALL" ]; then
        mv "$LATEST_TARBALL" "$PREVIOUS_TARBALL"
    fi

    # Download the new tarball
    assets_url=$(curl -s "https://api.github.com/repos/$(basename $REPO_URL)/releases/tags/$LATEST_TAG")
    download_url=$(echo "$assets_url" | jq -r '.assets[] | select(.name == "langiot-package.tar.gz") | .browser_download_url')
    wget -O "$LATEST_TARBALL" "$download_url"

    # Extract the new tarball and check the operation
    tar -xzvf "$LATEST_TARBALL" || { log_message "Extraction failed"; exit 1; }

    # Restart and check the service
    if restart_service; then
        log_message "Update to version $LATEST_TAG completed successfully. Service is running."
    else
        # Attempt to recover from the previous version if the update fails
        if [ -f "$PREVIOUS_TARBALL" ]; then
            tar -xzvf "$PREVIOUS_TARBALL" -C "$APP_DIR" || { log_message "Rollback failed"; exit 1; }
            if restart_service; then
                log_message "Successfully reverted to the previous version."
            else
                log_message "Service failed to start after revert. Manual intervention required."
            fi
        else
            log_message "No previous version to revert to. Manual intervention required."
        fi
    fi

    # Cleanup old tarballs after the update or rollback
    cleanup_old_tarballs
else
    log_message "Current version $CURRENT_TAG is up-to-date. No update required."
fi

