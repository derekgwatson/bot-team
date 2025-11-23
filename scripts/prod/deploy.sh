#!/bin/bash
# Deploy latest changes from Claude's feature branch
# Usage:
#   /var/www/bot-team/scripts/prod/deploy.sh        # Deploy and restart all bots
#   /var/www/bot-team/scripts/prod/deploy.sh iris   # Deploy and restart only iris

set -e  # Exit on error

# ==== Self-update detection ====
# If this script was updated by the git merge, we need to re-exec the new version.
# We use an environment variable to prevent infinite loops.
SCRIPT_PATH="$(realpath "$0")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"

if [ -z "${DEPLOY_REEXEC:-}" ]; then
    # First run - record script hashes before merge
    export DEPLOY_SCRIPT_HASH_BEFORE
    DEPLOY_SCRIPT_HASH_BEFORE=$(md5sum "$SCRIPT_PATH" "$SCRIPT_DIR/restart_bots.sh" "$SCRIPT_DIR/merge_latest_git_branch.sh" 2>/dev/null | md5sum | cut -d' ' -f1)
fi

BOT="${1:-}"

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

PROD_SCRIPTS_DIR="/var/www/bot-team/scripts/prod"

header "Deploying Latest Git Branch (default: claude/*)"

# Step 1: Merge latest matching branch into main
header "Step 1: Merging latest matching git branch into main"
info "Running merge_latest_git_branch.sh as www-data..."
sudo -u www-data "$PROD_SCRIPTS_DIR/merge_latest_git_branch.sh"
success "Merge step complete"

# ==== Check if scripts were updated ====
if [ -z "${DEPLOY_REEXEC:-}" ] && [ -n "${DEPLOY_SCRIPT_HASH_BEFORE:-}" ]; then
    SCRIPT_HASH_AFTER=$(md5sum "$SCRIPT_PATH" "$SCRIPT_DIR/restart_bots.sh" "$SCRIPT_DIR/merge_latest_git_branch.sh" 2>/dev/null | md5sum | cut -d' ' -f1)

    if [ "$DEPLOY_SCRIPT_HASH_BEFORE" != "$SCRIPT_HASH_AFTER" ]; then
        header "Deploy Scripts Updated!"
        warning "The deploy scripts were updated by the merge."
        info "Re-executing with the new version..."
        echo ""

        # Set flag to prevent infinite loop, then re-exec
        export DEPLOY_REEXEC=1
        exec "$SCRIPT_PATH" "$@"
    fi
fi

# Step 2: Update bot(s) - pip install + restart services
echo ""
if [ -n "$BOT" ]; then
    header "Step 2: Updating bot '$BOT'"
    info "Running restart_bots.sh for $BOT as www-data..."
    sudo -u www-data "$PROD_SCRIPTS_DIR/restart_bots.sh" "$BOT"
else
    header "Step 2: Updating ALL bots"
    info "Running restart_bots.sh for all bots as www-data..."
    sudo -u www-data "$PROD_SCRIPTS_DIR/restart_bots.sh"
fi

echo ""
header "Deployment Complete"
success "Latest Claude changes deployed and bots updated"
echo ""
