#!/bin/bash
# Deploy latest changes from Claude's feature branch
# Usage:
#   /var/www/bot-team/scripts/prod/deploy_bot_team.sh        # Update all bots
#   /var/www/bot-team/scripts/prod/deploy_bot_team.sh iris   # Update only iris

set -e  # Exit on error

BOT="${1:-}"

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

PROD_SCRIPTS_DIR="/var/www/bot-team/scripts/prod"

header "Deploying Latest Git Branch (default: claude/*)"

# Step 1: Merge latest matching branch into main
header "Step 1: Merging latest matching git branch into main"
info "Running merge_latest_git_branch.sh as www-data..."
sudo -u www-data "$PROD_SCRIPTS_DIR/merge_latest_git_branch.sh"
success "Merge step complete"

# Step 2: Update bot(s) - pip install + restart services
echo ""
if [ -n "$BOT" ]; then
    header "Step 2: Updating bot '$BOT'"
    info "Running update_bots.sh for $BOT as www-data..."
    sudo -u www-data "$PROD_SCRIPTS_DIR/update_bots.sh" "$BOT"
else
    header "Step 2: Updating ALL bots"
    info "Running update_bots.sh for all bots as www-data..."
    sudo -u www-data "$PROD_SCRIPTS_DIR/update_bots.sh"
fi

echo ""
header "Deployment Complete"
success "Latest Claude changes deployed and bots updated"
echo ""
