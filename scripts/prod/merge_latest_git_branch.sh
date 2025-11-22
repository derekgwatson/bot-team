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

info "Switching to $MAIN_BRANCH and updating from $REMOTE/$MAIN_BRANCH..."
git checkout "$MAIN_BRANCH"
git pull "$REMOTE" "$MAIN_BRANCH"

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

###########################################################
# Post-merge cleanup: optionally delete the merged branch #
###########################################################

# Only proceed if the branch is fully merged into MAIN_BRANCH
if git branch --merged "$MAIN_BRANCH" | grep -q " $LOCAL_BRANCH\$"; then
    header "Post-merge cleanup"

    info "Branch '$LOCAL_BRANCH' is fully merged into '$MAIN_BRANCH'."

    # Only prompt if stdin is a TTY (i.e. interactive run)
    if [ -t 0 ]; then
        echo
        read -r -p "Delete local branch '$LOCAL_BRANCH' and remote '$REMOTE/$LOCAL_BRANCH'? [y/N]: " REPLY
        case "$REPLY" in
            y|Y|yes|YES)
                info "Deleting local branch '$LOCAL_BRANCH'..."
                if git branch -d "$LOCAL_BRANCH"; then
                    success "Local branch '$LOCAL_BRANCH' deleted."
                else
                    warning "Could not delete local branch '$LOCAL_BRANCH' (maybe already gone?)."
                fi

                info "Deleting remote branch '$REMOTE/$LOCAL_BRANCH'..."
                if git push "$REMOTE" --delete "$LOCAL_BRANCH"; then
                    success "Remote branch '$REMOTE/$LOCAL_BRANCH' deleted."
                else
                    warning "Could not delete remote branch '$REMOTE/$LOCAL_BRANCH' (maybe already gone?)."
                fi
                ;;
            *)
                warning "Keeping branch '$LOCAL_BRANCH' (no delete requested)."
                ;;
        esac
    else
        warning "Non-interactive shell detected; skipping branch deletion prompt."
        warning "You can delete later with:"
        echo "  git branch -d \"$LOCAL_BRANCH\""
        echo "  git push $REMOTE --delete \"$LOCAL_BRANCH\""
    fi
else
    warning "Branch '$LOCAL_BRANCH' is not fully merged into '$MAIN_BRANCH'; skipping deletion."
fi

success "Done."
