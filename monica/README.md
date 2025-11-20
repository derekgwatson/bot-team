# 📡 Monica - ChromeOS Monitoring Agent

Monica is a lightweight monitoring agent for ChromeOS devices (Chromeboxes) with a simple web-based dashboard. It tracks device heartbeats, network health, and provides real-time status monitoring for retail store devices.

## 🎯 Features

- **Zero-installation agent**: Just visit a URL, no extensions needed
- **Real-time monitoring**: Live heartbeat tracking with traffic-light status indicators
- **Network health metrics**: Latency and download speed measurements
- **Multi-store support**: Organize devices by store location
- **Persistent registration**: Devices remember their configuration using localStorage
- **Auto-refresh dashboard**: See all your devices at a glance
- **REST API**: Full API for integration with other systems

## 🏗️ Architecture

Monica follows the bot-team ecosystem patterns:

```
monica/
├── app.py                    # Flask application entry point
├── config.py                 # Configuration loader
├── config.yaml               # Bot configuration
├── api/
│   └── routes.py             # REST API endpoints
├── web/
│   └── routes.py             # Web interface (dashboard, agent page)
├── database/
│   ├── db.py                 # Database manager
│   └── schema.sql            # SQLite schema
└── services/
    └── status_service.py     # Business logic for status computation
```

**Port:** 8015 (registered in `shared/config/ports.yaml`)

## 📋 Database Schema

### Stores
- Retail store locations (e.g., "FYSHWICK", "BELCONNEN")

### Devices
- Individual ChromeOS devices at each store
- Each device has a unique agent token for authentication
- Tracks last heartbeat timestamp and status

### Heartbeats
- Historical heartbeat records with timestamps
- Network metrics (latency, download speed)
- Public IP addresses and user agents

## 🚀 Quick Start

### 1. Install Dependencies

Monica uses the shared virtual environment at the project root:

```bash
cd /home/user/bot-team
source .venv/bin/activate  # If not already activated
```

All required dependencies should already be in the project's `requirements.txt`.

### 2. Configure Environment

```bash
cd monica
cp .env.example .env
# Edit .env and set FLASK_SECRET_KEY
```

### 3. Run Monica

```bash
python monica/app.py
```

Monica will start on **http://localhost:8015**

You should see:
```
============================================================
📡 Hi! I'm Monica
   ChromeOS device monitoring agent with heartbeat tracking
   Version: 1.0.0
   Running on http://0.0.0.0:8015
============================================================

Endpoints:
  • Dashboard:  http://localhost:8015/dashboard
  • Agent Page: http://localhost:8015/agent?store=XXX&device=YYY
  • API Info:   http://localhost:8015/info
  • Health:     http://localhost:8015/health
============================================================
```

### 4. View the Dashboard

Open **http://localhost:8015/dashboard** to see all registered devices.

### 5. Set Up a Test Device

Visit: **http://localhost:8015/agent?store=EXAMPLE&device=TestDevice**

The agent will:
1. Auto-register with the server
2. Save credentials to localStorage
3. Start sending heartbeats every 60 seconds
4. Run network tests every 5 minutes

## 🏪 Setting Up Chromeboxes in Stores

### For Each Chromebox:

1. **Open Chrome** on the Chromebox

2. **Navigate to the agent page** with your store and device info:
   ```
   https://your-server.com/agent?store=FYSHWICK&device=Front%20Counter
   ```

   Replace:
   - `FYSHWICK` → Your store code
   - `Front%20Counter` → Device name (URL-encoded)

3. **Pin the tab** (right-click → Pin tab)

4. **Set as startup page**:
   - Settings → On startup → Open a specific page
   - Add the agent URL

5. **Done!** The Chromebox will now:
   - Send heartbeats every 60 seconds
   - Run network tests every 5 minutes
   - Persist across browser restarts

### Alternative: ChromeOS Kiosk Mode

For managed ChromeOS devices via Google Admin Console:

1. **Create a Kiosk app** pointing to the agent URL
2. **Deploy to devices** via organizational unit
3. **Configure auto-launch** on device startup

This provides the most robust solution for production deployments.

## 📊 Dashboard

The dashboard shows all devices grouped by store with real-time status:

### Status Indicators

- 🟢 **Online** (Green): Last seen ≤ 2 minutes ago
- 🟡 **Degraded** (Amber): Last seen 2-10 minutes ago
- 🔴 **Offline** (Red): Last seen > 10 minutes ago

### Auto-Refresh

The dashboard auto-refreshes every 30 seconds by default.

Configure refresh interval in `config.yaml`:
```yaml
dashboard:
  auto_refresh: 30  # seconds
```

## 🔌 API Endpoints

### POST /api/register
Register a new device or retrieve existing credentials.

**Request:**
```json
{
  "store_code": "FYSHWICK",
  "device_label": "Front Counter"
}
```

**Response:**
```json
{
  "success": true,
  "device_id": 123,
  "agent_token": "abc123...",
  "message": "Device registered successfully"
}
```

### POST /api/heartbeat
Record a heartbeat from a device.

**Headers:**
```
X-Agent-Token: <agent_token>
```

**Request:**
```json
{
  "timestamp": "2025-11-20T10:30:00Z",  // optional
  "latency_ms": 45.2,                    // optional
  "download_mbps": 98.5                  // optional
}
```

**Response:**
```json
{
  "success": true,
  "message": "Heartbeat recorded"
}
```

### GET /api/devices
List all devices with their current status.

**Response:**
```json
{
  "success": true,
  "devices": [
    {
      "id": 1,
      "store_code": "FYSHWICK",
      "device_label": "Front Counter",
      "last_heartbeat_at": "2025-11-20T10:30:00",
      "computed_status": "online",
      "status_emoji": "🟢",
      "status_label": "Online",
      "last_seen_text": "2 minutes ago",
      "last_public_ip": "203.123.45.67"
    }
  ]
}
```

### GET /api/devices/:id/heartbeats
Get heartbeat history for a specific device.

**Query Parameters:**
- `limit` (optional): Maximum number of heartbeats to return (default: 100)

**Response:**
```json
{
  "success": true,
  "heartbeats": [
    {
      "id": 1,
      "device_id": 1,
      "timestamp": "2025-11-20T10:30:00",
      "public_ip": "203.123.45.67",
      "latency_ms": 45.2,
      "download_mbps": 98.5
    }
  ]
}
```

## ⚙️ Configuration

### config.yaml

```yaml
name: monica
description: ChromeOS device monitoring agent with heartbeat tracking
version: 1.0.0
emoji: 📡

server:
  host: 0.0.0.0
  port: 8015

# Heartbeat thresholds (in minutes)
heartbeat:
  online_threshold: 2      # Green if last seen within 2 minutes
  degraded_threshold: 10   # Amber if last seen within 10 minutes

# Agent settings
agent:
  heartbeat_interval: 60   # Seconds between heartbeats
  network_test_interval: 300  # Seconds between network tests (5 minutes)
  network_test_file_size: 1048576  # 1 MB file for speed test

# Database
database:
  cleanup_days: 30  # Keep heartbeats for 30 days

# Dashboard
dashboard:
  auto_refresh: 30  # Auto-refresh dashboard every 30 seconds
```

### Environment Variables (.env)

```bash
# Flask Configuration
FLASK_SECRET_KEY=your-secret-key-here
FLASK_DEBUG=False

# Optional: Bot API Key (for bot-to-bot communication)
BOT_API_KEY=shared-bot-api-key
```

## 🗄️ Database

Monica uses SQLite for data storage. The database file is created automatically at:
```
monica/database/monica.db
```

### Database Maintenance

**Cleanup old heartbeats** (automated in future):
```python
from monica.database.db import db
db.cleanup_old_heartbeats(days=30)  # Delete heartbeats older than 30 days
```

## 🔒 Security Notes

### For MVP / Internal Use:
- Agent registration is **public** (no authentication required)
- Heartbeat endpoints require **agent token** (X-Agent-Token header)
- Agent tokens are **32-byte secure random tokens**
- Tokens stored in **localStorage** (client-side)

### For Production:
1. **Use HTTPS** (configure nginx with SSL certificates)
2. **Rate limiting** (protect registration endpoint)
3. **IP whitelisting** (if devices have static IPs)
4. **Google OAuth** (optional: add admin authentication to dashboard)
5. **Token rotation** (implement token expiry and refresh)

