#!/bin/bash
# Release script for Monica Chrome Extension

set -e

EXTENSION_DIR="monica-chrome-extension"
VERSION=$(grep '"version"' $EXTENSION_DIR/manifest.json | cut -d'"' -f4)

echo "🚀 Building Monica Store Monitor v$VERSION"
echo "=========================================="

# Check we're in the right directory
if [ ! -d "$EXTENSION_DIR" ]; then
    echo "❌ Error: Run this from bot-team/ directory"
    exit 1
fi

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo "⚠️  Warning: You have uncommitted changes"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create ZIP package
ZIP_NAME="monica-monitor-v${VERSION}.zip"

echo "📦 Creating package: $ZIP_NAME"
zip -r "$ZIP_NAME" "$EXTENSION_DIR" \
    -x "$EXTENSION_DIR/*.py" \
    -x "$EXTENSION_DIR/.git/*" \
    -x "$EXTENSION_DIR/.DS_Store" \
    -q

echo "✅ Package created: $ZIP_NAME"
echo ""
echo "Next steps:"
echo "1. Go to https://chrome.google.com/webstore/devconsole"
echo "2. Click on Monica Store Monitor"
echo "3. Upload $ZIP_NAME"
echo "4. Submit for review"
echo ""
echo "Current version: $VERSION"
