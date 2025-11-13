# Bot Team Production Deployment Guide

Complete guide to deploying the bot-team application with gunicorn and nginx on a production server.

## Architecture Overview

- **5 Flask bots** running independently as systemd services
- **Gunicorn** as the WSGI server for each bot (3 workers per bot)
- **Nginx** as reverse proxy with SSL termination
- **Let's Encrypt** for SSL certificates
- **Unix sockets** for nginx ↔ gunicorn communication (faster than TCP)
- Each bot has its own socket at `/run/gunicorn-*/gunicorn.sock`
- Nginx proxies external HTTPS traffic to the appropriate bot via unix socket

## Prerequisites

- Ubuntu 20.04+ or Debian 11+ server
- Root or sudo access
- Domain names pointing to your server:
  - fred.watsonblinds.com.au
  - iris.watsonblinds.com.au
  - peter.watsonblinds.com.au
  - pam.watsonblinds.com.au
  - quinn.watsonblinds.com.au

## Step 1: Server Setup

### Install required packages

```bash
sudo apt update
sudo apt install -y python3.9 python3.9-venv python3-pip nginx certbot python3-certbot-nginx git
```

### Create deployment user and directory

```bash
# The bots will run as www-data (nginx user)
sudo mkdir -p /var/www/bot-team
sudo chown www-data:www-data /var/www/bot-team
```

## Step 2: Deploy Code

### Clone repository

```bash
cd /var/www
sudo -u www-data git clone <your-repo-url> bot-team
cd bot-team
```

### Create virtual environments

Each bot gets its own virtual environment:

```bash
# Fred
sudo -u www-data python3.9 -m venv fred/.venv
sudo -u www-data fred/.venv/bin/pip install --upgrade pip
sudo -u www-data fred/.venv/bin/pip install -r fred/requirements.txt
sudo -u www-data fred/.venv/bin/pip install gunicorn

# Iris
sudo -u www-data python3.9 -m venv iris/.venv
sudo -u www-data iris/.venv/bin/pip install --upgrade pip
sudo -u www-data iris/.venv/bin/pip install -r iris/requirements.txt
sudo -u www-data iris/.venv/bin/pip install gunicorn

# Peter
sudo -u www-data python3.9 -m venv peter/.venv
sudo -u www-data peter/.venv/bin/pip install --upgrade pip
sudo -u www-data peter/.venv/bin/pip install -r peter/requirements.txt
sudo -u www-data peter/.venv/bin/pip install gunicorn

# Pam
sudo -u www-data python3.9 -m venv pam/.venv
sudo -u www-data pam/.venv/bin/pip install --upgrade pip
sudo -u www-data pam/.venv/bin/pip install -r pam/requirements.txt
sudo -u www-data pam/.venv/bin/pip install gunicorn

# Quinn
sudo -u www-data python3.9 -m venv quinn/.venv
sudo -u www-data quinn/.venv/bin/pip install --upgrade pip
sudo -u www-data quinn/.venv/bin/pip install -r quinn/requirements.txt
sudo -u www-data quinn/.venv/bin/pip install gunicorn
```

## Step 3: Setup Google Service Account Credentials

### Copy credentials.json to each bot directory

```bash
# Replace with your actual credentials.json file
sudo -u www-data cp /path/to/credentials.json /var/www/bot-team/fred/
sudo -u www-data cp /path/to/credentials.json /var/www/bot-team/iris/
sudo -u www-data cp /path/to/credentials.json /var/www/bot-team/peter/
sudo -u www-data cp /path/to/credentials.json /var/www/bot-team/quinn/
```

### Set proper permissions

```bash
sudo chmod 600 /var/www/bot-team/*/credentials.json
```

## Step 4: Generate Flask Secret Keys

Each bot needs its own unique secret key:

