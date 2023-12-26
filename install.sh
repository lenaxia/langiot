#!/bin/bash

# Configuration Variables
USER="yin"
APP_NAME="langiot"
REPO_URL="https://github.com/lenaxia/langiot.git"
APP_DIR="/home/$USER/$APP_NAME"
CONFIG_DIR="/etc/$APP_NAME"
LOG_FILE="/home/$USER/$APP_NAME-install.log"
SERVICE_FILE="/etc/systemd/system/$APP_NAME.service"

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

# Install pyenv for Python version management
log_message "Installing pyenv..."
curl https://pyenv.run | bash
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
if [ $? -ne 0 ]; then
    log_message "Failed to install pyenv."
    exit 1
fi

# Check Python version and install new version if needed
PYTHON_REQUIRED="3.9.0"
pyenv install -s $PYTHON_REQUIRED
pyenv global $PYTHON_REQUIRED
if [ $? -ne 0 ]; then
    log_message "Failed to install Python $PYTHON_REQUIRED."
    exit 1
fi

# Reload shell
exec "$SHELL"


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

# Enable I2C
sudo sed -i 's/#dtparam=i2c_arm=on/dtparam=i2c_arm=on/' /boot/config.txt

# Enable I2S
sudo sed -i 's/#dtparam=i2s=on/dtparam=i2s=on/' /boot/config.txt

# Enable API
sudo sed -i 's/#dtparam=spi=on/dtparam=spi=on/' /boot/config.txt

# Set up HiFiBerry DAC (Max98357 compatible)
echo "dtoverlay=hifiberry-dac" | sudo tee -a /boot/config.txt

# Disable onboard audio (to avoid conflicts)
sudo sed -i 's/dtparam=audio=on/#dtparam=audio=on/' /boot/config.txt

if [ $? -ne 0 ]; then
    log_message "Failed to configure Raspberry Pi settings."
    exit 1
fi


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

