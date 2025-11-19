# 🤖 Bot Team

A collection of purpose-built bots, each doing one thing well.

## Philosophy

Following the Unix principle: **do one thing and do it well.** Each bot in this team is focused on a specific task and provides both a web interface for humans and a REST API for bot-to-bot communication.

## Meet the Team

### 👤 Fred
**Google Workspace User Management**

Fred handles onboarding and offboarding for your Google Workspace account. He can create users, archive users, and provide visibility into your organization's accounts.

- Port: 8001
- API: http://localhost:8001/api/
- [Read Fred's documentation →](fred/README.md)

### 🔍 Iris
**Google Workspace Reporting & Analytics**

Iris keeps an eye on how your Google Workspace is being used. She tracks storage quotas, usage patterns, and provides insights into Gmail vs Drive consumption. Perfect for identifying who's using the most space and understanding your organization's storage trends.

- Port: 8002
- API: http://localhost:8002/api/
- [Read Iris's documentation →](iris/README.md)

### 📱 Peter
**Phone Directory Manager**

Peter manages your organization's phone directory. He syncs with your Google Sheets phone list and makes it easy to search for extensions, mobile numbers, and emails. Perfect for bot-to-bot integration when other bots need contact information.

- Port: 8003
- API: http://localhost:8003/api/
- [Read Peter's documentation →](peter/README.md)

### 👩‍💼 Sally
**SSH Command Executor**

Sally is your go-to girl for server operations. She handles SSH connections and executes commands on remote servers securely. Sally provides a simple REST API and web interface for running commands, viewing execution history, and managing server access. She's focused on doing one thing well: executing SSH commands reliably.

- Port: 8004
- API: http://localhost:8004/api/
- [Read Sally's documentation →](sally/README.md)

### 🚀 Dorothy
**Deployment Orchestrator**

Dorothy knows how to deploy and manage bots. She orchestrates complex deployment workflows by calling Sally to execute commands on servers. Dorothy handles nginx configuration, gunicorn services, SSL certificates, git repositories, virtual environments, and permissions. She can verify deployments, run health checks, and keep track of deployment history.

- Port: 8005
- API: http://localhost:8005/api/
- [Read Dorothy's documentation →](dorothy/README.md)

### 👤 Zac
**Zendesk User Management**

Zac manages your Zendesk users. He can create, update, suspend, and delete Zendesk users (end-users, agents, and admins). Zac provides a friendly web interface for managing your support team and a REST API for automation. Perfect for onboarding new support agents or managing customer accounts.

- Port: 8007
- API: http://localhost:8007/api/
- [Read Zac's documentation →](zac/README.md)

### 🎉 Oscar
**Staff Onboarding Orchestrator**

Oscar coordinates the entire staff onboarding process. He provides a simple web form for initiating onboarding and automatically orchestrates the workflow across multiple bots: notifying HR, creating Google Workspace accounts (via Fred), creating Zendesk accounts (via Zac), registering staff in the HR database (via Peter), and creating VOIP setup tickets (via Sadie). Oscar tracks the entire workflow with detailed status and activity logging, and manages manual tasks that require human intervention.

- Port: 8011
- API: http://localhost:8011/api/
- [Read Oscar's documentation →](oscar/README.md)

## How Bots Work Together

Each bot:
- Is **self-contained** with its own dependencies and configuration
- Exposes a **REST API** at `/api/*` for automation
- Provides a **web interface** at `/` for manual operations
- Can **call other bots** via their APIs
- Has a **personality** (name) to make the system more approachable

Example workflows:
```
# Staff Onboarding
Oscar (orchestrate) → Email notification to HR
                    → Fred (create Google user)
                    → Zac (create Zendesk account)
                    → Peter (register in HR database)
                    → Sadie (create VOIP setup ticket)

# Cleanup
Analytics bot → Iris (find heavy storage users)
              → Fred (check last login)
              → Fred (archive inactive users)

# Deployment
Dorothy (orchestrate) → Sally (execute SSH commands) → Production Server
   ↓
Verify nginx, gunicorn, SSL, repo, venv, permissions

# Server Management
Admin → Sally (run server command) → Production Server
        ↑
   Direct command execution
```

## Adding New Bots

1. Create a new directory: `mkdir <bot-name>`
2. Follow the pattern established by Fred
3. Update this README with the new bot's description
4. Each bot should be independently deployable

## Running Bots

Each bot runs on its own port:
- **Fred** (Google Workspace User Management): `http://localhost:8001`
- **Iris** (Google Workspace Reporting): `http://localhost:8002`
- **Peter** (Staff Directory / HR Database): `http://localhost:8003`
- **Sally** (SSH Command Executor): `http://localhost:8004`
- **Dorothy** (Deployment Orchestrator): `http://localhost:8005`
- **Quinn** (External Staff Access Manager): `http://localhost:8006`
- **Zac** (Zendesk User Management): `http://localhost:8007`
- **Chester** (Bot Team Concierge): `http://localhost:8008`
- **Pam** (Phone Directory Presenter): `http://localhost:8009`
- **Sadie** (Zendesk Ticket Manager): `http://localhost:8010`
- **Oscar** (Staff Onboarding Orchestrator): `http://localhost:8011`
- (Future bots will use 8012, 8013, etc.)

For production deployment, use nginx to route domains/paths to different bots.

## Development

### Quick Start

All bots use a single consolidated virtual environment at the project root:

**Windows:**
```powershell
.\setup-venv.ps1
.venv\Scripts\Activate.ps1
```

**Linux/Mac:**
```bash
./setup-venv.sh
source .venv/bin/activate
```

### Running Bots

Once the venv is activated, run any bot:

```bash
python chester/app.py
python dorothy/app.py
python sally/app.py
# ... etc
```

### Manual Setup

If you prefer to set up manually:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

---

Built with ❤️ following the Unix philosophy.