```bash
# Generate 5 different secret keys
python3 -c "import secrets; print('Fred:  ', secrets.token_hex(32))"
python3 -c "import secrets; print('Iris:  ', secrets.token_hex(32))"
python3 -c "import secrets; print('Peter: ', secrets.token_hex(32))"
python3 -c "import secrets; print('Pam:   ', secrets.token_hex(32))"
python3 -c "import secrets; print('Quinn: ', secrets.token_hex(32))"

# Generate Quinn's API key
python3 -c "import secrets; print('Quinn API:', secrets.token_urlsafe(32))"
```

Save these keys - you'll need them in the next step.

## Step 5: Configure Environment Variables

### Setup Google OAuth credentials

1. Go to Google Cloud Console > APIs & Services > Credentials
2. Create OAuth 2.0 Client ID (Web application)
3. Add authorized redirect URIs for each bot:
   - `https://fred.watsonblinds.com.au/oauth/callback`
   - `https://iris.watsonblinds.com.au/oauth/callback`
   - `https://peter.watsonblinds.com.au/oauth/callback`
   - `https://quinn.watsonblinds.com.au/admin/oauth/callback`
4. Save the Client ID and Client Secret

### Create .env files for each bot

Use the templates in `deployment/env-examples/` as starting points:

```bash
# Fred
sudo -u www-data cp deployment/env-examples/fred.env.production /var/www/bot-team/fred/.env
sudo -u www-data nano /var/www/bot-team/fred/.env
# Fill in: FLASK_SECRET_KEY, GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET

# Iris
sudo -u www-data cp deployment/env-examples/iris.env.production /var/www/bot-team/iris/.env
sudo -u www-data nano /var/www/bot-team/iris/.env
# Fill in: FLASK_SECRET_KEY, GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET

# Peter
sudo -u www-data cp deployment/env-examples/peter.env.production /var/www/bot-team/peter/.env
sudo -u www-data nano /var/www/bot-team/peter/.env
# Fill in: FLASK_SECRET_KEY, GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET

# Pam
sudo -u www-data cp deployment/env-examples/pam.env.production /var/www/bot-team/pam/.env
sudo -u www-data nano /var/www/bot-team/pam/.env
# Fill in: FLASK_SECRET_KEY, QUINN_API_URL, PETER_API_URL

# Quinn
sudo -u www-data cp deployment/env-examples/quinn.env.production /var/www/bot-team/quinn/.env
sudo -u www-data nano /var/www/bot-team/quinn/.env
# Fill in: FLASK_SECRET_KEY, GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, QUINN_API_KEY
```

### Secure the .env files

```bash
sudo chmod 600 /var/www/bot-team/*/.env
sudo chown www-data:www-data /var/www/bot-team/*/.env
```

## Step 6: Setup Systemd Services

### Install service files

```bash
sudo cp deployment/systemd/gunicorn-bot-team-fred.service /etc/systemd/system/
sudo cp deployment/systemd/gunicorn-bot-team-iris.service /etc/systemd/system/
sudo cp deployment/systemd/gunicorn-bot-team-peter.service /etc/systemd/system/
sudo cp deployment/systemd/gunicorn-bot-team-pam.service /etc/systemd/system/
sudo cp deployment/systemd/gunicorn-bot-team-quinn.service /etc/systemd/system/
```

### Enable and start services

```bash
# Reload systemd to recognize new services
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable gunicorn-bot-team-fred gunicorn-bot-team-iris gunicorn-bot-team-peter gunicorn-bot-team-pam gunicorn-bot-team-quinn

# Start all services
sudo systemctl start gunicorn-bot-team-fred gunicorn-bot-team-iris gunicorn-bot-team-peter gunicorn-bot-team-pam gunicorn-bot-team-quinn

# Check status
sudo systemctl status gunicorn-bot-team-fred
sudo systemctl status gunicorn-bot-team-iris
sudo systemctl status gunicorn-bot-team-peter
sudo systemctl status gunicorn-bot-team-pam
sudo systemctl status gunicorn-bot-team-quinn
```

### Verify bots are running

