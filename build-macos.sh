#!/usr/bin/env bash
set -euo pipefail

echo "============================================"
echo " LoudScan - macOS Build"
echo "============================================"
echo

# Locate Python 3
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "ERROR: Python 3 not found."
    echo "Install from https://www.python.org/downloads/mac-osx/"
    echo "  or:  brew install python"
    exit 1
fi

PYTHON_VERSION=$($PYTHON --version 2>&1)
echo "Using: $PYTHON_VERSION"
echo

echo "[1/3] Installing build dependencies..."
$PYTHON -m pip install -r requirements-dev.txt --quiet

echo "[2/3] Building executable..."
$PYTHON -m PyInstaller \
    --clean \
    --noconfirm \
    --distpath builds/macos \
    --workpath .build_tmp \
    loudscan.spec

echo "[3/3] Cleaning up temporary files..."
rm -rf .build_tmp

echo
echo "============================================"
echo " Build complete!"
echo " Output: builds/macos/LoudScan-macos"
echo "============================================"
echo
echo "NOTE: macOS Gatekeeper will block unsigned binaries."
echo "First-run workaround for your users:"
echo "  Right-click the file > Open > Open anyway"
echo "  (only required once)"
echo
echo "Upload builds/macos/LoudScan-macos to your GitHub Release."
