# 👩‍💼 Sally - SSH Command Executor

Sally is your go-to girl for server operations. She handles SSH connections and executes commands on remote servers, providing a simple REST API and web interface for server management.

## What Sally Does

Sally is a **simple, focused SSH executor** - she connects to servers and runs commands. That's it. She doesn't know about deployments or orchestration; she just provides a reliable interface for remote command execution.

### Core Capabilities

- 🔐 **Secure SSH Connections** - Manages SSH connections using private keys
- ⚡ **Command Execution** - Runs commands and captures stdout, stderr, and exit codes
- 📊 **Execution History** - Keeps track of all commands executed
- 🔍 **Connection Testing** - Verify server connectivity before executing commands
- 🌐 **REST API** - Full API for programmatic access
- 🖥️ **Web Interface** - User-friendly UI for manual operations

## Quick Start

### 1. Install Dependencies

```bash
cd sally
pip install -r requirements.txt
```

### 2. Configure Servers

Edit `config.yaml` to add your servers:

```yaml
servers:
  prod:
    host: your-prod-server.com
    user: ubuntu
    description: Production Ubuntu Server

  staging:
    host: staging.example.com
    user: ubuntu
    description: Staging Environment
```

### 3. Set Up SSH Key

```bash
# Copy example env file
cp .env.example .env

# Edit .env and set your SSH key path
# SSH_PRIVATE_KEY_PATH=/home/user/.ssh/id_rsa
```

### 4. Run Sally

```bash
python app.py
```

Visit http://localhost:8004 to see Sally's web interface!

## API Reference

### List Servers
```bash
GET /api/servers
```

Response:
```json
{
  "servers": [
    {
      "name": "prod",
      "host": "your-server.com",
      "user": "ubuntu",
      "description": "Production Server"
    }
  ],
  "count": 1
}
```

### Test Connection
```bash
GET /api/test/<server_name>
```

Response:
```json
{
  "connected": true,
  "server": "prod",
  "message": "Sally is connected!"
}
```

### Execute Command
```bash
POST /api/execute
Content-Type: application/json

{
  "server": "prod",
  "command": "ls -la /var/www",
  "timeout": 60
}
```

Response:
```json
{
  "success": true,
  "exit_code": 0,
  "stdout": "total 12\ndrwxr-xr-x ...",
  "stderr": "",
  "execution_time": 0.34,
  "server": "prod",
  "command": "ls -la /var/www",
  "id": "a1b2c3d4",
  "timestamp": 1699564823.45
}
```

### Get Command History
```bash
GET /api/history?limit=50
```

Response:
```json
{
  "history": [
    {
      "id": "a1b2c3d4",
      "server": "prod",
      "command": "ls -la",
      "success": true,
      "exit_code": 0,
      "execution_time": 0.34,
      "timestamp": 1699564823.45
    }
  ],
  "total": 127
}
```

### Get Execution Details
```bash
GET /api/history/<exec_id>
```

## Security Notes

- Sally uses SSH key-based authentication only (no passwords)
- Private keys should never be committed to git (they're in `.gitignore`)
- Each command execution is logged with full details
- Connections are reused but can be closed with proper shutdown
- Command timeouts prevent hung connections

## Integration with Other Bots

Sally is designed to be called by other bots! For example, **Dorothy** (the deployment orchestrator) calls Sally's API to execute deployment commands.

Example integration:
```python
import requests

# Ask Sally to execute a command
response = requests.post('http://localhost:8004/api/execute', json={
    'server': 'prod',
    'command': 'systemctl status nginx'
})

result = response.json()
if result['success']:
    print(result['stdout'])
```

## Architecture Philosophy

Sally follows the Unix philosophy: **do one thing well**. She executes SSH commands and nothing more. This makes her:

- **Simple** - Easy to understand and maintain
- **Reliable** - Fewer moving parts, fewer bugs
- **Reusable** - Any bot can use Sally for SSH access
- **Testable** - Simple interface to test

For deployment orchestration, see **Dorothy** →

## Configuration

### config.yaml
```yaml
name: sally
description: SSH Command Executor
version: 0.1.0

server:
  host: 0.0.0.0
  port: 8004

ssh:
  default_user: ubuntu
  connect_timeout: 10      # seconds
  command_timeout: 300     # 5 minutes default

servers:
  # Add your servers here
```

### .env
```bash
SSH_PRIVATE_KEY_PATH=/path/to/your/id_rsa
```

## Common Use Cases

### Check Server Status
```bash
curl -X POST http://localhost:8004/api/execute \
  -H "Content-Type: application/json" \
  -d '{"server":"prod","command":"uptime"}'
```

### View Logs
```bash
curl -X POST http://localhost:8004/api/execute \
  -H "Content-Type: application/json" \
  -d '{"server":"prod","command":"tail -n 50 /var/log/nginx/error.log"}'
```

### Restart a Service
```bash
curl -X POST http://localhost:8004/api/execute \
  -H "Content-Type: application/json" \
  -d '{"server":"prod","command":"sudo systemctl restart nginx"}'
```

## Troubleshooting

### "Failed to load SSH key"
- Check that `SSH_PRIVATE_KEY_PATH` in `.env` points to a valid private key
- Ensure the key file has correct permissions (`chmod 600`)

### "Failed to connect"
- Verify the server host and user in `config.yaml`
- Test SSH manually: `ssh -i /path/to/key user@host`
- Check firewall rules and security groups

### "Server not configured"
- Make sure the server name exists in `config.yaml` under `servers:`

---

Built with ❤️ as part of the Bot Team
