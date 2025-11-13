# 🤖 Bot Team

A collection of purpose-built bots, each doing one thing well.

## Philosophy

Following the Unix principle: **do one thing and do it well.** Each bot in this team is focused on a specific task and provides both a web interface for humans and a REST API for bot-to-bot communication.

## Meet the Team

### 👤 Fred
**Google Workspace User Management**

Fred handles onboarding and offboarding for your Google Workspace account. He can create users, archive users, and provide visibility into your organization's accounts.

[Read Fred's documentation →](fred/README.md)

## How Bots Work Together

Each bot:
- Is **self-contained** with its own dependencies and configuration
- Exposes a **REST API** at `/api/*` for automation
- Provides a **web interface** at `/` for manual operations
- Can **call other bots** via their APIs
- Has a **personality** (name) to make the system more approachable

Example workflow:
```
Onboarding bot → Fred (create user) → Iris (send welcome email)
```

## Adding New Bots

1. Create a new directory: `mkdir <bot-name>`
2. Follow the pattern established by Fred
3. Update this README with the new bot's description
4. Each bot should be independently deployable

## Running Bots

Each bot runs on its own port:
- Fred: `http://localhost:8001`
- (Future bots will use 8002, 8003, etc.)

For production deployment, use nginx to route domains/paths to different bots.

## Development

Each bot has its own `requirements.txt` and can be developed independently:

```bash
cd <bot-name>
pip install -r requirements.txt
python app.py
```

---

Built with ❤️ following the Unix philosophy.
