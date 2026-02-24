#!/usr/bin/env bash
set -euo pipefail

echo "============================================"
echo " LoudScan - macOS Build"
echo "============================================"
echo

# ── Xcode Command Line Tools ──────────────────────────────────────────────────
if ! xcode-select -p &>/dev/null; then
    echo "ERROR: Xcode Command Line Tools not installed."
    echo "Run the following command, wait for the installation to complete,"
    echo "then re-run this script:"
    echo
    echo "  xcode-select --install"
    exit 1
fi

# The license must be accepted before clang (used by PyInstaller) can run.
# This only prompts for sudo the very first time.
if ! clang --version &>/dev/null 2>&1; then
    echo "Xcode license not yet accepted — accepting now (requires sudo)..."
    sudo xcodebuild -license accept
    echo "License accepted."
    echo
fi

# ── Python ────────────────────────────────────────────────────────────────────
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

# ── Build ─────────────────────────────────────────────────────────────────────
# Use an isolated venv so we never touch the system/Homebrew Python
VENV_DIR=".venv-build"

echo "[1/4] Creating isolated build environment..."
$PYTHON -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

echo "[2/4] Installing build dependencies..."
pip install -r requirements-dev.txt --quiet

echo "[3/4] Building executable..."
PyInstaller \
    --clean \
    --noconfirm \
    --distpath builds/macos \
    --workpath .build_tmp \
    loudscan.spec

echo "[4/4] Cleaning up..."
deactivate
rm -rf .build_tmp "$VENV_DIR"

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
