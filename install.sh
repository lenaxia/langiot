#!/bin/bash

# Configuration Variables
YOUR_APP_NAME="langiot"
REPO_URL="https://github.com/yourusername/your-repo.git"
APP_DIR="/home/pi/$YOUR_APP_NAME"
CONFIG_DIR="/etc/$YOUR_APP_NAME"
LOG_FILE="/var/log/$YOUR_APP_NAME-install.log"
SERVICE_FILE="/etc/systemd/system/$YOUR_APP_NAME.service"

# Function to log messages
log_message() {
    echo "$(date): $1" | tee -a "$LOG_FILE"
}

# Update and install dependencies
log_message "Updating system and installing dependencies..."
sudo apt-get update && sudo apt-get install -y git python3 python3-pip nodejs npm gcc libglib2.0-0
if [ $? -ne 0 ]; then
    log_message "Failed to install required packages."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d " " -f 2)
PYTHON_REQUIRED="3.9"
if [[ "$PYTHON_VERSION" < "$PYTHON_REQUIRED" ]]; then
    log_message "Python version $PYTHON_VERSION is not sufficient. Required version is $PYTHON_REQUIRED or higher."
    exit 1
fi

# Check Node.js version
NODE_VERSION=$(node --version | cut -d "v" -f 2)
NODE_REQUIRED="18"
if [[ "${NODE_VERSION%%.*}" -lt "$NODE_REQUIRED" ]]; then
    log_message "Node.js version $NODE_VERSION is not sufficient. Required version is $NODE_REQUIRED or higher."
    exit 1
fi

# Clone the repository
log_message "Cloning repository..."
git clone "$REPO_URL" "$APP_DIR" 2>&1 | tee -a "$LOG_FILE"
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

# Install Python dependencies
log_message "Installing Python dependencies..."
pip3 install --no-cache-dir -r requirements.txt 2>&1 | tee -a "$LOG_FILE"
if [ $? -ne 0 ]; then
    log_message "Failed to install Python dependencies."
    exit 1
fi

# Create config directory and copy config file
log_message "Setting up configuration..."
sudo mkdir -p "$CONFIG_DIR" && sudo cp "$APP_DIR/backend/config.ini" "$CONFIG_DIR"
if [ $? -ne 0 ]; then
    log_message "Failed to set up configuration."
    exit 1
fi

# Create a systemd service for Flask app
log_message "Creating systemd service..."
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=Flask Application
After=network.target

[Service]
User=pi
WorkingDirectory=$APP_DIR/backend
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONUNBUFFERED=1
Environment=FLASK_APP=langiot
Environment=FLASK_ENV=production
ExecStart=/usr/bin/python3 -m flask run --host=0.0.0.0 --port=80

[Install]
WantedBy=multi-user.target
EOF

if [ $? -ne 0 ]; then
    log_message "Failed to create systemd service."
    exit 1
fi

# Enable and start the service
log_message "Enabling and starting the service..."
sudo systemctl enable $YOUR_APP_NAME.service && sudo systemctl start $YOUR_APP_NAME.service
if [ $? -ne 0 ]; then
    log_message "Failed to enable or start the service."
    exit 1
fi

log_message "Installation of $YOUR_APP_NAME completed successfully."