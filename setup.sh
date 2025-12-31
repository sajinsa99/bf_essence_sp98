#!/bin/bash
# Quick setup script for bf_essence_sp98

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔧 Setting up Essence SP98 Price Tracker..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3."
    exit 1
fi
echo "✓ Python 3 found: $(python3 --version)"

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 not found. Please install pip3."
    exit 1
fi
echo "✓ pip3 found"

# Install dependencies
echo ""
echo "📦 Installing Python dependencies..."
cd "$SCRIPT_DIR"
pip3 install -r requirements.txt

# Check for ChromeDriver
echo ""
echo "🌐 Checking for ChromeDriver..."
if command -v chromedriver &> /dev/null; then
    echo "✓ ChromeDriver found: $(chromedriver --version 2>/dev/null | head -1)"
else
    echo "⚠️  ChromeDriver not found. Install with:"
    echo "   brew install chromedriver"
    echo ""
    echo "Without ChromeDriver, price fetching will use demo data."
fi

# Make scripts executable
echo ""
echo "🔐 Making scripts executable..."
chmod +x "$SCRIPT_DIR/bf_essence_sp98.sh"
chmod +x "$SCRIPT_DIR/essence_tracker.py"
echo "✓ Scripts made executable"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Start the server: ./bf_essence_sp98.sh start"
echo "  2. Fetch prices: ./bf_essence_sp98.sh fetch"
echo "  3. View dashboard: http://localhost:9000"
echo ""
echo "For help: ./bf_essence_sp98.sh"
