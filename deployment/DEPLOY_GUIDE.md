# Day-to-Day Deployment Guide

Quick reference for deploying changes to production.

## Prerequisites

### Configure sudoers for www-data

To allow www-data to restart services without a password, add this to sudoers:

```bash
sudo visudo
```

Add these lines:
```
# Allow www-data to restart gunicorn services
www-data ALL=(ALL) NOPASSWD: /bin/systemctl restart gunicorn-bot-team-*
www-data ALL=(ALL) NOPASSWD: /bin/systemctl status gunicorn-bot-team-*
www-data ALL=(ALL) NOPASSWD: /bin/systemctl is-active gunicorn-bot-team-*
```

This allows the deployment script to restart services while running as www-data.

## Quick Deploy (Recommended)

Use the deployment script for automated deployment:

```bash
# Deploy all bots (run as www-data to avoid permission issues)
cd /var/www/bot-team
sudo -u www-data ./deployment/deploy.sh all

# Deploy a specific bot
sudo -u www-data ./deployment/deploy.sh pam
```

The script automatically:
- Pulls latest changes from git
- Shows what changed
- Installs dependencies if requirements.txt changed
- Restarts the affected services
- Verifies services are running

## Manual Deployment Steps

If you need to deploy manually:

### 1. Pull Latest Changes

```bash
# Run as www-data to avoid permission issues
sudo -u www-data bash
cd /var/www/bot-team
git pull origin main  # or your branch name
```

### 2. Update Dependencies (if requirements.txt changed)

```bash
# For a specific bot (example: Pam)
cd /var/www/bot-team/pam
.venv/bin/pip install -r requirements.txt

# Or for all bots
for bot in fred iris peter pam quinn; do
    /var/www/bot-team/$bot/.venv/bin/pip install -r /var/www/bot-team/$bot/requirements.txt
done
```

### 3. Restart Services

```bash
# Restart a specific bot
sudo systemctl restart gunicorn-bot-team-pam

# Restart all bots
sudo systemctl restart gunicorn-bot-team-fred
sudo systemctl restart gunicorn-bot-team-iris
sudo systemctl restart gunicorn-bot-team-peter
sudo systemctl restart gunicorn-bot-team-pam
sudo systemctl restart gunicorn-bot-team-quinn
```

### 4. Verify Services

```bash
# Check status of a specific bot
sudo systemctl status gunicorn-bot-team-pam

# Check status of all bots
for bot in fred iris peter pam quinn; do
    echo "=== $bot ==="
    sudo systemctl status gunicorn-bot-team-$bot --no-pager
    echo ""
done
```

## View Logs

```bash
# View live logs for a specific bot
sudo journalctl -u gunicorn-bot-team-pam -f

# View recent logs (last 50 lines)
sudo journalctl -u gunicorn-bot-team-pam -n 50

# View logs from the last hour
sudo journalctl -u gunicorn-bot-team-pam --since "1 hour ago"

# View logs for all bots
sudo journalctl -u "gunicorn-bot-team-*" -f
```

## Check What Changed

```bash
# Run as www-data to see git status
sudo -u www-data bash
cd /var/www/bot-team

# See recent commits
git log -5 --oneline

# See what changed in last commit
git show --stat

# Compare with remote
git fetch
git log HEAD..origin/main --oneline

exit
```

## Rollback to Previous Version

```bash
# Run as www-data
sudo -u www-data bash
cd /var/www/bot-team

# See recent commits
git log --oneline

# Rollback to a specific commit
git reset --hard <commit-hash>

# Then restart services
exit  # exit www-data shell
sudo -u www-data ./deployment/deploy.sh all
```

## Emergency: Quick Restart All Services

```bash
sudo systemctl restart gunicorn-bot-team-{fred,iris,peter,pam,quinn}
```

## Enable Maintenance Mode

```bash
# For a specific bot (example: Pam)
sudo touch /var/www/bot-team/pam/maintenance.on

# Disable maintenance mode
sudo rm /var/www/bot-team/pam/maintenance.on
```

Note: Maintenance mode doesn't require nginx reload - it works immediately!

## Nginx Commands

```bash
# Test nginx configuration
sudo nginx -t

# Reload nginx (for config changes)
sudo systemctl reload nginx

# Restart nginx
sudo systemctl restart nginx

# View nginx logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

## SSL Certificate Renewal

Certbot handles this automatically, but to force renewal:

```bash
# Dry run (test)
sudo certbot renew --dry-run

# Force renewal
sudo certbot renew --force-renewal
```

## Troubleshooting

### Service won't start

```bash
# Check service logs
sudo journalctl -u gunicorn-bot-team-pam -n 50

# Check if socket exists
ls -la /run/gunicorn-pam/

# Check if virtual environment is intact
/var/www/bot-team/pam/.venv/bin/python --version

# Try starting manually for debugging
cd /var/www/bot-team/pam
source .venv/bin/activate
gunicorn --bind 127.0.0.1:9999 app:app  # Test on different port
```

### 502 Bad Gateway

```bash
# Check if gunicorn service is running
sudo systemctl status gunicorn-bot-team-pam

# Check if socket file exists
ls -la /run/gunicorn-pam/gunicorn.sock

# Check nginx error log
sudo tail -f /var/log/nginx/error.log
```

### Dependencies issues

```bash
# Reinstall all dependencies in virtual environment
cd /var/www/bot-team/pam
.venv/bin/pip install --force-reinstall -r requirements.txt
```

## Best Practices

1. **Always test in dev first** - Test changes locally before deploying to production
2. **Use the deployment script** - It handles dependencies and restarts automatically
3. **Check logs after deploy** - Monitor for errors: `sudo journalctl -u gunicorn-bot-team-pam -f`
4. **Deploy during low-traffic times** - Minimize user impact
5. **One bot at a time** - For major changes, deploy and verify each bot individually
6. **Keep maintenance.html ready** - Use maintenance mode for longer deployments

## Common Workflows

### Fixing a bug in Pam

```bash
# 1. Pull latest changes as www-data (includes your fix)
sudo -u www-data bash
cd /var/www/bot-team
git pull
exit

# 2. Deploy just Pam
sudo -u www-data ./deployment/deploy.sh pam

# 3. Watch logs to verify fix
sudo journalctl -u gunicorn-bot-team-pam -f
```

### Adding a new dependency

```bash
# 1. Pull changes as www-data (includes updated requirements.txt)
sudo -u www-data bash
cd /var/www/bot-team
git pull
exit

# 2. Deploy (script will detect requirements.txt change)
sudo -u www-data ./deployment/deploy.sh pam

# Script automatically installs new dependencies
```

### Deploying changes to multiple bots

```bash
# Pull and deploy all at once
sudo -u www-data bash
cd /var/www/bot-team
git pull
exit
sudo -u www-data ./deployment/deploy.sh all
```
