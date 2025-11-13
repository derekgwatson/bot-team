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

## How Bots Work Together

Each bot:
- Is **self-contained** with its own dependencies and configuration
- Exposes a **REST API** at `/api/*` for automation
- Provides a **web interface** at `/` for manual operations
- Can **call other bots** via their APIs
- Has a **personality** (name) to make the system more approachable

Example workflows:
```
# Onboarding
Onboarding bot → Fred (create user) → Notification bot (send welcome email)

# Cleanup
Analytics bot → Iris (find heavy storage users)
              → Fred (check last login)
              → Fred (archive inactive users)
```

## Adding New Bots

1. Create a new directory: `mkdir <bot-name>`
2. Follow the pattern established by Fred
3. Update this README with the new bot's description
4. Each bot should be independently deployable

## Running Bots

Each bot runs on its own port:
- **Fred** (User Management): `http://localhost:8001`
- **Iris** (Reporting): `http://localhost:8002`
- (Future bots will use 8003, 8004, etc.)

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
