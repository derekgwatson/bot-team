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
REPO_PATH="/var/www/bot-team"
BRANCH_PATTERN="claude/*"
REMOTE="origin"
MAIN_BRANCH="main"

header "Deploying Latest Git Branch (default: claude/*)"

# Step 1: Preview and confirm branch merge
header "Step 1: Checking for feature branches to merge"

info "Fetching latest from $REMOTE..."
sudo -u www-data git -C "$REPO_PATH" fetch "$REMOTE" --prune

# Find the latest matching branch
LATEST_REMOTE_BRANCH=$(
  sudo -u www-data git -C "$REPO_PATH" for-each-ref \
    --sort=-committerdate \
    --format='%(refname:short)' \
    "refs/remotes/$REMOTE/$BRANCH_PATTERN" \
    | head -n 1
)

if [[ -z "${LATEST_REMOTE_BRANCH:-}" ]]; then
    warning "No remote branches found matching pattern '$BRANCH_PATTERN'."
    info "Skipping merge step - will just update $MAIN_BRANCH and restart bots."
    SKIP_MERGE=1
else
    LOCAL_BRANCH="${LATEST_REMOTE_BRANCH#${REMOTE}/}"

    echo ""
    info "Latest matching branch: ${WHITE}$LOCAL_BRANCH${NC}"

    # Show recent commits on the branch
    echo ""
    info "Recent commits on this branch:"
    sudo -u www-data git -C "$REPO_PATH" log --oneline -5 "$LATEST_REMOTE_BRANCH" 2>/dev/null | while read -r line; do
        echo "    $line"
    done
    echo ""

    # Prompt for confirmation
    if [ -t 0 ]; then
        read -r -p "Merge '$LOCAL_BRANCH' into $MAIN_BRANCH? [Y/n]: " REPLY
        case "$REPLY" in
            n|N|no|NO)
                warning "Merge skipped by user."
                info "Will just update $MAIN_BRANCH from remote and restart bots."
                SKIP_MERGE=1
                ;;
            *)
                info "Proceeding with merge..."
                SKIP_MERGE=0
                ;;
        esac
    else
        warning "Non-interactive shell detected; proceeding with merge automatically."
        SKIP_MERGE=0
    fi
fi

if [[ "${SKIP_MERGE:-0}" == "0" ]]; then
    header "Merging feature branch into main"
    info "Running merge_latest_git_branch.sh as www-data..."
    sudo -u www-data "$PROD_SCRIPTS_DIR/merge_latest_git_branch.sh"
    success "Merge step complete"
else
    header "Updating main branch"
    info "Pulling latest $MAIN_BRANCH from $REMOTE..."
    sudo -u www-data git -C "$REPO_PATH" checkout "$MAIN_BRANCH" 2>/dev/null || true
    sudo -u www-data git -C "$REPO_PATH" pull "$REMOTE" "$MAIN_BRANCH"
    success "Main branch updated"
fi

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
