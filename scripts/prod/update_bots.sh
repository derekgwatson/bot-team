#!/bin/bash
# Update bots after git pull
# This script should be run as www-data user after running merge_latest_claude.sh

set -e

REPO_PATH="/var/www/bot-team"
CHESTER_CONFIG="$REPO_PATH/chester/config.yaml"
SHARED_REQUIREMENTS="$REPO_PATH/requirements.txt"
HEALTH_CHECK_TIMEOUT=5  # seconds to wait for health check

# ==== Colours ====
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
warning() { echo -e "${YELLOW}[WARNING]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }

header() {
    echo ""
    echo -e "${WHITE}== $* ==${NC}"
    echo ""
}

# --- Load bot list dynamically from Chester's config.yaml ---
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

# --- Get bot port from chester/config.yaml ---
get_bot_port() {
    local bot=$1
    python3 - <<EOF
import yaml
import sys

path = "$CHESTER_CONFIG"
bot_name = "$bot"
try:
    with open(path) as f:
        data = yaml.safe_load(f)
    bot_team = data.get("bot_team", {})
    bot_info = bot_team.get(bot_name, {})
    port = bot_info.get("port")
    if port:
        print(port)
    else:
        sys.exit(1)
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
EOF
}

# --- Check bot health endpoint via HTTP port ---
check_bot_health() {
    local bot=$1
    local port
    port=$(get_bot_port "$bot")

    if [ -z "$port" ]; then
        # No port configured for this bot
        return 1
    fi

    # Use curl to check health endpoint via port
    if curl -sf --max-time "$HEALTH_CHECK_TIMEOUT" "http://127.0.0.1:$port/health" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
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

# First, update shared dependencies (only once for all bots)
header "Updating Shared Dependencies"
info "Installing from $SHARED_REQUIREMENTS..."

if [ -f "$SHARED_REQUIREMENTS" ]; then
    # All bots share a single venv in production
    SHARED_VENV="$REPO_PATH/.venv"

    if [ ! -d "$SHARED_VENV" ]; then
        warning "Shared virtual environment not found at $SHARED_VENV"
        info "Creating shared virtual environment..."
        python3 -m venv "$SHARED_VENV"
    fi

    "$SHARED_VENV/bin/pip" install -q -r "$SHARED_REQUIREMENTS"
    success "Shared dependencies updated"
else
    warning "Shared requirements.txt not found at $SHARED_REQUIREMENTS"
fi

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

# Give services a moment to start up before health checks
info "Waiting 3 seconds for services to initialize..."
sleep 3

header "Health Check Summary"

echo "Checking bot health endpoints via HTTP..."
echo "----------------------------------------"
failed_bots=()
healthy_bots=()

for bot in "${BOTS[@]}"; do
    service_name="gunicorn-bot-team-$bot"
    port=$(get_bot_port "$bot")

    # First check if service is running
    if ! systemctl is-active --quiet "$service_name" 2>/dev/null; then
        error "$bot: service not running"
        failed_bots+=("$bot")
        continue
    fi

    # Check if we have a port configured
    if [ -z "$port" ]; then
        warning "$bot: no port configured in chester/config.yaml"
        failed_bots+=("$bot")
        continue
    fi

    # Check health endpoint via HTTP port
    if check_bot_health "$bot"; then
        success "$bot: healthy (port $port)"
        healthy_bots+=("$bot")
    else
        error "$bot: health check failed (http://127.0.0.1:$port/health)"
        failed_bots+=("$bot")
    fi
done

echo ""
echo "----------------------------------------"
info "Healthy: ${#healthy_bots[@]} | Failed: ${#failed_bots[@]}"

# Show troubleshooting commands for failed bots
if [ ${#failed_bots[@]} -gt 0 ]; then
    header "Failed Bots - Troubleshooting"

    echo "Run these commands to investigate:"
    echo ""

    for bot in "${failed_bots[@]}"; do
        service_name="gunicorn-bot-team-$bot"
        port=$(get_bot_port "$bot")

        echo "--- $bot ---"
        echo "  Check service status:"
        echo "    sudo systemctl status $service_name"
        echo ""
        echo "  View recent logs:"
        echo "    sudo journalctl -u $service_name -n 50"
        echo ""
        echo "  Test health endpoint:"
        echo "    curl -v http://127.0.0.1:$port/health"
        echo ""
        echo "  Follow logs (live tail):"
        echo "    sudo journalctl -u $service_name -f"
        echo ""
    done
else
    success "All bots are healthy!"
fi

echo ""
success "Update complete!"
echo ""
