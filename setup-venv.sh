#!/bin/bash
# Setup script for consolidated virtual environment

echo "🔧 Setting up consolidated virtual environment for bot-team"
echo "=========================================================="
echo ""

# Navigate to project root
cd "$(dirname "$0")"

# Create virtual environment at root if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment at project root..."
    python -m venv .venv
    echo "✅ Virtual environment created"
else
    echo "ℹ️  Virtual environment already exists at project root"
fi

echo ""
echo "📥 Installing dependencies..."
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null

pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "To activate the virtual environment:"
echo "  Linux/Mac:  source .venv/bin/activate"
echo "  Windows:    .venv\\Scripts\\activate"
echo ""
echo "To clean up old bot-level venvs (optional):"
echo "  rm -rf chester/.venv dorothy/.venv sally/.venv"
echo "  rm -rf fred/.venv iris/.venv peter/.venv pam/.venv"
echo "  rm -rf quinn/.venv zac/.venv olive/.venv oscar/.venv rita/.venv sadie/.venv"
echo ""
