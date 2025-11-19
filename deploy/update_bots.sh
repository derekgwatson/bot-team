#!/bin/bash
# Update all bots after git pull
# This script should be run as www-data user after running merge_latest_claude.sh
# Usage: sudo su -s /bin/bash -c '/usr/local/bin/update_bots.sh' www-data

set -e  # Exit on error

REPO_PATH="/var/www/bot-team"
VENV_PATH="$REPO_PATH/.venv"
REQUIREMENTS_FILE="$REPO_PATH/requirements.txt"
BOTS=("chester" "dorothy" "fred" "iris" "pam" "peter" "quinn" "sadie" "sally" "zac" "oscar" "olive" "rita")

echo "=========================================="
echo "Bot Team Update Script"
echo "=========================================="
echo ""

# ==========================================
# Step 1: Setup Root Virtual Environment
# ==========================================
echo "----------------------------------------"
echo "Setting up root virtual environment..."
echo "----------------------------------------"

if [ ! -d "$VENV_PATH" ]; then
    echo "⚠️  Virtual environment not found at $VENV_PATH"
    echo "   Creating virtual environment..."
    cd "$REPO_PATH"
    python3 -m venv .venv
    echo "✓ Virtual environment created"
fi

# Ensure correct ownership (www-data since gunicorn runs as www-data)
echo "🔧 Setting ownership to www-data:www-data..."
sudo chown -R www-data:www-data "$VENV_PATH"
echo "✓ Ownership set"

# ==========================================
# Step 2: Install/Update Dependencies
# ==========================================
echo ""
echo "----------------------------------------"
echo "Installing dependencies..."
echo "----------------------------------------"

if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "⚠️  Warning: $REQUIREMENTS_FILE not found!"
    echo "   Skipping dependency installation..."
else
    echo "📦 Installing from $REQUIREMENTS_FILE..."
    cd "$REPO_PATH"

    # Install as www-data user using the full path to pip
    sudo -u www-data "$VENV_PATH/bin/pip" install -q -r "$REQUIREMENTS_FILE"

    echo "✓ All dependencies installed"
fi

# ==========================================
# Step 3: Restart Bot Services
# ==========================================
echo ""
echo "----------------------------------------"
echo "Restarting bot services..."
echo "----------------------------------------"
echo ""

for bot in "${BOTS[@]}"; do
    service_name="gunicorn-bot-team-$bot"
    bot_path="$REPO_PATH/$bot"

    # Check if bot directory exists
    if [ ! -d "$bot_path" ]; then
        echo "⚠️  Warning: $bot_path does not exist, skipping $bot..."
        continue
    fi

    echo "🔄 Restarting $service_name..."

    if sudo systemctl restart "$service_name" 2>/dev/null; then
        echo "✓ $service_name restarted successfully"
    else
        echo "⚠️  Warning: Could not restart $service_name (may not exist or not be enabled)"
    fi

    echo ""
done

echo "=========================================="
echo "✓ All bots updated!"
echo "=========================================="
echo ""

# ==========================================
# Step 4: Service Status Check
# ==========================================
echo "Service Status:"
echo "----------------------------------------"
failed_services=()

for bot in "${BOTS[@]}"; do
    service_name="gunicorn-bot-team-$bot"
    if systemctl is-active --quiet "$service_name" 2>/dev/null; then
        echo "  ✓ $service_name is running"
    else
        echo "  ✗ $service_name is not running"
        failed_services+=("$service_name")
    fi
done

# Show troubleshooting commands for failed services
if [ ${#failed_services[@]} -gt 0 ]; then
    echo ""
    echo "=========================================="
    echo "⚠️  Failed Services - Troubleshooting"
    echo "=========================================="
    echo ""
    echo "Run these commands to investigate:"
    echo ""

    for service_name in "${failed_services[@]}"; do
        echo "--- $service_name ---"
        echo "  Check status:"
        echo "    sudo systemctl status $service_name"
        echo ""
        echo "  View recent logs:"
        echo "    sudo journalctl -u $service_name -n 50 --no-pager"
        echo ""
        echo "  Follow logs (live tail):"
        echo "    sudo journalctl -u $service_name -f"
        echo ""
    done

    echo "=========================================="
fi

echo ""
echo "✓ Update complete!"
echo ""
