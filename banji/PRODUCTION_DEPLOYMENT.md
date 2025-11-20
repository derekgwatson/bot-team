# Banji Production Deployment Guide

This guide covers deploying Banji on a traditional Linux server using pip (no Docker).

## Prerequisites

- **Linux server** (Ubuntu 20.04+ or similar)
- **Python 3.8+** installed
- **SSH access** to your server
- **sudo/root access** for installing system packages

## Step-by-Step Deployment

### 1. Install Python Dependencies

```bash
# On your server
cd /path/to/bot-team

# Install Python packages (including Playwright)
pip install -r requirements.txt
```

### 2. Install Playwright Browsers

Playwright needs to download Chromium browser:

```bash
playwright install chromium
```

This downloads Chromium (~150MB) to `~/.cache/ms-playwright/`

### 3. Install System Dependencies

**This is the critical step for production!**

Playwright needs various system libraries to run headless browsers on Linux. Install them:

```bash
# Easiest way - let Playwright install everything:
playwright install-deps chromium
```

**Or manually (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0
```

**For other distributions:**
- **CentOS/RHEL:** `playwright install-deps chromium` handles it
- **Alpine Linux:** Use `apk add` with similar package names

### 4. Verify Production Readiness

Run the verification script to check everything is installed correctly:

```bash
cd banji
python tools/verify_production_ready.py
```

**Expected output:**
```
╔==========================================================╗
║  Banji Production Readiness Verification               ║
╚==========================================================╝

============================================================
  Python Version Check
============================================================
✓ Python version: 3.11.5
✓ Python version is compatible

============================================================
  Playwright Package Check
============================================================
✓ Playwright package installed: 1.40.0

============================================================
  Playwright Browser Check
============================================================
✓ Playwright browsers appear to be installed

============================================================
  System Dependencies Check (Linux)
============================================================
✓ Critical system libraries appear to be installed

============================================================
  Browser Launch Test
============================================================
Attempting to launch Chromium in headless mode...
✓ Browser launched successfully!
✓ Browser can navigate and render pages

============================================================
  Environment Configuration Check
============================================================
✓ .env file exists: /path/to/banji/.env
✓ Required environment variables appear to be set

============================================================
  Authentication Storage State Check
============================================================
✓ Storage state exists for: designer_drapes
✓ Storage state exists for: canberra

✓ All storage state files present

============================================================
  Summary
============================================================
✓ Python Version
✓ Playwright Package
✓ Playwright Browsers
✓ System Dependencies
✓ Browser Launch
✓ Environment Config
✓ Auth Storage States

Passed: 7/7

============================================================
🎉 All checks passed! Banji is ready for production!
============================================================
```

If any checks fail, follow the error messages to fix them.

### 5. Configure Environment

```bash
cd banji

# Copy environment template
cp .env.example .env

# Edit with your settings
nano .env
```

**Required settings:**
```bash
BUZ_ORGS=designer_drapes,canberra,tweed
BOT_API_KEY=your-secure-api-key-here
FLASK_SECRET_KEY=another-secure-random-key
```

**Production settings:**
```bash
FLASK_DEBUG=False  # Disable debug mode
# BUZ_HEADLESS is auto-set to true when FLASK_DEBUG=False
```

### 6. Bootstrap Authentication

For each organization, generate the auth storage state file.

**Option A: Bootstrap on dev machine, copy to production**
```bash
# On your dev machine (with GUI)
cd banji
python tools/buz_auth_bootstrap.py designer_drapes

# This creates: .secrets/buz_storage_state_designer_drapes.json

# Copy to production server
scp .secrets/buz_storage_state_designer_drapes.json \
    user@prod-server:/path/to/banji/.secrets/
```

**Option B: Bootstrap directly on production (if X11 forwarding available)**
```bash
# On production server with X11 forwarding
cd banji
python tools/buz_auth_bootstrap.py designer_drapes
```

**Repeat for all organizations in your BUZ_ORGS list.**

### 7. Test Manually

Before setting up as a service, test that Banji runs:

```bash
cd banji
python app.py
```

You should see:
```
==================================================
🎭 Hi! I'm Banji
   Browser Automation for Buz
   Running on http://localhost:8014
   Browser mode: headless
==================================================
```

**Test the health endpoint:**
```bash
curl http://localhost:8014/health
```

Expected response:
```json
{
  "status": "healthy",
  "bot": "Banji",
  "version": "1.0.0",
  "browser_mode": "headless"
}
```

If that works, press Ctrl+C to stop Banji. Now let's set it up as a service.

### 8. Create Systemd Service

Create a systemd service file to run Banji automatically:

```bash
sudo nano /etc/systemd/system/banji.service
```

**Service file contents:**
```ini
[Unit]
Description=Banji - Browser Automation for Buz
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/bot-team/banji
Environment="PATH=/home/your-username/.local/bin:/usr/bin"
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=banji

[Install]
WantedBy=multi-user.target
```

**Adjust:**
- `User=your-username` - Replace with your actual username
- `WorkingDirectory=/path/to/bot-team/banji` - Replace with actual path
- `Environment="PATH=..."` - Adjust if you use virtualenv

**Enable and start the service:**
```bash
# Reload systemd to recognize new service
sudo systemctl daemon-reload

# Enable to start on boot
sudo systemctl enable banji

# Start the service
sudo systemctl start banji

# Check status
sudo systemctl status banji
```

**View logs:**
```bash
# Follow logs in real-time
sudo journalctl -u banji -f

# View last 100 lines
sudo journalctl -u banji -n 100
```

### 9. Configure Reverse Proxy (Optional)

If you want to access Banji externally, set up nginx as a reverse proxy:

```bash
sudo apt-get install nginx
```

**Create nginx config:**
```bash
sudo nano /etc/nginx/sites-available/banji
```

```nginx
server {
    listen 80;
    server_name banji.yourdomain.com;  # Replace with your domain

    location / {
        proxy_pass http://127.0.0.1:8014;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for long-running browser operations
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;  # 5 minutes for browser operations
    }
}
```

**Enable and reload nginx:**
```bash
sudo ln -s /etc/nginx/sites-available/banji /etc/nginx/sites-enabled/
sudo nginx -t  # Test config
sudo systemctl reload nginx
```

**Optional: Add HTTPS with Let's Encrypt:**
```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d banji.yourdomain.com
```

## Troubleshooting

### "Browser launch failed" Error

**Symptom:** Banji starts but crashes when trying to launch browser

**Solutions:**
1. **Missing system dependencies:**
   ```bash
   playwright install-deps chromium
   ```

2. **Check which library is missing:**
   ```bash
   cd banji
   python tools/verify_production_ready.py
   ```

3. **Check logs:**
   ```bash
   sudo journalctl -u banji -n 50
   ```

4. **Test browser launch manually:**
   ```bash
   cd banji
   python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(headless=True); print('Success!'); b.close()"
   ```

### Permission Issues

**Symptom:** "Permission denied" errors for `/tmp` or cache directories

**Solution:** Ensure the user running Banji has write access:
```bash
# Check who's running the service
sudo systemctl status banji | grep "Main PID"

# Ensure proper permissions
chmod 755 /home/your-username
chmod -R 755 ~/.cache/ms-playwright
```

### Storage State Expired

**Symptom:** "Authentication failed" errors in logs

**Solution:** Storage state files (session tokens) have expired. Regenerate:
```bash
cd banji
python tools/buz_auth_bootstrap.py designer_drapes

# Copy to production if bootstrapping locally
scp .secrets/buz_storage_state_designer_drapes.json user@prod:/path/to/banji/.secrets/

# Restart service
sudo systemctl restart banji
```

### High Memory Usage

**Symptom:** Server running out of memory

**Causes:**
- Browser sessions not being closed properly
- Too many concurrent sessions

**Solutions:**
1. Check active sessions:
   ```bash
   curl -H "X-API-Key: your-key" http://localhost:8014/api/sessions/active
   ```

2. Adjust session timeout in `app.py`:
   ```python
   session_manager = init_session_manager(config, session_timeout_minutes=15)  # Reduce from 30
   ```

3. Monitor memory:
   ```bash
   watch -n 5 'ps aux | grep banji'
   ```

4. Restart service to clear sessions:
   ```bash
   sudo systemctl restart banji
   ```

### Port Already in Use

**Symptom:** "Address already in use" error

**Solution:**
```bash
# Find what's using port 8014
sudo lsof -i :8014

# Kill the process if needed
sudo kill -9 <PID>

# Or change Banji's port in config.yaml
```

## Monitoring

### Check Service Status
```bash
# Is it running?
sudo systemctl status banji

# Recent logs
sudo journalctl -u banji -n 100

# Follow logs live
sudo journalctl -u banji -f
```

### Check Active Sessions
```bash
curl -H "X-API-Key: your-key" http://localhost:8014/api/sessions/active
```

### Health Check
```bash
curl http://localhost:8014/health
```

## Updating Banji

When you deploy new code:

```bash
# Pull latest code
cd /path/to/bot-team
git pull

# Install any new dependencies
pip install -r requirements.txt

# Restart service
sudo systemctl restart banji

# Check it started successfully
sudo systemctl status banji
```

## Security Considerations

1. **API Key Protection:**
   - Use strong, random API keys
   - Never commit `.env` to git
   - Rotate keys periodically

2. **Firewall:**
   - If Banji is only used internally, block port 8014 from external access:
     ```bash
     sudo ufw allow from 192.168.1.0/24 to any port 8014  # Internal network only
     ```

3. **Storage State Files:**
   - `.secrets/` directory is gitignored
   - These files contain session tokens - protect them like passwords
   - Regenerate if compromised

4. **File Permissions:**
   ```bash
   chmod 600 banji/.env
   chmod 700 banji/.secrets
   chmod 600 banji/.secrets/*.json
   ```

## Performance Tuning

### Session Timeout

Adjust based on your usage patterns:
```python
# In app.py
session_manager = init_session_manager(
    config,
    session_timeout_minutes=15  # Shorter timeout = less memory usage
)
```

### Browser Timeouts

Adjust in `config.yaml`:
```yaml
buz:
  login_timeout: 10000      # 10 seconds
  navigation_timeout: 5000  # 5 seconds
  save_timeout: 10000       # 10 seconds
```

### Concurrent Sessions

Monitor and limit based on server resources. Each browser session uses ~100-200MB RAM.

## Support

If issues persist after following this guide:

1. Run verification script: `python tools/verify_production_ready.py`
2. Check logs: `sudo journalctl -u banji -n 100`
3. Test browser launch manually (see Troubleshooting section)
4. Review system requirements: Python 3.8+, sufficient RAM (2GB+ recommended)

---

**Next:** See [README.md](README.md) for API documentation and usage examples.
