#!/usr/bin/env bash
set -euo pipefail

echo "============================================"
echo " LoudScan - macOS Build"
echo "============================================"
echo

# ── Versioning (stored in version#) ─────────────────────────────────────────
VERSION_OK=1
CURRENT_VERSION=""
NEXT_VERSION=""

if [[ ! -f "version#" ]]; then
    echo "ERROR: version# not found. Building without version suffix."
    VERSION_OK=0
else
    CURRENT_VERSION=$(tr -d '\r\n' < "version#" | xargs)
    IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

    if [[ -z "${MAJOR:-}" || -z "${MINOR:-}" || -z "${PATCH:-}" ]]; then
        echo "ERROR: Invalid version in version#: '$CURRENT_VERSION'. Building without version suffix."
        VERSION_OK=0
    elif ! [[ "$MAJOR" =~ ^[0-9]+$ && "$MINOR" =~ ^[0-9]+$ && "$PATCH" =~ ^[0-9]+$ ]]; then
        echo "ERROR: Non-numeric version in version#: '$CURRENT_VERSION'. Building without version suffix."
        VERSION_OK=0
    else
        NEXT_VERSION="$MAJOR.$MINOR.$((PATCH + 1))"
        echo "Current version: $CURRENT_VERSION"
        echo "Next version   : $NEXT_VERSION"
        echo
    fi
fi

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
if [[ "$VERSION_OK" == "1" ]]; then
    export LOUDSCAN_VERSION="$NEXT_VERSION"
else
    unset LOUDSCAN_VERSION
fi
PyInstaller \
    --clean \
    --noconfirm \
    --distpath builds/macos \
    --workpath .build_tmp \
    loudscan.spec

# Persist version bump only after a successful build
if [[ "$VERSION_OK" == "1" ]]; then
    printf '%s\n' "$NEXT_VERSION" > "version#"
fi

echo "[4/4] Cleaning up..."
deactivate
rm -rf .build_tmp "$VENV_DIR"

echo
echo "============================================"
echo " Build complete!"
if [[ "$VERSION_OK" == "1" ]]; then
    echo " Output: builds/macos/LoudScan-macos-$NEXT_VERSION"
else
    echo " Output: builds/macos/LoudScan-macos"
fi
echo "============================================"
echo
echo "NOTE: macOS Gatekeeper will block unsigned binaries."
echo "First-run workaround for your users:"
echo "  Right-click the file > Open > Open anyway"
echo "  (only required once)"
echo
if [[ "$VERSION_OK" == "1" ]]; then
    echo "Upload builds/macos/LoudScan-macos-$NEXT_VERSION to your GitHub Release."
else
    echo "Upload builds/macos/LoudScan-macos to your GitHub Release."
fi
