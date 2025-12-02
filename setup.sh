#!/bin/bash
set -e

cd /opt/ntms-kv-blob-queue

sudo apt update -y
sudo apt install -y python3 python3-pip python3-venv

# Create venv if missing
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

source venv/bin/activate

# Install packages
pip install --upgrade pip
pip install Flask azure-storage-blob azure-storage-queue Pillow azure-identity azure-keyvault-secrets

# Create folders
mkdir -p logs templates

# Restart worker
pkill -f worker.py || true
nohup python3 worker.py > logs/worker.log 2>&1 &

# Restart app
pkill -f app.py || true
nohup python3 app.py > logs/app.log 2>&1 &

echo "Setup completed."