```bash
# Check if unix sockets exist
ls -l /run/gunicorn-*/gunicorn.sock

# Check systemd logs for any startup errors
sudo journalctl -u gunicorn-bot-team-fred -n 20 --no-pager
sudo journalctl -u gunicorn-bot-team-iris -n 20 --no-pager
sudo journalctl -u gunicorn-bot-team-peter -n 20 --no-pager
sudo journalctl -u gunicorn-bot-team-pam -n 20 --no-pager
sudo journalctl -u gunicorn-bot-team-quinn -n 20 --no-pager
```

## Step 7: Setup SSL Certificates

### Get certificates and configure HTTPS with certbot

Certbot will automatically:
- Obtain SSL certificates from Let's Encrypt
- Add HTTPS (443) server blocks to your nginx configs
- Configure HTTP to HTTPS redirects
- Set up auto-renewal

```bash
# Get certificates for each bot (interactive)
# Certbot will modify the nginx configs to enable HTTPS
sudo certbot --nginx -d fred.watsonblinds.com.au
sudo certbot --nginx -d iris.watsonblinds.com.au
sudo certbot --nginx -d peter.watsonblinds.com.au
sudo certbot --nginx -d pam.watsonblinds.com.au
sudo certbot --nginx -d quinn.watsonblinds.com.au

# Or get all certificates at once (if DNS is already configured for all domains)
sudo certbot --nginx \
  -d fred.watsonblinds.com.au \
  -d iris.watsonblinds.com.au \
  -d peter.watsonblinds.com.au \
  -d pam.watsonblinds.com.au \
  -d quinn.watsonblinds.com.au
```

**Note:** The nginx configs are intentionally HTTP-only initially. Certbot will add all the HTTPS configuration automatically.

### Setup auto-renewal

```bash
# Test renewal
sudo certbot renew --dry-run

# Certbot automatically installs a cron job for renewal
# Verify it exists:
sudo systemctl status certbot.timer
```

## Step 8: Configure Nginx

### Install nginx configurations

```bash
# Copy config files to sites-available
sudo cp deployment/nginx/bot-team-fred.conf /etc/nginx/sites-available/
sudo cp deployment/nginx/bot-team-iris.conf /etc/nginx/sites-available/
sudo cp deployment/nginx/bot-team-peter.conf /etc/nginx/sites-available/
sudo cp deployment/nginx/bot-team-pam.conf /etc/nginx/sites-available/
sudo cp deployment/nginx/bot-team-quinn.conf /etc/nginx/sites-available/

# Enable sites by creating symlinks
sudo ln -s /etc/nginx/sites-available/bot-team-fred.conf /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/bot-team-iris.conf /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/bot-team-peter.conf /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/bot-team-pam.conf /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/bot-team-quinn.conf /etc/nginx/sites-enabled/

# Remove default site if present
sudo rm -f /etc/nginx/sites-enabled/default
```

### Test and reload nginx

```bash
# Test configuration
sudo nginx -t

# If test passes, reload nginx
sudo systemctl reload nginx
```

## Step 9: Setup Quinn Database

Quinn uses SQLite for storing external staff data:

```bash
# Create database directory
sudo -u www-data mkdir -p /var/www/bot-team/quinn/database

# The database will be created automatically on first run
# But you can initialize it manually if needed:
cd /var/www/bot-team/quinn
sudo -u www-data ../venv/bin/python -c "from models.external_staff import init_db; init_db()"
```

## Step 10: Verify Deployment

### Test each bot in your browser

1. **Fred**: https://fred.watsonblinds.com.au
   - Should redirect to Google OAuth login
   - After login, you should see the user management interface

2. **Iris**: https://iris.watsonblinds.com.au
   - Should redirect to Google OAuth login
   - After login, you should see the reporting interface

3. **Peter**: https://peter.watsonblinds.com.au
   - Should redirect to Google OAuth login
   - After login, you should see the phone directory management interface

