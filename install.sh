#!/bin/bash

# Configuration Variables
APP_NAME="langiot"
REPO_URL="https://github.com/lenaxia/langiot.git"
APP_DIR="$HOME/$APP_NAME"
TARBALLS="$HOME/langiot-tarballs"
CONFIG_DIR="$HOME"
CONFIG_FILE="$APP_NAME.conf"
LOG_FILE="$HOME/$APP_NAME-install.log"
SERVICE_FILE="/etc/systemd/system/$APP_NAME.service"
AVAHISERVICEFILE="/etc/avahi/services/$APP_NAME.service"
PORT=8080
S3_URL="https://s3.amazonaws.com/mybucket/myicon.png"
DESCRIPTION="This is the web frontend to manage the LangClient"
ADHOC_MANAGER="adhoc-network-manager"
ADHOC_SCRIPT_PATH="$HOME/$APP_NAME/adhoc_network_manager.py"
ADHOC_SERVICE_FILE="/etc/systemd/system/$ADHOC_MANAGER.service"
ADHOC_CONFIG_SCRIPT_PATH="$HOME/$APP_NAME/configure_adhoc_network.py"

# Function to log messages
log_message() {
    echo "$(date): $1" | tee -a "$LOG_FILE"
}

log_message "Starting installation script..."

# Ensure the log file exists
touch "$LOG_FILE"
sudo mkdir /home/$USER/.xdg
sudo chown $USER:$USER /home/$USER/.xdg

if ! grep -q "export PATH=\"\$PATH:/home/yin/.local/bin\"" /home/yin/.bashrc; then
     echo 'export PATH="$PATH:/home/yin/.local/bin"' >> /home/yin/.bashrc
fi

# Update and install dependencies
log_message "Updating system and installing dependencies..."
sudo apt-get remove nodejs-legacy
sudo apt-get update && sudo apt-get install -y jq git gcc libglib2.0-0 make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev python3-dbus dbus python3-networkmanager
sudo apt-get install -y libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev libportmidi-dev libjpeg-dev python3-dev libasound2-dev ffmpeg python3-pip pipx

# Install Piper TTS using pipx
pipx install piper-tts
PIPER_MODEL_NAME="en_US-lessac-medium"
PIPER_DOWNLOAD_DIR="$HOME/.piper/downloads"
mkdir -p "$PIPER_DOWNLOAD_DIR"
piper-tts download "$PIPER_MODEL_NAME" "$PIPER_DOWNLOAD_DIR"
curl -sL https://deb.nodesource.com/setup_18.x | sudo -E bash -  # Adjust "setup_18.x" as needed for your preferred version
sudo apt-get install -y nodejs
if [ $? -ne 0 ]; then
    log_message "Failed to install required packages."
    exit 1
fi

# Check if Node.js version 18 or higher is already installed
NODE_VERSION=$(node --version 2>/dev/null | cut -d "v" -f 2)
NODE_REQUIRED="18"

if [[ $? -eq 0 && "${NODE_VERSION%%.*}" -ge "$NODE_REQUIRED" ]]; then
    log_message "Node.js version $NODE_VERSION is already installed and meets the required version."
else
    # Install Node.js
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt-get install -y nodejs

    # Update the NODE_VERSION variable after installation
    NODE_VERSION=$(node --version | cut -d "v" -f 2)
    log_message "Node.js version $NODE_VERSION has been installed, or is already installed."
fi

# Remove unused packages
sudo apt autoremove -y

log_message "Configuring Raspberry Pi settings for I2C, I2S, SPI and HiFiBerry DAC audio..."

# Backup the original config.txt file
sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.bak

# Enable I2C, I2S and SPI, and HiFiBerry DAC
sudo sed -i 's/#dtparam=i2c_arm=on/dtparam=i2c_arm=on/' /boot/firmware/config.txt
sudo sed -i 's/#dtparam=i2s=on/dtparam=i2s=on/' /boot/firmware/config.txt
sudo sed -i 's/#dtparam=spi=on/dtparam=spi=on/' /boot/firmware/config.txt
if ! grep -q "^dtoverlay=hifiberry-dac$" /boot/firmware/config.txt; then
    echo "dtoverlay=hifiberry-dac" | sudo tee -a /boot/firmware/config.txt
fi

