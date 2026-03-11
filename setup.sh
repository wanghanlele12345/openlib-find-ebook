#!/bin/bash

# Openlib Book Finder Setup Script
echo "[*] Starting setup for Openlib Book Finder..."

# 1. Create virtual environment
if [ ! -d "venv" ]; then
    echo "[*] Creating virtual environment..."
    python3 -m venv venv
else
    echo "[!] venv already exists, skipping creation."
fi

# 2. Install dependencies
echo "[*] Installing dependencies from requirements.txt..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# 3. Install Playwright browser
echo "[*] Installing Chromium for Playwright..."
./venv/bin/playwright install chromium

echo "[+] Setup complete! You can now use this extension in Gemini CLI."
