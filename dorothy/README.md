# 🚀 Dorothy - Deployment Orchestrator

Dorothy knows how to deploy and manage bots. She orchestrates complex deployment workflows by calling Sally (the SSH executor) to run commands on remote servers.

## What Dorothy Does

Dorothy is a **smart deployment orchestrator** who understands how to:

- 🚀 **Deploy bots** - Full deployment workflow from clone to production
- ✅ **Verify deployments** - Check that everything is configured correctly
- 🏥 **Health checks** - Ensure bots are running and responding
- 📊 **Track deployments** - Keep history of all deployment activities

### Dorothy's Intelligence

Unlike Sally (who just executes commands), Dorothy **knows deployment workflows**:

- Nginx configuration and SSL certificates
- Gunicorn/systemd service management
- Git repository setup
- Python virtual environments
- File permissions and ownership
- Port availability and health checks

## Quick Start

### 1. Install Dependencies

```bash
cd dorothy
pip install -r requirements.txt
```

### 2. Configure Bots

Edit `config.yaml` to define your bots:

```yaml
bots:
  fred:
    port: 8001
    domain: fred.example.com
    repo: https://github.com/yourorg/bot-team.git
    path: /var/www/fred
    service: fred-bot

  iris:
    port: 8002
    domain: iris.example.com
    repo: https://github.com/yourorg/bot-team.git
    path: /var/www/iris
    service: iris-bot
```

### 3. Set Sally's URL

```bash
# Copy example env file
cp .env.example .env

# Edit if Sally is not on localhost:8004
# SALLY_URL=http://localhost:8004
```

### 4. Run Dorothy

```bash
python app.py
```

Visit http://localhost:8005 to see Dorothy's web interface!

## Architecture

Dorothy follows the **separation of concerns** principle:

```
Dorothy (Orchestrator)
    ↓ Calls API
Sally (SSH Executor)
    ↓ SSH Connection
Production Server
```

**Dorothy knows WHAT to do** - deployment workflows, verification steps
**Sally knows HOW to do it** - SSH connections, command execution

This separation makes both bots:
- Simpler and more focused
- Easier to test and maintain
- Reusable in different contexts

## API Reference

### List Bots
```bash
GET /api/bots
```

Response:
```json
{
  "bots": [
    {
      "name": "fred",
      "port": 8001,
      "domain": "fred.example.com",
      "path": "/var/www/fred",
      "service": "fred-bot"
    }
  ],
  "count": 1
}
```

### Verify Bot Deployment
```bash
POST /api/verify/<bot_name>
Content-Type: application/json

{
  "server": "prod"
}
```

Response:
```json
{
  "bot": "fred",
  "server": "prod",
  "all_passed": true,
  "checks": [
    {
      "check": "nginx_config",
      "success": true,
      "exists": true,
      "syntax_valid": true
    },
    {
      "check": "gunicorn_service",
      "success": true,
      "exists": true,
      "running": true
    },
    {
      "check": "ssl_certificate",
      "success": true,
      "exists": true,
      "domain": "fred.example.com"
    },
    {
      "check": "repository",
      "success": true,
      "exists": true,
      "branch": "main",
      "status": "clean"
    },
    {
      "check": "virtualenv",
      "success": true,
      "exists": true
    },
    {
      "check": "permissions",
      "success": true
    }
  ],
  "timestamp": 1699564823.45
}
```

### Deploy Bot
```bash
POST /api/deploy/<bot_name>
Content-Type: application/json

{
  "server": "prod"
}
```

Response:
```json
{
  "id": "a1b2c3d4",
  "bot": "fred",
  "server": "prod",
  "status": "completed",
  "start_time": 1699564800.0,
  "end_time": 1699564845.2,
  "duration": 45.2,
  "steps": [
    {
      "name": "Repository setup",
      "status": "completed",
      "result": {...}
    },
    {
      "name": "Virtual environment setup",
      "status": "completed",
      "result": {...}
    },
    {
      "name": "Install dependencies",
      "status": "completed",
      "result": {...}
    },
    {
      "name": "Nginx configuration",
      "status": "completed",
      "result": {...}
    },
    {
      "name": "Systemd service",
      "status": "completed",
      "result": {...}
    }
  ]
}
```

### Health Check
```bash
POST /api/health-check/<bot_name>
Content-Type: application/json

{
  "server": "prod"
}
```

Response:
```json
{
  "bot": "fred",
  "server": "prod",
  "port": 8001,
  "healthy": true,
  "response": "{\"status\":\"healthy\",...}",
  "success": true
}
```

### Deployment History
```bash
GET /api/deployments
```