4. **Pam**: https://pam.watsonblinds.com.au
   - Public interface - no login required
   - Should display the phone directory

5. **Quinn**: https://quinn.watsonblinds.com.au
   - Public self-service interface at `/`
   - Admin interface at `/admin` (requires OAuth login)

### Check logs if issues occur

```bash
# Systemd service logs
sudo journalctl -u gunicorn-bot-team-fred -n 50 --no-pager
sudo journalctl -u gunicorn-bot-team-iris -n 50 --no-pager
sudo journalctl -u gunicorn-bot-team-peter -n 50 --no-pager
sudo journalctl -u gunicorn-bot-team-pam -n 50 --no-pager
sudo journalctl -u gunicorn-bot-team-quinn -n 50 --no-pager

# Nginx logs
sudo tail -f /var/log/nginx/fred.error.log
sudo tail -f /var/log/nginx/iris.error.log
sudo tail -f /var/log/nginx/peter.error.log
sudo tail -f /var/log/nginx/pam.error.log
sudo tail -f /var/log/nginx/quinn.error.log

# Application logs (logs go to systemd journal)
# View logs for all bots in real-time:
sudo journalctl -u gunicorn-bot-team-fred -u gunicorn-bot-team-iris -u gunicorn-bot-team-peter -u gunicorn-bot-team-pam -u gunicorn-bot-team-quinn -f

# Or individual bot:
sudo journalctl -u gunicorn-bot-team-pam -f
```

## Ongoing Management

### Update code

```bash
cd /var/www/bot-team
sudo -u www-data git pull

# Install any new dependencies for each bot
sudo -u www-data fred/.venv/bin/pip install -r fred/requirements.txt
sudo -u www-data iris/.venv/bin/pip install -r iris/requirements.txt
sudo -u www-data peter/.venv/bin/pip install -r peter/requirements.txt
sudo -u www-data pam/.venv/bin/pip install -r pam/requirements.txt
sudo -u www-data quinn/.venv/bin/pip install -r quinn/requirements.txt

# Restart services
sudo systemctl restart gunicorn-bot-team-fred gunicorn-bot-team-iris gunicorn-bot-team-peter gunicorn-bot-team-pam gunicorn-bot-team-quinn
```

### Restart individual bot

```bash
sudo systemctl restart gunicorn-bot-team-fred
# or
sudo systemctl restart gunicorn-bot-team-iris
# or
sudo systemctl restart gunicorn-bot-team-peter
# etc.
```

### View service status

```bash
sudo systemctl status gunicorn-bot-team-fred gunicorn-bot-team-iris gunicorn-bot-team-peter gunicorn-bot-team-pam gunicorn-bot-team-quinn
```

### Stop all bots

```bash
sudo systemctl stop gunicorn-bot-team-fred gunicorn-bot-team-iris gunicorn-bot-team-peter gunicorn-bot-team-pam gunicorn-bot-team-quinn
```

### Start all bots

```bash
sudo systemctl start gunicorn-bot-team-fred gunicorn-bot-team-iris gunicorn-bot-team-peter gunicorn-bot-team-pam gunicorn-bot-team-quinn
```

## Troubleshooting

### Bot won't start

```bash
# Check service status
sudo systemctl status gunicorn-bot-team-fred

# Check detailed logs
sudo journalctl -u gunicorn-bot-team-fred -n 100 --no-pager

# Common issues:
# - Missing .env file
# - Invalid credentials.json
# - Wrong file permissions
# - Port already in use
```

### OAuth login fails

1. Check redirect URI in Google Cloud Console matches exactly:
   - Must be `https://` (not `http://`)
   - Must include `/oauth/callback` path
   - For Quinn admin: `/admin/oauth/callback`

2. Check GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in .env

3. Check FLASK_SECRET_KEY is set in .env

### 502 Bad Gateway

