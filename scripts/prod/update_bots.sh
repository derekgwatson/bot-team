#!/bin/bash
# Update bots after git pull
# This script should be run as www-data user after running merge_latest_claude.sh

set -e

REPO_PATH="/var/www/bot-team"
CHESTER_CONFIG="$REPO_PATH/chester/config.yaml"

# ==== Colours ====
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
warning() { echo -e "${YELLOW}[WARNING]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }

header() {
    echo ""
    echo -e "${BLUE}== $* ==${NC}"
    echo ""
}

# --- Load bot list dynamically from Chester’s config.yaml ---
load_bots_from_yaml() {
    python3 - <<EOF
import yaml
import sys

path = "$CHESTER_CONFIG"
try:
    with open(path) as f:
        data = yaml.safe_load(f)

    bot_team = data.get("bot_team", {})
    for bot in bot_team.keys():
        print(bot)
except Exception as e:
    print(f"Error reading YAML: {e}", file=sys.stderr)
    sys.exit(1)
EOF
}

# If args provided → only update those bots
if [ "$#" -gt 0 ]; then
    BOTS=("$@")
else
    header "Loading bot list from Chester config.yaml"
    info "Config: $CHESTER_CONFIG"
    mapfile -t BOTS < <(load_bots_from_yaml)
    info "Bots detected: ${BOTS[*]}"
fi

header "Bot Team Update Script"

# Function to update a single bot
update_bot() {
    local bot=$1
    local bot_path="$REPO_PATH/$bot"

    echo "----------------------------------------"
    info "Updating $bot..."
    echo "----------------------------------------"

    # Check if bot directory exists
    if [ ! -d "$bot_path" ]; then
        warning "Directory $bot_path does not exist, skipping..."
        echo ""
        return
    fi

    # Check if requirements.txt exists
    if [ ! -f "$bot_path/requirements.txt" ]; then
        info "No requirements.txt for $bot, skipping pip install..."
    else
        info "Installing dependencies for $bot..."

        # Check if venv exists
        if [ ! -d "$bot_path/.venv" ]; then
            warning "Virtual environment not found at $bot_path/.venv"
            info "Creating virtual environment..."
            cd "$bot_path"
            python3 -m venv --without-pip .venv
            .venv/bin/python3 -m ensurepip --default-pip
        fi

        # Install/update requirements
        cd "$bot_path"
        .venv/bin/pip install -q -r requirements.txt
        success "Dependencies updated for $bot"
    fi

    # Restart gunicorn service
    local service_name="gunicorn-bot-team-$bot"
    info "Restarting $service_name..."

    if sudo systemctl restart "$service_name" 2>/dev/null; then
        success "$service_name restarted successfully"
    else
        warning "Could not restart $service_name (may not exist or not be enabled)"
    fi

    echo ""
}

# Update each bot
for bot in "${BOTS[@]}"; do
    update_bot "$bot"
done

header "Bot Update Summary"

echo "Service Status:"
echo "----------------------------------------"
failed_services=()

for bot in "${BOTS[@]}"; do
    service_name="gunicorn-bot-team-$bot"
    if systemctl is-active --quiet "$service_name" 2>/dev/null; then
        success "$service_name is running"
    else
        error "$service_name is NOT running"
        failed_services+=("$service_name")
    fi
done

# Show troubleshooting commands for failed services
if [ ${#failed_services[@]} -gt 0 ]; then
    header "Failed Services - Troubleshooting"

    echo "Run these commands to investigate:"
    echo ""

    for service_name in "${failed_services[@]}"; do
        echo "--- $service_name ---"
        echo "  Check status:"
        echo "    sudo systemctl status $service_name"
        echo ""
        echo "  View recent logs:"
        echo "    sudo journalctl -u $service_name -n 50"
        echo ""
        echo "  Follow logs (live tail):"
        echo "    sudo journalctl -u $service_name -f"
        echo ""
    done
else
    success "All services are running"
fi

echo ""
success "Update complete!"
echo ""