Response:
```json
{
  "deployments": [
    {
      "id": "a1b2c3d4",
      "bot": "fred",
      "server": "prod",
      "status": "completed",
      "duration": 45.2
    }
  ],
  "total": 15
}
```

## Deployment Workflow

When you deploy a bot, Dorothy runs these steps:

### 1. Repository Setup
- Clones repo if not exists, or pulls latest changes
- Ensures correct branch is checked out

### 2. Virtual Environment
- Creates Python virtual environment if missing
- Activates venv for subsequent steps

### 3. Install Dependencies
- Runs `pip install -r requirements.txt`
- Ensures all packages are up to date

### 4. Nginx Configuration
- Creates/updates nginx site configuration
- Tests nginx syntax
- Reloads nginx if needed

### 5. Systemd Service
- Creates/updates systemd service file
- Reloads systemd daemon
- Restarts service

### 6. SSL Certificate (if needed)
- Runs certbot for Let's Encrypt SSL
- Configures auto-renewal

## Verification Checks

Dorothy can verify deployments with these checks:

### nginx_config
- ✅ Config file exists in `/etc/nginx/sites-available/`
- ✅ Nginx syntax is valid (`nginx -t`)

### gunicorn_service
- ✅ Service file exists in `/etc/systemd/system/`
- ✅ Service is running

### ssl_certificate
- ✅ Certificate exists in `/etc/letsencrypt/live/`
- ✅ Certificate is not expired

### repository
- ✅ Git repository is cloned
- ✅ On correct branch
- ✅ Working directory is clean

### virtualenv
- ✅ Virtual environment exists
- ✅ Required packages are installed

### permissions
- ✅ Directory ownership is correct
- ✅ File permissions are appropriate

## Configuration

### config.yaml

```yaml
name: dorothy
description: Deployment Orchestrator
version: 0.1.0

server:
  host: 0.0.0.0
  port: 8005

sally:
  url: http://localhost:8004  # Sally's API endpoint

deployment:
  default_server: prod
  deployment_timeout: 600  # 10 minutes
  verification_checks:
    - nginx_config
    - gunicorn_service
    - ssl_certificate
    - repository
    - virtualenv
    - permissions

bots:
  # Define your bots here
  fred:
    port: 8001
    domain: fred.example.com
    repo: https://github.com/yourorg/bot-team.git
    path: /var/www/fred
    service: fred-bot
```

### .env

```bash
# Sally's URL (optional)
SALLY_URL=http://localhost:8004

# GitHub token for private repos (optional)
GITHUB_TOKEN=your_token_here
```

## Common Use Cases

### Verify Everything is Set Up Correctly
```bash
curl -X POST http://localhost:8005/api/verify/fred \
  -H "Content-Type: application/json" \
  -d '{"server":"prod"}'
```

### Deploy a Bot
```bash
curl -X POST http://localhost:8005/api/deploy/fred \
  -H "Content-Type: application/json" \
  -d '{"server":"prod"}'
```

### Check if Bot is Healthy
```bash
curl -X POST http://localhost:8005/api/health-check/fred \
  -H "Content-Type: application/json" \
  -d '{"server":"prod"}'
```

## Integration Example

Dorothy can be called from CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Deploy to production
  run: |
    curl -X POST https://dorothy.example.com/api/deploy/fred \
      -H "Content-Type: application/json" \
      -d '{"server":"prod"}'
```

Or from other bots:

```python
import requests

# Deploy fred
response = requests.post('http://localhost:8005/api/deploy/fred', json={
    'server': 'prod'
})

deployment = response.json()
print(f"Deployment {deployment['id']} status: {deployment['status']}")
```

## Extending Dorothy

### Adding New Verification Checks

Add a method to `deployment_orchestrator.py`:

```python
def verify_custom_check(self, server: str, bot_name: str) -> Dict:
    """Your custom verification logic"""
    result = self._call_sally(server, "your command here")
    return {
        'check': 'custom_check',
        'success': result.get('success'),
        'details': 'your details'
    }
```

Then add to `config.yaml`:

```yaml
deployment:
  verification_checks:
    - nginx_config
    - gunicorn_service
    - custom_check  # Your new check
```

### Adding Custom Deployment Steps

Modify the `deploy_bot()` method in `deployment_orchestrator.py` to add your custom steps.

## Troubleshooting

### "Failed to call Sally"
- Check that Sally is running on the configured URL
- Verify `SALLY_URL` in `.env` or `config.yaml`

### "Bot not configured"
- Ensure the bot exists in `config.yaml` under `bots:`

### Verification Checks Failing
- Run individual checks to see specific issues
- Use Sally directly to debug: http://localhost:8004

---

Built with ❤️ as part of the Bot Team

Dorothy + Sally = Powerful deployment automation! 🚀
