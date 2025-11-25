#!/usr/bin/env bash
set -euo pipefail

# Merge the latest claude/* feature branch into main, then optionally delete it
# Usage:
#   ./merge-feature.sh              # Find latest claude/* branch
#   ./merge-feature.sh "feature/*"  # Use different pattern
#   ./merge-feature.sh my-branch    # Merge specific branch

# ==== Config ====
BRANCH_PATTERN="${1:-claude/*}"
MAIN_BRANCH="main"
REMOTE="origin"

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

header "Merge Feature Branch into $MAIN_BRANCH"

info "Branch pattern: $BRANCH_PATTERN"

info "Fetching latest from $REMOTE..."
git fetch "$REMOTE" --prune

info "Checking for uncommitted changes..."
if ! git diff --quiet || ! git diff --cached --quiet; then
    error "You have uncommitted changes. Commit or stash them first."
    exit 1
fi

# Find the latest matching branch
info "Finding latest remote branch matching: $BRANCH_PATTERN"
LATEST_REMOTE_BRANCH=$(
    git for-each-ref \
        --sort=-committerdate \
        --format='%(refname:short)' \
        "refs/remotes/$REMOTE/$BRANCH_PATTERN" \
        | head -n 1
)

if [[ -z "${LATEST_REMOTE_BRANCH:-}" ]]; then
    warning "No remote branches found matching '$BRANCH_PATTERN'."
    exit 0
fi

LOCAL_BRANCH="${LATEST_REMOTE_BRANCH#${REMOTE}/}"

echo ""
info "Latest matching branch: ${WHITE}$LOCAL_BRANCH${NC}"

# Show recent commits
echo ""
info "Recent commits on this branch:"
git log --oneline -5 "$LATEST_REMOTE_BRANCH" 2>/dev/null | while read -r line; do
    echo "    $line"
done
echo ""

# Confirm merge
read -r -p "Merge '$LOCAL_BRANCH' into $MAIN_BRANCH? [Y/n]: " REPLY
case "$REPLY" in
    n|N|no|NO)
        warning "Merge cancelled."
        exit 0
        ;;
esac

# Update main first
header "Updating $MAIN_BRANCH"
git checkout "$MAIN_BRANCH"
git pull "$REMOTE" "$MAIN_BRANCH"

# Ensure local tracking branch exists and is up to date
info "Ensuring local branch '$LOCAL_BRANCH' is up to date..."
if git show-ref --verify --quiet "refs/heads/$LOCAL_BRANCH"; then
    git checkout "$LOCAL_BRANCH"
    git reset --hard "$LATEST_REMOTE_BRANCH"
else
    git checkout -b "$LOCAL_BRANCH" "$LATEST_REMOTE_BRANCH"
fi

# Merge
header "Merging $LOCAL_BRANCH into $MAIN_BRANCH"
git checkout "$MAIN_BRANCH"

if ! git merge --no-ff "$LOCAL_BRANCH" -m "Merge $LOCAL_BRANCH into $MAIN_BRANCH"; then
    echo ""
    error "Merge conflict! Resolve conflicts, then run:"
    echo "  git add <fixed files>"
    echo "  git commit"
    echo "  git push $REMOTE $MAIN_BRANCH"
    exit 1
fi

info "Pushing $MAIN_BRANCH to $REMOTE..."
git push "$REMOTE" "$MAIN_BRANCH"

success "Merge complete!"

# Prompt for branch deletion
header "Cleanup"

echo ""
read -r -p "Delete branch '$LOCAL_BRANCH' (local and remote)? [Y/n]: " REPLY
case "$REPLY" in
    n|N|no|NO)
        warning "Keeping branch '$LOCAL_BRANCH'."
        ;;
    *)
        info "Deleting local branch '$LOCAL_BRANCH'..."
        if git branch -d "$LOCAL_BRANCH" 2>/dev/null; then
            success "Local branch deleted."
        else
            warning "Could not delete local branch (maybe already gone?)."
        fi

        info "Deleting remote branch '$REMOTE/$LOCAL_BRANCH'..."
        if git push "$REMOTE" --delete "$LOCAL_BRANCH" 2>/dev/null; then
            success "Remote branch deleted."
        else
            warning "Could not delete remote branch (maybe already gone?)."
        fi
        ;;
esac

echo ""
success "Done!"