- Bot service is not running: `sudo systemctl start gunicorn-bot-team-<bot-name>`
- Check unix socket exists: `ls -l /run/gunicorn-*/gunicorn.sock`
- Check socket permissions: `ls -l /run/gunicorn-pam/` (should be owned by www-data)
- Check systemd logs: `sudo journalctl -u gunicorn-bot-team-pam -n 50`

### SSL certificate issues

```bash
# Renew certificates manually
sudo certbot renew

# Check certificate expiry
sudo certbot certificates
```

## Security Notes

1. **Never commit .env files** - They contain secrets
2. **Never commit credentials.json** - It's in .gitignore
3. **Keep Flask secret keys unique** - Different key for each bot
4. **Restrict file permissions** - .env and credentials.json should be 600
5. **Update regularly** - Keep packages and OS up to date
6. **Monitor logs** - Watch for suspicious activity
7. **Backup database** - Quinn's SQLite database at `quinn/database/external_staff.db`

## Firewall Configuration

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# The bots communicate via unix sockets - no need to open additional ports
```

## Backup

### Important files to backup

```bash
# Environment files (contain secrets)
/var/www/bot-team/*/.env

# Google service account credentials
/var/www/bot-team/*/credentials.json

# Quinn's database
/var/www/bot-team/quinn/database/external_staff.db

# Nginx configs (if customized)
/etc/nginx/sites-available/*.conf

# SSL certificates (auto-renewed, but good to backup)
/etc/letsencrypt/
```

### Backup script example

```bash
#!/bin/bash
BACKUP_DIR="/backup/bot-team-$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# Backup .env files
cp /var/www/bot-team/*/.env $BACKUP_DIR/

# Backup credentials
cp /var/www/bot-team/*/credentials.json $BACKUP_DIR/

# Backup Quinn database
cp /var/www/bot-team/quinn/database/external_staff.db $BACKUP_DIR/

# Encrypt backup
tar czf - $BACKUP_DIR | gpg --encrypt --recipient your@email.com > bot-team-backup.tar.gz.gpg
```

## Performance Tuning

### Adjust worker count

Edit gunicorn config files in `deployment/gunicorn/*.py`:

```python
# Rule of thumb: 2-4 workers per bot
workers = 2

# For CPU-intensive tasks:
workers = multiprocessing.cpu_count() * 2 + 1
```

After changes:
```bash
sudo systemctl restart <bot-name>
```

### Monitor resource usage

```bash
# CPU and memory per service
systemctl status gunicorn-bot-team-fred gunicorn-bot-team-iris gunicorn-bot-team-peter gunicorn-bot-team-pam gunicorn-bot-team-quinn

# Detailed resource monitoring
htop

# Check gunicorn processes
ps aux | grep gunicorn
```

## Quick Reference

### Service names
- `gunicorn-bot-team-fred` - User management bot
- `gunicorn-bot-team-iris` - Reporting bot
- `gunicorn-bot-team-peter` - Phone directory manager
- `gunicorn-bot-team-pam` - Phone directory presenter
- `gunicorn-bot-team-quinn` - External staff access manager

### URLs
- https://fred.watsonblinds.com.au
- https://iris.watsonblinds.com.au
- https://peter.watsonblinds.com.au
- https://pam.watsonblinds.com.au
- https://quinn.watsonblinds.com.au

### Common commands
```bash
# Restart all bots
sudo systemctl restart gunicorn-bot-team-fred gunicorn-bot-team-iris gunicorn-bot-team-peter gunicorn-bot-team-pam gunicorn-bot-team-quinn

# View all logs
sudo journalctl -u gunicorn-bot-team-fred -u gunicorn-bot-team-iris -u gunicorn-bot-team-peter -u gunicorn-bot-team-pam -u gunicorn-bot-team-quinn -f

# Update code and restart
cd /var/www/bot-team && sudo -u www-data git pull && sudo systemctl restart gunicorn-bot-team-fred gunicorn-bot-team-iris gunicorn-bot-team-peter gunicorn-bot-team-pam gunicorn-bot-team-quinn
```