# Disable onboard audio (to avoid conflicts)
sudo sed -i 's/^dtparam=audio=on/#dtparam=audio=on/' /boot/firmware/config.txt

if [ $? -ne 0 ]; then
    log_message "Failed to configure Raspberry Pi settings."
    exit 1
fi

log_message "Installing and configuring Avahi for mDNS..."

# Before installing Avahi daemon, check if it's already installed
if ! dpkg -l | grep -qw avahi-daemon; then
    log_message "Installing Avahi daemon..."
    sudo apt-get install -y avahi-daemon
    if [ $? -ne 0 ]; then
        log_message "Failed to install Avahi daemon."
        exit 1
    fi
else
    log_message "Avahi daemon already installed."
fi

# Create and configure Avahi service file
sudo tee "$AVAHISERVICEFILE" > /dev/null << EOF
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">%h - My Custom Service</name>
  <service>
    <type>_$APP_NAME._tcp</type>
    <port>$PORT</port>
    <txt-record>appname=$APP_NAME</txt-record>
    <txt-record>description=$DESCRIPTION</txt-record>
    <txt-record>icon_url=$S3_URL</txt-record>
  </service>
</service-group>
EOF

if [ $? -ne 0 ]; then
    log_message "Failed to create Avahi service file."
    exit 1
fi

# Restart Avahi daemon to apply changes
sudo systemctl restart avahi-daemon
if [ $? -ne 0 ]; then
    log_message "Failed to restart Avahi daemon."
    exit 1
fi

log_message "Avahi mDNS configuration complete."

# Configure WiFi settings 
echo "Configuring Wifi Settings. If not previously set up, please run this script as sudo"
# Check if 'wificonfig' group exists
if ! getent group wificonfig > /dev/null; then
    sudo groupadd wificonfig
    echo "Group 'wificonfig' created"
fi
# Check if user is in 'wificonfig' group
if ! id -nG "$USER" | grep -qw wificonfig; then
    sudo usermod -a -G wificonfig "$USER"
    echo "User '$USER' added to 'wificonfig' group"
fi
# Check the group owner of wpa_supplicant.conf
if [ "$(stat -c %G /etc/wpa_supplicant/wpa_supplicant.conf)" != "wificonfig" ]; then
    sudo chgrp wificonfig /etc/wpa_supplicant/wpa_supplicant.conf
    echo "Group owner of wpa_supplicant.conf changed to 'wificonfig'"
fi
# Check the permissions of wpa_supplicant.conf
if [ "$(stat -c %a /etc/wpa_supplicant/wpa_supplicant.conf)" != "640" ]; then
    sudo chmod 640 /etc/wpa_supplicant/wpa_supplicant.conf
    echo "Permissions of wpa_supplicant.conf set to 640"
fi

# Set up a cron job for weekly updates
# We want this to be smart enough to not add duplicate contab entries
log_message "Setting up a weekly cron job for repository updates..."

# Define the cron job command
CRON_JOB_COMMAND="cd $APP_DIR && bash update.sh > /dev/null 2>&1"

# Export existing crontab to a temporary file
TEMP_CRONTAB=$(mktemp)
crontab -l > "$TEMP_CRONTAB" 2>/dev/null

# Check if a similar cron job already exists
if grep -Fq "$CRON_JOB_COMMAND" "$TEMP_CRONTAB"; then
    log_message "A similar cron job for weekly updates already exists. No changes made."
else
    # Add the new cron job if it doesn't exist
    echo "0 2 * * 1 $CRON_JOB_COMMAND" >> "$TEMP_CRONTAB"
    crontab "$TEMP_CRONTAB"
    if [ $? -ne 0 ]; then
        log_message "Failed to set up the cron job."
        rm "$TEMP_CRONTAB"
        exit 1
    fi
    log_message "Cron job for weekly updates set up successfully."
fi
# Clean up
rm "$TEMP_CRONTAB"

# make the app folder
mkdir -p $TARBALLS
cd $APP_DIR

