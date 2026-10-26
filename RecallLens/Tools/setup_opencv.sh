#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
VENDOR_DIR="$ROOT_DIR/Vendor/OpenCV"
ARCHIVE="$VENDOR_DIR/opencv-5.0.0-ios-framework.zip"
FRAMEWORK="$VENDOR_DIR/opencv2.framework"
URL="https://github.com/opencv/opencv/releases/download/5.0.0/opencv-5.0.0-ios-framework.zip"

if [ -d "$FRAMEWORK" ]; then
  echo "OpenCV 5.0.0 is already installed."
  exit 0
fi

mkdir -p "$VENDOR_DIR"
curl --fail --location "$URL" --output "$ARCHIVE"
unzip -q -o "$ARCHIVE" -d "$VENDOR_DIR"
echo "Installed OpenCV 5.0.0 at $FRAMEWORK"
