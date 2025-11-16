# Chester - Bot Team Concierge

> *Helpful, knowledgeable, and welcoming. Like a classic concierge who knows everyone and everything about the establishment.*

Chester is your guide to the bot team! He maintains a comprehensive directory of all team members, monitors their health, and helps you find the right bot for any task.

## Features

- **Team Directory**: Complete registry of all 8 bots with their capabilities
- **Health Dashboard**: Real-time health monitoring for all team members
- **Smart Search**: Find bots by capability keywords
- **New Bot Guide**: Step-by-step instructions for adding new team members
- **Bot Details**: Detailed information about each bot's endpoints and features

## Quick Start

### Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your settings
```

### Running

```bash
# Development
python app.py

# Production (with gunicorn)
gunicorn -w 3 -b 0.0.0.0:8008 app:app
```

The web interface will be available at http://localhost:8008

## API Endpoints

### Bot Information
- `GET /api/bots` - Get all bots
- `GET /api/bots/<bot_name>` - Get specific bot info
- `GET /api/capabilities/<bot_name>` - Get bot capabilities
- `GET /api/summary` - Get team summary

### Health Checks
- `GET /api/health/all` - Check all bots' health
- `GET /api/health/<bot_name>` - Check specific bot health

### Search
- `GET /api/search?q=<keyword>` - Search bots by capability

### Standard Endpoints
- `GET /health` - Chester's health check
- `GET /info` - Chester's information

## Web Interface

- `/` - Home page with overview
- `/dashboard` - Interactive team dashboard with health status
- `/bot/<bot_name>` - Detailed bot information
- `/search` - Search for bots by capability
- `/new-bot-guide` - Guide for adding new bots

## Configuration

Chester's configuration is in `config.yaml`:

- **Bot Team Registry**: Maintains information about all team members
- **Health Check Settings**: Timeout and interval configurations
- **New Bot Template**: Standard structure for new bots

### Adding a New Bot to the Registry

Edit `config.yaml` and add your bot to the `bot_team` section:

```yaml
bot_team:
  yourbot:
    name: YourBotName
    port: 8010
    url: http://localhost:8010
    description: What your bot does
    capabilities:
      - Capability 1
      - Capability 2
    api_endpoints:
      info: /info
      health: /health
    personality: Bot's personality description
```

## Current Team Members

Chester knows about these bots:

1. **Fred** (8001) - Google Workspace User Management
2. **Iris** (8002) - Google Workspace Reporting & Analytics
3. **Peter** (8003) - Phone Directory Manager
4. **Sally** (8004) - SSH Command Executor
5. **Dorothy** (8005) - Deployment Orchestrator
6. **Quinn** (8006) - External Staff Access Manager
7. **Zac** (8007) - Zendesk User Management
8. **Pam** (8009) - Phone Directory Presenter

## Development

### Project Structure

```
chester/
├── app.py                 # Main Flask application
├── config.py              # Configuration loader
├── config.yaml            # Bot registry and settings
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (not in git)
├── .env.example           # Environment template
├── api/
│   └── bots.py           # Bot API endpoints
├── web/
│   ├── routes.py         # Web interface routes
│   └── templates/        # HTML templates
└── services/
    └── bot_service.py    # Bot information and health check logic
```

### Running Tests

```bash
# From bot-team root directory
pytest tests/unit/test_chester.py
pytest tests/integration/test_chester.py
```

## Production Deployment

See `/home/user/bot-team/deployment/DEPLOYMENT.md` for production deployment instructions.

Chester should be deployed with:
- Systemd service (`chester.service`)
- Nginx reverse proxy configuration
- SSL certificate (Let's Encrypt)
- Running as `www-data` user
- 3 gunicorn workers

## Version

Current version: 1.0.0
