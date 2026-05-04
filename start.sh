#!/bin/bash
# FreeCAD Text-to-3D - macOS setup and launch script

set -e

FREECAD_APP="${FREECAD_APP_DIR:-${FREECAD_HOME:-/Applications/FreeCAD.app}}"
TESTED_FREECAD_VERSION="1.1.1"

echo ""
echo "----------------------------------------------"
echo "  FreeCAD Text-to-3D - Setup & Launch"
echo "----------------------------------------------"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "[ERROR] python3 not found. Install it with Homebrew: brew install python3"
  exit 1
fi

echo "[OK] Python: $(python3 --version)"
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
  echo "[ERROR] Python 3.10 or newer is required."
  exit 1
fi

# Check FreeCAD
if [ -d "$FREECAD_APP" ]; then
  echo "[OK] FreeCAD detected: $FREECAD_APP"

  if command -v plutil &>/dev/null; then
    FREECAD_VERSION=$(plutil -extract CFBundleVersion raw "$FREECAD_APP/Contents/Info.plist" 2>/dev/null || true)
    if [ -n "$FREECAD_VERSION" ]; then
      echo "[OK] FreeCAD version: $FREECAD_VERSION"
    fi
  fi

  echo "[INFO] Tested FreeCAD version: $TESTED_FREECAD_VERSION"
else
  echo "[WARN] FreeCAD not found."
  echo "       Download it from https://www.freecad.org"
  echo "       Continuing anyway so you can test without FreeCAD."
  echo "[INFO] Tested FreeCAD version: $TESTED_FREECAD_VERSION"
fi

# Create venv
if [ ! -d "venv" ]; then
  echo ""
  echo "-> Creating virtual environment..."
  python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install dependencies
echo "-> Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Check API key
if [ -z "$OPENAI_API_KEY" ]; then
  echo ""
  echo "[WARN] OPENAI_API_KEY environment variable is not set."
  echo "   Option 1: export OPENAI_API_KEY='sk-...'"
  echo "   Option 2: enter it from the web Settings panel"
  echo ""
fi

# Create output directory
mkdir -p ~/freecad_text_to_3d_output

echo ""
echo "----------------------------------------------"
echo "  Starting app -> http://127.0.0.1:5000"
echo "----------------------------------------------"
echo ""

python3 app.py
