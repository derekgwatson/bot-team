#!/bin/bash
# Production deployment script for bot-team
# Usage: ./deploy.sh [bot-name|all]
# Example: ./deploy.sh pam
# Example: ./deploy.sh all

set -e  # Exit on error

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="/var/www/bot-team"
BOTS=("fred" "iris" "peter" "pam" "quinn")

# Function to print colored messages
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to deploy a single bot
deploy_bot() {
    local bot=$1
    local bot_dir="$PROJECT_ROOT/$bot"

    info "Deploying $bot..."

    # Check if bot directory exists
    if [ ! -d "$bot_dir" ]; then
        error "Bot directory not found: $bot_dir"
        return 1
    fi

    # Check if requirements.txt changed
    cd "$bot_dir"
    local requirements_changed=false
    if git diff HEAD@{1} HEAD --name-only 2>/dev/null | grep -q "requirements.txt"; then
        requirements_changed=true
        warning "requirements.txt changed for $bot"
    fi

    # Install/update dependencies if requirements changed
    if [ "$requirements_changed" = true ]; then
        info "Installing dependencies for $bot..."
        if [ -f "$bot_dir/.venv/bin/pip" ]; then
            "$bot_dir/.venv/bin/pip" install -r "$bot_dir/requirements.txt"
            success "Dependencies updated for $bot"
        else
            error "Virtual environment not found at $bot_dir/.venv"
            return 1
        fi
    fi

    # Restart the service
    local service_name="gunicorn-bot-team-$bot"
    info "Restarting $service_name..."

    if sudo systemctl restart "$service_name"; then
        success "$service_name restarted"

        # Wait a moment for the service to start
        sleep 2

        # Check service status
        if sudo systemctl is-active --quiet "$service_name"; then
            success "$bot is running"
        else
            error "$bot failed to start"
            sudo systemctl status "$service_name" --no-pager -l
            return 1
        fi
    else
        error "Failed to restart $service_name"
        return 1
    fi

    echo ""
}

# Main deployment logic
main() {
    local target=${1:-all}

    echo ""
    info "Starting deployment process..."
    echo ""

    # Navigate to project root
    cd "$PROJECT_ROOT"

    # Show current branch
    info "Current branch: $(git branch --show-current)"

    # Pull latest changes
    info "Pulling latest changes..."
    if git pull; then
        success "Git pull completed"
    else
        error "Git pull failed"
        exit 1
    fi

    echo ""
    info "Recent commits:"
    git log -3 --oneline
    echo ""

    # Deploy bots
    if [ "$target" = "all" ]; then
        info "Deploying all bots..."
        echo ""

        local failed_bots=()
        for bot in "${BOTS[@]}"; do
            if ! deploy_bot "$bot"; then
                failed_bots+=("$bot")
            fi
        done

        # Summary
        echo ""
        info "Deployment Summary:"
        if [ ${#failed_bots[@]} -eq 0 ]; then
            success "All bots deployed successfully"
        else
            error "Failed to deploy: ${failed_bots[*]}"
            exit 1
        fi
    else
        # Deploy specific bot
        local bot="$target"

        # Check if bot exists
        if [[ ! " ${BOTS[@]} " =~ " ${bot} " ]]; then
            error "Unknown bot: $bot"
            error "Available bots: ${BOTS[*]}"
            exit 1
        fi

        if deploy_bot "$bot"; then
            success "Deployment completed"
        else
            error "Deployment failed"
            exit 1
        fi
    fi

    echo ""
    info "To view logs, use: sudo journalctl -u gunicorn-bot-team-<bot> -f"
    echo ""
}

# Run main function with all arguments
main "$@"
