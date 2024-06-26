#!/bin/bash

# Default Configuration Variables
APP_NAME="langiot"
REPO_URL="https://github.com/lenaxia/langiot"
APP_DIR="$HOME/$APP_NAME"
LOG_FILE="$HOME/langiot-update.log"
MAX_LOG_SIZE=1048576  # 1MB in bytes
TARBALL_DIR="$HOME/langiot-tarballs"
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

# Function to compare semantic versions
compare_versions() {
    # Strip non-numeric prefix (like 'v') before comparison
    local ver1_str=${1#v}
    local ver2_str=${2#v}

    if [[ $ver1_str == $ver2_str ]]
    then
        return 0
    fi

    local IFS=.
    local i ver1=($ver1_str) ver2=($ver2_str)
    # fill empty fields in ver1 with zeros
    for ((i=${#ver1[@]}; i<${#ver2[@]}; i++))
    do
        ver1[i]=0
    done
    for ((i=0; i<${#ver1[@]}; i++))
    do
        if [[ -z ${ver2[i]} ]]
        then
            # fill empty fields in ver2 with zeros
            ver2[i]=0
        fi
        if ((10#${ver1[i]} > 10#${ver2[i]}))
        then
            return 1
        fi
        if ((10#${ver1[i]} < 10#${ver2[i]}))
        then
            return 2
        fi
    done
    return 0  # Return 0 if versions are equal after comparison
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
    local stability_check_interval=5  # Seconds to wait before re-checking the service status
    local max_checks=3  # Number of times to check for stability
    local check_count=0

    if [ "$SIMULATE_FAILURE" = "true" ]; then
        log_message "Simulating service failure..."
        return 1
    else
        sudo systemctl restart "$SERVICE_NAME"
        while [ $check_count -lt $max_checks ]; do
            if ! systemctl is-active --quiet "$SERVICE_NAME"; then
                log_message "Service failed to start..."
                return 1
            fi
            if systemctl --quiet is-failed "$SERVICE_NAME"; then
                log_message "Service is in a failed state..."
                return 1
            fi

            log_message "Service is active, checking for stability..."
            sleep $stability_check_interval
            ((check_count++))
        done
    fi
    log_message "Service has remained active for $(($stability_check_interval * $max_checks)) seconds. Assuming stability."
    return 0
}

# Function to attempt rollback
attempt_rollback() {
    local tarball_to_rollback="$1"
    log_message "Attempting to roll back to $tarball_to_rollback..."
    tar -xzvf "$tarball_to_rollback" -C "$APP_DIR" || return 1
    if restart_service; then
        log_message "Successfully reverted to $(basename "$tarball_to_rollback")."
        return 0
    else
        log_message "Service failed to start after revert to $(basename "$tarball_to_rollback")."
        return 1
    fi
}

# Extract version from tarball filename
extract_version() {
    local filename="$1"
    echo "$filename" | sed -E 's/.*-([0-9]+(\.[0-9]+)*).tar.gz/\1/'
}

# Compare and sort tarball versions
sort_tarballs_by_version() {
    local tarballs=("$@")
    local sorted=()
    local t version

    for t in "${tarballs[@]}"; do
        version=$(extract_version "$t")
        local inserted=false
        for ((i = 0; i < ${#sorted[@]}; i++)); do
            compare_versions "$(extract_version "${sorted[i]}")" "$version"
            if [ $? -eq 2 ]; then
                sorted=("${sorted[@]:0:i}" "$t" "${sorted[@]:i}")
                inserted=true
                break
            fi
        done
        if [ "$inserted" = false ]; then
            sorted+=("$t")
        fi
    done

    echo "${sorted[@]}"
}

# Function to handle the rollback process
rollback_service() {
    local all_tarballs=("$TARBALL_DIR/$APP_NAME"-*.tar.gz)
    local sorted_tarballs=($(sort_tarballs_by_version "${all_tarballs[@]}"))

    local attempts=0
    for tarball in "${sorted_tarballs[@]}"; do
        if [ "$attempts" -ge 2 ]; then
            break
        fi

        if [ "$tarball" != "$LATEST_TARBALL" ]; then
            if attempt_rollback "$tarball"; then
                return 0
            fi
            ((attempts++))
        fi
    done

    log_message "Rollback failed after two attempts. Manual intervention required."
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

# If the help option is not called, proceed with the script
if [ "$OPTIND" -eq 1 ]; then
    log_message "Proceeding with default configuration..."
fi

# Ensure necessary directories and files exist
mkdir -p "$TARBALL_DIR"
touch "$LOG_FILE"

log_message "Starting update check..."

# Get the current and latest tags (if not overridden)
if [ -z "$CURRENT_TAG" ]; then
    #CURRENT_TAG=$(git -C "$APP_DIR" describe --tags `git rev-list --tags --max-count=1`)
    CURRENT_TAG=$(cat "$APP_DIR/version.txt")
fi
if [ -z "$LATEST_TAG" ]; then
    LATEST_TAG=$(git ls-remote --refs --tags "$REPO_URL" | cut -d/ -f3 | sort -V | tail -n1)
fi

log_message "Current version: $CURRENT_TAG"
log_message "Latest version:  $LATEST_TAG"

# Update process
# Validate and compare versions
compare_versions "$CURRENT_TAG" "$LATEST_TAG"
result=$?

if [ $result -eq 0 ]; then
    log_message "Current version $CURRENT_TAG is the same as the latest version. No update required."
    exit 0
elif [ $result -eq 2 ]; then
    log_message "New version detected: $LATEST_TAG. Starting update process..."
    # Proceed with update
else
    log_message "Current version $CURRENT_TAG is up-to-date or newer. No update required."
    exit 0
fi


cd "$APP_DIR" || exit

# Prepare for update: back up the current tarball
if [ -f "$LATEST_TARBALL" ]; then
    # Use CURRENT_TAG to name the backup of the current tarball
    PREVIOUS_TARBALL="$TARBALL_DIR/$APP_NAME-$CURRENT_TAG.tar.gz"

    # Only proceed with the backup if PREVIOUS_TARBALL does not already exist
    if [ ! -f "$PREVIOUS_TARBALL" ]; then
        mv "$LATEST_TARBALL" "$PREVIOUS_TARBALL"
        log_message "Backing up current tarball $LATEST_TARBALL to $PREVIOUS_TARBALL"
    else
        log_message "Backup for current tarball already exists, skipping backup."
    fi
fi


# Download the new tarball
# Extract the owner and repository name from the URL, removing the optional .git suffix
REPO_OWNER=$(echo "$REPO_URL" | sed -n 's#.*/\([^/]*\)/\([^/]*\)\(\.git\)*$#\1#p')
REPO_NAME=$(echo "$REPO_URL" | sed -n 's#.*/\([^/]*\)/\([^/]*\)\(\.git\)*$#\2#p')
release_info=$(curl -s "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/tags/$LATEST_TAG")
download_url=$(echo "$release_info" | jq -r '.assets[]? | select(.name == "langiot-package.tar.gz") | .browser_download_url')

# Check if the download URL is valid
if [ -z "$download_url" ] || [ "$download_url" == "null" ]; then
    log_message "Error: No valid download URL found for the latest release."
    exit 1
fi

wget -O "$LATEST_TARBALL" "$download_url"


# Change to the parent directory of $APP_DIR
cd "$(dirname "$APP_DIR")" || exit

# Extract the new tarball, overwriting existing files
tar -xzvf "$LATEST_TARBALL" -C "$(basename "$APP_DIR")" || { log_message "Extraction failed"; exit 1; }

# Restart and check the service
if restart_service; then
    log_message "Update to version $LATEST_TAG completed successfully. Service is running."
else
    rollback_service
fi

# Cleanup old tarballs after the update or rollback
cleanup_old_tarballs
