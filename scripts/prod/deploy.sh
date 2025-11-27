#!/bin/bash
# Deploy latest changes from Claude's feature branch
# Usage:
#   /var/www/bot-team/scripts/prod/deploy.sh              # Deploy and restart only changed bots
#   /var/www/bot-team/scripts/prod/deploy.sh iris         # Deploy and restart only iris
#   /var/www/bot-team/scripts/prod/deploy.sh --force      # Deploy and restart ALL bots (skip change detection)

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

# Parse arguments
BOT=""
FORCE_ALL=0
for arg in "$@"; do
    case "$arg" in
        --force|-f)
            FORCE_ALL=1
            ;;
        *)
            BOT="$arg"
            ;;
    esac
done

# ==== Change Detection ====
# Record HEAD before any git operations so we can detect what changed
HEAD_BEFORE=""
record_head_before() {
    HEAD_BEFORE=$(sudo -u www-data git -C "$REPO_PATH" rev-parse HEAD 2>/dev/null || echo "")
}

# Determine which bots have changes between two commits
# Returns: space-separated list of bot names, or "ALL" if shared code changed
get_changed_bots() {
    local old_head="$1"
    local new_head="$2"

    if [ -z "$old_head" ] || [ -z "$new_head" ] || [ "$old_head" = "$new_head" ]; then
        echo ""
        return
    fi

    # Get list of changed files
    local changed_files
    changed_files=$(sudo -u www-data git -C "$REPO_PATH" diff --name-only "$old_head" "$new_head" 2>/dev/null || echo "")

    if [ -z "$changed_files" ]; then
        echo ""
        return
    fi

    # Check if shared code or requirements changed - if so, ALL bots need restart
    if echo "$changed_files" | grep -qE '^(shared/|requirements\.txt)'; then
        echo "ALL"
        return
    fi

    # Extract unique bot directories from changed files
    # Bot directories are top-level folders that aren't special dirs
    local bots=""
    local seen=""

    while IFS= read -r file; do
        # Get the top-level directory
        local top_dir
        top_dir=$(echo "$file" | cut -d'/' -f1)

        # Skip non-bot directories
        case "$top_dir" in
            shared|scripts|tests|docs|.github|""|.|..)
                continue
                ;;
        esac

        # Skip if we've already seen this bot
        if echo "$seen" | grep -q " $top_dir "; then
            continue
        fi
        seen="$seen $top_dir "

        # Check if it's actually a bot directory (has app.py)
        if [ -f "$REPO_PATH/$top_dir/app.py" ]; then
            if [ -n "$bots" ]; then
                bots="$bots $top_dir"
            else
                bots="$top_dir"
            fi
        fi
    done <<< "$changed_files"

    echo "$bots"
}

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

# Record HEAD before any changes (for change detection)
record_head_before

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

# If a specific bot was requested, just restart that one
if [ -n "$BOT" ]; then
    header "Step 2: Updating bot '$BOT'"
    info "Running restart_bots.sh for $BOT as www-data..."
    sudo -u www-data "$PROD_SCRIPTS_DIR/restart_bots.sh" "$BOT"
elif [ "$FORCE_ALL" = "1" ]; then
    header "Step 2: Updating ALL bots (--force)"
    info "Force flag set. Restarting all bots..."
    sudo -u www-data "$PROD_SCRIPTS_DIR/restart_bots.sh"
else
    # Detect which bots have changes
    HEAD_AFTER=$(sudo -u www-data git -C "$REPO_PATH" rev-parse HEAD 2>/dev/null || echo "")
    CHANGED_BOTS=$(get_changed_bots "$HEAD_BEFORE" "$HEAD_AFTER")

    if [ -z "$CHANGED_BOTS" ]; then
        header "Step 2: No code changes detected"
        info "HEAD before: ${HEAD_BEFORE:0:8}"
        info "HEAD after:  ${HEAD_AFTER:0:8}"
        warning "No bot code changes detected. Skipping restart."
        info "To force restart all bots, run: $PROD_SCRIPTS_DIR/restart_bots.sh"
    elif [ "$CHANGED_BOTS" = "ALL" ]; then
        header "Step 2: Updating ALL bots (shared code changed)"
        info "Shared code or requirements.txt was modified."
        info "Running restart_bots.sh for all bots as www-data..."
        sudo -u www-data "$PROD_SCRIPTS_DIR/restart_bots.sh"
    else
        header "Step 2: Updating changed bots only"
        info "Changed bots: ${WHITE}$CHANGED_BOTS${NC}"
        info "Running restart_bots.sh for changed bots..."
        # shellcheck disable=SC2086
        sudo -u www-data "$PROD_SCRIPTS_DIR/restart_bots.sh" $CHANGED_BOTS
    fi
fi

echo ""
header "Deployment Complete"
success "Latest Claude changes deployed and bots updated"
echo ""
