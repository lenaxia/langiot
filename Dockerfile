# Stage 1: Build the React application
FROM node:18 as react-build-stage

# Set working directory for the React app build
WORKDIR /app/web

# Copy package.json and package-lock.json for React app
COPY web/package*.json ./

# Install dependencies for React app
RUN npm install


# Copy the React app files into the image
COPY web/ .

# Build the React app
RUN npm run build

# Stage 2: Set up the Python Flask environment
FROM python:3.9-slim

# Set working directory in the container
WORKDIR /app

# Create a directory to hold the React app build
RUN mkdir -p /app/web

# Copy the build output from the React app build stage
COPY --from=react-build-stage /app/web/build /app/web

# Copy the Flask app files into the image
COPY backend /app

# create config directory
RUN mkdir /config
COPY backend/config.ini /config

# Set environment variables for runtime
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV FLASK_APP=langiot
ENV FLASK_ENV=production

# Set default values for PUID and PGID
ARG PUID=1000
ARG PGID=1000

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc libglib2.0-0

# Add a non-root user and switch to it
RUN groupadd -r appuser -g ${PGID} && useradd -r -g appuser -u ${PUID} appuser

# Create and set ownership of necessary directories
RUN mkdir -p /home/appuser && chown -R appuser:appuser /home/appuser
RUN chown -R appuser:appuser /app
RUN chown -R appuser:appuser /config

# Install any needed packages specified in requirements.txt as root
# This ensures global installation
USER root
RUN pip3 install --no-cache-dir -r requirements.txt

# Switch back to non-root user for security
USER appuser

# Make port 80 available to the world outside this container
EXPOSE 80

# Run app.py when the container launches
CMD ["flask", "run", "--host=0.0.0.0", "--port=80"]
