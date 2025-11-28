#!/usr/bin/env bash
set -euo pipefail

# ==== Config ====
REPO_PATH="/var/www/bot-team"
# Default to Claude-style branches, but allow override:
#   ./merge_latest_git_branch.sh "feature/*"
#   ./merge_latest_git_branch.sh my-specific-branch
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

cd "$REPO_PATH"

header "Merging latest git branch into $MAIN_BRANCH"

info "Repository: $REPO_PATH"
info "Remote: $REMOTE"
info "Branch pattern: $BRANCH_PATTERN"

info "Fetching latest from $REMOTE..."
git fetch "$REMOTE" --prune

info "Checking for uncommitted changes..."
if ! git diff --quiet || ! git diff --cached --quiet; then
  error "You have uncommitted changes. Commit or stash them before running this script."
  exit 1
fi

# Always update main first, regardless of whether there's a branch to merge
info "Switching to $MAIN_BRANCH and updating from $REMOTE/$MAIN_BRANCH..."
git checkout "$MAIN_BRANCH"
git pull "$REMOTE" "$MAIN_BRANCH"

info "Finding latest remote branch matching pattern: $BRANCH_PATTERN"
LATEST_REMOTE_BRANCH=$(
  git for-each-ref \
    --sort=-committerdate \
    --format='%(refname:short)' \
    "refs/remotes/$REMOTE/$BRANCH_PATTERN" \
    | head -n 1
)

if [[ -z "${LATEST_REMOTE_BRANCH:-}" ]]; then
  warning "No remote branches found matching pattern '$BRANCH_PATTERN'. Nothing to merge."
  success "$MAIN_BRANCH is up to date with $REMOTE/$MAIN_BRANCH."
  exit 0
fi

info "Latest matching remote branch: $LATEST_REMOTE_BRANCH"

# Strip "origin/" prefix to get local branch name
LOCAL_BRANCH="${LATEST_REMOTE_BRANCH#${REMOTE}/}"

info "Ensuring local tracking branch '$LOCAL_BRANCH' exists..."
if git show-ref --verify --quiet "refs/heads/$LOCAL_BRANCH"; then
  info "Local branch '$LOCAL_BRANCH' exists. Updating from remote..."
  git checkout "$LOCAL_BRANCH"
  git reset --hard "$LATEST_REMOTE_BRANCH"
else
  info "Creating local tracking branch '$LOCAL_BRANCH' from '$LATEST_REMOTE_BRANCH'..."
  git checkout -b "$LOCAL_BRANCH" "$LATEST_REMOTE_BRANCH"
fi

info "Switching back to $MAIN_BRANCH for merge..."
git checkout "$MAIN_BRANCH"

info "Merging '$LOCAL_BRANCH' into '$MAIN_BRANCH'..."
if ! git merge --no-ff "$LOCAL_BRANCH" -m "Merge $LOCAL_BRANCH (latest matching branch) into $MAIN_BRANCH"; then
  echo
  error "Merge conflict detected."
  echo "Resolve conflicts, then run:"
  echo "  git add <fixed files>"
  echo "  git commit"
  echo "  git push $REMOTE $MAIN_BRANCH"
  exit 1
fi

info "Pushing updated $MAIN_BRANCH to $REMOTE..."
git push "$REMOTE" "$MAIN_BRANCH"

success "Merge and push complete. '$LOCAL_BRANCH' is now in '$MAIN_BRANCH'."
# Note: Branch deletion is handled by deploy.sh after bot restarts
