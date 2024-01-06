#!/bin/bash

# Configuration Variables
USER="yin"
APP_NAME="langiot"
REPO_URL="https://github.com/lenaxia/langiot.git"
APP_DIR="/home/$USER/$APP_NAME"
CONFIG_DIR="/etc/$APP_NAME"
LOG_FILE="/home/$USER/$APP_NAME-install.log"
SERVICE_FILE="/etc/systemd/system/$APP_NAME.service"
AVAHISERVICEFILE="/etc/avahi/services/$APP_NAME.service"
PORT=8080
S3_URL="https://s3.amazonaws.com/mybucket/myicon.png"
DESCRIPTION="This is the web frontend to manage the LangClient"


# Function to log messages
log_message() {
    echo "$(date): $1" | tee -a "$LOG_FILE"
}

log_message "Starting installation script..."

# Ensure the log file exists
touch "$LOG_FILE"
sudo mkdir /home/$USER/.xdg
sudo chown $USER:$USER /home/$USER/.xdg

# Check if pyenv is already installed
if [ -d "$HOME/.pyenv" ]; then
    log_message "WARNING: '/home/yin/.pyenv' directory already exists. Removing it to proceed with the installation."
    rm -rf "$HOME/.pyenv"
    if [ $? -ne 0 ]; then
        log_message "Failed to remove existing '.pyenv' directory. Please remove it manually and re-run the script."
        exit 1
    fi
fi

# Update and install dependencies
log_message "Updating system and installing dependencies..."
sudo apt-get update && sudo apt-get install -y git nodejs npm gcc libglib2.0-0 make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
sudo apt-get install -y libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev libportmidi-dev libjpeg-dev python3-dev
if [ $? -ne 0 ]; then
    log_message "Failed to install required packages."
    exit 1
fi

# Check if pyenv is installed and functional
if command -v pyenv >/dev/null; then
    log_message "pyenv is already installed."
else
    log_message "Installing pyenv..."
    curl https://pyenv.run | bash

    # Update PATH and initialize pyenv in the current script session
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init --path)"
    eval "$(pyenv init -)"
fi

# Check Python version and install new version if needed
PYTHON_REQUIRED="3.9.0"
if pyenv versions | grep -q "$PYTHON_REQUIRED"; then
    log_message "Python $PYTHON_REQUIRED is already installed."
else
    log_message "Installing Python $PYTHON_REQUIRED..."
    pyenv install $PYTHON_REQUIRED
    if [ $? -ne 0 ]; then
        log_message "Failed to install Python $PYTHON_REQUIRED."
        exit 1
    fi
fi

pyenv global $PYTHON_REQUIRED


# Check Node.js version
NODE_VERSION=$(node --version | cut -d "v" -f 2)
NODE_REQUIRED="18"
if [[ "${NODE_VERSION%%.*}" -lt "$NODE_REQUIRED" ]]; then
    log_message "Node.js version $NODE_VERSION is not sufficient. Required version is $NODE_REQUIRED or higher."
    exit 1
fi

log_message "Configuring Raspberry Pi settings for I2C, I2S, SPI and HiFiBerry DAC audio..."

# Backup the original config.txt file
sudo cp /boot/config.txt /boot/config.txt.bak

# Enable I2C, I2S and SPI, and HiFiBerry DAC
sudo sed -i 's/#dtparam=i2c_arm=on/dtparam=i2c_arm=on/' /boot/config.txt
sudo sed -i 's/#dtparam=i2s=on/dtparam=i2s=on/' /boot/config.txt
sudo sed -i 's/#dtparam=spi=on/dtparam=spi=on/' /boot/config.txt
echo "dtoverlay=hifiberry-dac" | sudo tee -a /boot/config.txt

# Disable onboard audio (to avoid conflicts)
sudo sed -i 's/dtparam=audio=on/#dtparam=audio=on/' /boot/config.txt

if [ $? -ne 0 ]; then
    log_message "Failed to configure Raspberry Pi settings."
    exit 1
fi

log_message "Installing and configuring Avahi for mDNS..."

# Install Avahi daemon
sudo apt-get install -y avahi-daemon
if [ $? -ne 0 ]; then
    log_message "Failed to install Avahi daemon."
    exit 1
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


# Clone the repository
log_message "Cloning repository..."
if [ -d "$APP_DIR" ]; then
    if [ -d "$APP_DIR/.git" ]; then
        log_message "Directory already exists and is a git repository. Pulling latest changes..."
        git -C "$APP_DIR" pull 2>&1 | tee -a "$LOG_FILE"
    else
        log_message "Directory already exists but is not a git repository. Removing and recloning..."
        rm -rf "$APP_DIR"
        git clone "$REPO_URL" "$APP_DIR" 2>&1 | tee -a "$LOG_FILE"
    fi
else
    git clone "$REPO_URL" "$APP_DIR" 2>&1 | tee -a "$LOG_FILE"
fi

if [ $? -ne 0 ]; then
    log_message "Failed to clone the repository."
    exit 1
fi

# Set up a cron job for weekly updates
# We want this to be smart enough to not add duplicate contab entries
log_message "Setting up a weekly cron job for repository updates..."

# Define the cron job command
CRON_JOB_COMMAND="cd $APP_DIR && git pull && bash install.sh > /dev/null 2>&1"

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

# Build the React application
log_message "Building React application..."
cd "$APP_DIR/web" && npm install && npm run build 2>&1 | tee -a "$LOG_FILE"
if [ $? -ne 0 ]; then
    log_message "Failed to build the React application."
    exit 1
fi

# Move to backend directory
cd "$APP_DIR/backend"
mkdir -p "$APP_DIR/backend/web"
rm -rf "$APP_DIR/backend/web/"*
mv "$APP_DIR/web/build/"* "$APP_DIR/backend/web"

# Setup Python Virtual Environment
log_message "Setting up Python Virtual Environment..."
cd "$APP_DIR/backend"
python3 -m venv venv
source venv/bin/activate
pip3 install --no-cache-dir -r requirements.txt
if [ $? -ne 0 ]; then
    log_message "Failed to install Python dependencies."
    exit 1
fi

# Deactivate virtual environment
deactivate

# Create config directory and copy config file
log_message "Setting up configuration..."
sudo mkdir -p "$CONFIG_DIR" && sudo cp "$APP_DIR/backend/config.ini" "$CONFIG_DIR"
if [ $? -ne 0 ]; then
    log_message "Failed to set up configuration."
    exit 1
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
Environment="CONFIG_PATH=$CONFIG_DIR/config.ini"
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

log_message "Installation of $APP_NAME completed successfully."

# Reboot to apply changes
log_message "Rebooting to apply changes..."
sudo reboot