# Get the latest release assets JSON from GitHub API
assets_url=$(curl -s https://api.github.com/repos/lenaxia/langiot/releases/latest | jq -r '.assets_url')
# Fetch the browser_download_url for the specific asset (langiot-package.tar.gz)
download_url=$(curl -s "${assets_url}" | jq -r '.[] | select(.name == "langiot-package.tar.gz") | .browser_download_url')
# Use wget to download the tar.gz file
wget -O $TARBALLS/langiot-latest.tar.gz "${download_url}"

cd $APP_DIR

tar -xzvf $TARBALLS/langiot-latest.tar.gz

# Setup Python Virtual Environment
log_message "Setting up Python Virtual Environment..."

# Check if Python virtual environment already exists
if [ -d "$APP_DIR/backend/venv" ]; then
    log_message "Python virtual environment already exists. Skipping creation."
else
    log_message "Setting up Python Virtual Environment..."
    python3 -m venv --system-site-packages "$APP_DIR/backend/venv"
fi

cd "$APP_DIR/backend"
source $APP_DIR/backend/venv/bin/activate
pip3 install --no-cache-dir -r "$APP_DIR/backend/requirements.txt" && pip3 install RPi.GPIO || {
    log_message "Failed to install Python dependencies."
    exit 1
}

# Deactivate virtual environment
deactivate

# Create config directory and copy config file if it doesn't exist
log_message "Setting up configuration..."
sudo mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG_DIR/$CONFIG_FILE" ]; then
    sudo cp "$APP_DIR/backend/config.ini" "$CONFIG_DIR/$CONFIG_FILE"
    sudo chown $USER:$USER "$CONFIG_DIR/$CONFIG_FILE"
    chmod 644 "$CONFIG_DIR/$CONFIG_FILE"

    if [ $? -ne 0 ]; then
        log_message "Failed to set up configuration."
        exit 1
    fi
else
    log_message "Configuration file already exists. Skipping copy."
fi


# Create a systemd service for Flask app using Gunicorn
log_message "Creating systemd service for Gunicorn..."
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=Gunicorn instance to serve Flask Application
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR/backend
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONUNBUFFERED=1
Environment="XDG_RUNTIME_DIR=/home/$USER/.xdg"
Environment="WEB_APP_PATH=$APP_DIR/backend/web"
Environment="CONFIG_FILE_PATH=$CONFIG_DIR/$CONFIG_FILE"
ExecStart=$APP_DIR/backend/venv/bin/gunicorn --workers 1 --bind 0.0.0.0:8080 'langiot:app'
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

if [ $? -ne 0 ]; then
    log_message "Failed to create systemd service."
    exit 1
fi

# Enable and start the service
log_message "Enabling and starting the service..."
sudo systemctl enable $APP_NAME.service && sudo systemctl start $APP_NAME.service
if [ $? -ne 0 ]; then
    log_message "Failed to enable or start the service."
    exit 1
fi

log_message "Creating asound.conf config file for HifiBerry DAC..."
sudo tee "/etc/asound.conf" > /dev/null << EOF
pcm.!default {
    type plug
    slave {
        pcm "hw:0,0"
    }
}

ctl.!default {
    type hw
    card 0
}
EOF

if [ $? -ne 0 ]; then
    log_message "Failed to create ~/.asoundrc config file."
    exit 1
fi


# Set up a cron job for running the adhoc network setup script on reboot
log_message "Setting up a cron job for running the adhoc network setup script on reboot..."

# Define the cron job command
CRON_JOB_COMMAND="@reboot /usr/bin/python3 $APP_DIR/backend/adhoc_network_manager.py"

# Export existing crontab to a temporary file
TEMP_CRONTAB=$(mktemp)
crontab -l > "$TEMP_CRONTAB" 2>/dev/null

# Check if a similar cron job already exists
if grep -Fq "$CRON_JOB_COMMAND" "$TEMP_CRONTAB"; then
    log_message "A similar cron job for running the adhoc network setup script on reboot already exists. No changes made."
else
    # Add the new cron job if it doesn't exist
    echo "$CRON_JOB_COMMAND" >> "$TEMP_CRONTAB"
    crontab "$TEMP_CRONTAB"
    if [ $? -ne 0 ]; then
        log_message "Failed to set up the cron job."
        rm "$TEMP_CRONTAB"
        exit 1
    fi
    log_message "Cron job for running the adhoc network setup script on reboot set up successfully."
fi
# Clean up
rm "$TEMP_CRONTAB"

log_message "Installation of $APP_NAME completed successfully."

# Reboot to apply changes
log_message "Rebooting to apply changes..."
sudo reboot

