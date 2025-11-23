#!/bin/bash
# Sync Unleashed product data via Mavis
#
# Usage:
#   /var/www/bot-team/scripts/prod/sync_unleashed.sh
#
# Crontab example (sync every 4 hours):
#   0 */4 * * * /var/www/bot-team/scripts/prod/sync_unleashed.sh >> /var/log/mavis-sync.log 2>&1
#
# This script sources the .env file to get BOT_API_KEY, then calls
# Mavis's sync endpoint to trigger a full product sync from Unleashed.

set -e  # Exit on error

# ==== Configuration ====
BOT_TEAM_DIR="/var/www/bot-team"
MAVIS_URL="http://localhost:8017"
ENV_FILE="$BOT_TEAM_DIR/.env"

# ==== Colours (for interactive use) ====
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Detect if running interactively
if [ -t 1 ]; then
    info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
    success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
    warning() { echo -e "${YELLOW}[WARNING]${NC} $*"; }
    error()   { echo -e "${RED}[ERROR]${NC} $*"; }
else
    # No colours for cron/log output
    info()    { echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') $*"; }
    success() { echo "[SUCCESS] $(date '+%Y-%m-%d %H:%M:%S') $*"; }
    warning() { echo "[WARNING] $(date '+%Y-%m-%d %H:%M:%S') $*"; }
    error()   { echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') $*"; }
fi

# ==== Load environment ====
if [ ! -f "$ENV_FILE" ]; then
    error "Environment file not found: $ENV_FILE"
    exit 1
fi

# Source the .env file (set -a exports all variables)
set -a
source "$ENV_FILE"
set +a

# Validate BOT_API_KEY is set
if [ -z "${BOT_API_KEY:-}" ]; then
    error "BOT_API_KEY not found in $ENV_FILE"
    exit 1
fi

# ==== Trigger sync ====
info "Triggering Unleashed product sync via Mavis..."

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$MAVIS_URL/api/sync/run" \
    -H "X-API-Key: $BOT_API_KEY" \
    -H "Content-Type: application/json")

# Split response body and HTTP code
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    success "Sync completed successfully"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
elif [ "$HTTP_CODE" = "409" ]; then
    warning "Sync already in progress"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
else
    error "Sync failed with HTTP $HTTP_CODE"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
    exit 1
fi