## 🚀 Production Deployment

### Using Gunicorn + Nginx

1. **Install gunicorn** (should be in requirements.txt):
   ```bash
   pip install gunicorn
   ```

2. **Run with gunicorn**:
   ```bash
   gunicorn -w 4 -b 0.0.0.0:8015 monica.app:app
   ```

3. **Configure nginx** (see `deployment/nginx/` for examples):
   ```nginx
   server {
       listen 80;
       server_name monitor.example.com;

       location / {
           proxy_pass http://127.0.0.1:8015;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

4. **Set up systemd service** (see `deployment/systemd/` for templates)

## 🧪 Testing

### Manual Testing

1. **Start Monica**:
   ```bash
   python monica/app.py
   ```

2. **Open agent page** in multiple browser tabs with different store/device combos:
   - http://localhost:8015/agent?store=STORE1&device=Device1
   - http://localhost:8015/agent?store=STORE1&device=Device2
   - http://localhost:8015/agent?store=STORE2&device=Device1

3. **View dashboard**:
   - http://localhost:8015/dashboard

4. **Check API**:
   ```bash
   curl http://localhost:8015/api/devices
   ```

### Test Registration API

```bash
curl -X POST http://localhost:8015/api/register \
  -H "Content-Type: application/json" \
  -d '{"store_code":"TEST","device_label":"TestDevice"}'
```

### Test Heartbeat API

```bash
# Use the agent_token from registration response
curl -X POST http://localhost:8015/api/heartbeat \
  -H "Content-Type: application/json" \
  -H "X-Agent-Token: YOUR_TOKEN_HERE" \
  -d '{"latency_ms": 45.2, "download_mbps": 98.5}'
```

## 🤝 Integration with Bot Ecosystem

Monica integrates with the bot-team ecosystem:

- **Port**: 8015 (registered in `shared/config/ports.yaml`)
- **Health check**: `/health` endpoint for Chester monitoring
- **API**: Other bots can query device status via `/api/devices`
- **Pattern compliance**: Follows standard bot structure and conventions

### Register with Chester

Add Monica to Chester's bot registry (`chester/config.yaml`):
```yaml
bots:
  monica:
    name: Monica
    description: ChromeOS Monitoring Agent
    url: http://localhost:8015
    emoji: 📡
```

## 📚 Future Enhancements

### Agent Improvements
- [ ] Chrome extension version (background service worker)
- [ ] More network tests (jitter, packet loss)
- [ ] Geolocation tracking
- [ ] Screenshot capture on demand

### Backend Enhancements
- [ ] Alert system (email/SMS when devices go offline)
- [ ] Historical graphs (uptime, network performance)
- [ ] Device groups and tags
- [ ] Batch operations (update config, restart agent)
- [ ] API authentication for dashboard access
- [ ] WebSocket support for real-time updates

### Operations
- [ ] Automated database cleanup job
- [ ] Backup and restore scripts
- [ ] Docker containerization
- [ ] Multi-region support

## 🐛 Troubleshooting

### Device Not Showing Up

1. Check agent page shows "Connected" status
2. Verify registration succeeded (check device ID displayed)
3. Check server logs for errors
4. Verify heartbeat timer is running (check agent logs)

### Status Shows Offline

1. Check time since last heartbeat
2. Verify network connectivity
3. Check if tab was closed or browser crashed
4. Re-open agent URL to resume heartbeats

### Network Tests Failing

1. Check browser console for errors
2. Verify server is reachable
3. Check CORS settings if on different domain
4. Network tests are optional - heartbeats will continue

### Database Errors

1. Ensure write permissions on `monica/database/` directory
2. Check disk space
3. Delete `monica.db` to recreate (will lose data)

## 📞 Support

For issues or questions:
- Check `/health` endpoint: http://localhost:8015/health
- Check `/info` endpoint: http://localhost:8015/info
- Review server logs in terminal
- Check browser console on agent page

## 📄 License

Part of the Watson Blinds bot-team ecosystem.

---

**Built with 💙 by the bot-team**

Version: 1.0.0 | Port: 8015 | Status: ✅ Operational
