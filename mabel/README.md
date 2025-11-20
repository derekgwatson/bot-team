# Mabel - Email Bot Microservice

**Mabel** (Mail Bot) is a standalone email-sending microservice for the bot-team ecosystem. It centralizes all email functionality, configuration, and templating so that other bots can send emails via a simple HTTP API without needing to know about SMTP, credentials, or email providers.

## Features

- **Centralized Email Sending**: Single service handles all outbound emails for the bot-team
- **RESTful API**: Simple HTTP POST endpoints for sending emails
- **Template Support**: Jinja2-based email templates (text and HTML)
- **Flexible Content**: Send plain text, HTML, or multipart emails
- **Attachments**: Support for base64-encoded file attachments
- **Batch Sending**: Send multiple emails in a single request
- **Security**: API key authentication for inter-bot communication
- **Health Checks**: Basic and deep health endpoints (including SMTP connectivity)
- **Correlation IDs**: Request tracking across services
- **Comprehensive Logging**: Structured logging for debugging and monitoring

## Architecture

```
mabel/
├── app.py                  # Flask application & WSGI entry point
├── config.py               # Configuration loader
├── config.yaml             # Service configuration
├── .env.example            # Environment variables template
├── requirements.txt        # Python dependencies
├── api/
│   ├── email.py           # Email sending endpoints
│   └── health.py          # Health check endpoints
├── services/
│   ├── email_models.py    # Pydantic models for validation
│   ├── email_sender.py    # SMTP email sending logic
│   └── templates.py       # Jinja2 template rendering
├── templates/
│   └── emails/            # Jinja2 email templates
│       ├── example_welcome.txt.j2
│       └── example_welcome.html.j2
└── tests/
    ├── unit/              # Unit tests
    └── integration/       # Integration tests
```

## Configuration

### 1. Environment Variables

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Required environment variables:

**Note**: `BOT_API_KEY` is defined in the root `.env` file (shared by all bots in the bot-team ecosystem) and is automatically loaded via `shared/config/env_loader.py`.

```bash
# Flask secret key (generate a random string)
FLASK_SECRET_KEY=your-secret-key-here

# SMTP credentials
EMAIL_SMTP_USERNAME=your-smtp-username@example.com
EMAIL_SMTP_PASSWORD=your-smtp-password
```

### 2. Configuration File

Edit `config.yaml` to customize:

- Server settings (host, port, log level)
- Default email addresses (from, reply-to, sender name)
- SMTP server settings (host, port, TLS)

```yaml
name: mabel
description: "Email-sending bot for the bot-team"
version: "0.1.0"

server:
  host: "0.0.0.0"
  port: 8010
  log_level: "INFO"

email:
  default_from: "no-reply@example.com"
  default_reply_to: "support@example.com"
  default_sender_name: "Bot Team"
  smtp:
    host: "smtp.example.com"
    port: 587
    use_tls: true
```

## Installation

### Prerequisites

- Python 3.8+
- SMTP server access (or email provider credentials)

### Setup

1. **Clone and navigate to the mabel directory**:

```bash
cd mabel
```

2. **Create and activate virtual environment**:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**:

```bash
pip install -r requirements.txt
```

4. **Configure environment**:

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

5. **Update config.yaml** with your SMTP settings

## Running Mabel

### Development Mode

```bash
# Using Flask development server
python app.py

# Or using flask run
flask run --host=0.0.0.0 --port=8010
```

### Production Mode

```bash
# Using Gunicorn (recommended)
gunicorn -w 4 -b 0.0.0.0:8010 "app:app"

# With more workers and timeout
gunicorn -w 8 -b 0.0.0.0:8010 --timeout 120 "app:app"
```

### Using systemd (Production Deployment)

Create `/etc/systemd/system/mabel.service`:

```ini
[Unit]
Description=Mabel Email Bot
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/path/to/mabel
Environment="PATH=/path/to/mabel/.venv/bin"
ExecStart=/path/to/mabel/.venv/bin/gunicorn -w 4 -b 0.0.0.0:8010 "app:app"
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable mabel
sudo systemctl start mabel
```

## API Documentation

### Authentication

All API endpoints (except `/health` and `/health/deep`) require authentication via the `X-Internal-Api-Key` header:

```bash
X-Internal-Api-Key: your-internal-api-key
```

### Endpoints

#### `POST /api/send-email`

Send a single email.

**Request Headers**:
- `Content-Type: application/json`
- `X-Internal-Api-Key: <your-api-key>`
- `X-Correlation-Id: <optional-correlation-id>` (optional, for tracking)

**Request Body**:

```json
{
  "to": ["recipient@example.com"],
  "cc": ["cc@example.com"],
  "bcc": ["bcc@example.com"],
  "subject": "Hello from Mabel",
  "text_body": "Plain text version",
  "html_body": "<p>HTML version</p>",
  "from_address": "custom@example.com",
  "from_name": "Custom Sender",
  "template": "example_welcome",
  "template_vars": {
    "user_name": "Derek"
  },
  "attachments": [
    {
      "filename": "report.pdf",
      "content_type": "application/pdf",
      "content_base64": "base64encodedcontent..."
    }
  ],
  "metadata": {
    "caller": "pam",
    "correlation_id": "123-abc",
    "tags": ["welcome"]
  }
}
```

**Field Requirements**:
- `to` (required): String or array of email addresses
- `subject` (required): Email subject
- At least ONE of: `text_body`, `html_body`, or `template`
- `cc`, `bcc`, `from_address`, `from_name` (optional)
- `template` (optional): Template name from `templates/emails/`
- `template_vars` (optional): Variables to pass to template
- `attachments` (optional): Array of attachment objects
- `metadata` (optional): Additional tracking information

**Response** (200 OK):

```json
{
  "status": "sent",
  "message_id": "generated-message-id",
  "to": ["recipient@example.com"],
  "subject": "Hello from Mabel",
  "provider": "smtp"
}
```

**Error Responses**:
- `401 Unauthorized`: Missing or invalid API key
- `400 Bad Request`: Validation error (invalid email, missing fields)
- `502 Bad Gateway`: SMTP send failed

#### `POST /api/send-batch`

Send multiple emails in a batch.

**Request Body**:

```json
{
  "emails": [
    {
      "to": "user1@example.com",
      "subject": "Email 1",
      "text_body": "Body 1"
    },
    {
      "to": "user2@example.com",
      "subject": "Email 2",
      "text_body": "Body 2"
    }
  ]
}
```

**Response** (200 OK):

```json
{
  "status": "completed",
  "total": 2,
  "success_count": 2,
  "failure_count": 0,
  "results": [
    {
      "index": 0,
      "status": "sent",
      "message_id": "msg-id-1",
      "to": ["user1@example.com"],
      "subject": "Email 1"
    },
    {
      "index": 1,
      "status": "sent",
      "message_id": "msg-id-2",
      "to": ["user2@example.com"],
      "subject": "Email 2"
    }
  ]
}
```

#### `GET /health`

Basic health check (no authentication required).

**Response** (200 OK):

```json
{
  "status": "ok",
  "name": "mabel",
  "version": "0.1.0",
  "uptime_seconds": 1234.56
}
```

#### `GET /health/deep`

Deep health check with SMTP connectivity test (no authentication required).

**Response** (200 OK):

```json
{
  "status": "ok",
  "name": "mabel",
  "version": "0.1.0",
  "uptime_seconds": 1234.56,
  "smtp_ok": true,
  "details": {
    "smtp_host": "smtp.example.com",
    "smtp_port": 587,
    "smtp_use_tls": true,
    "smtp_test_duration_ms": 123.45
  }
}
```

**Response** (503 Service Unavailable) - if SMTP is down:

```json
{
  "status": "degraded",
  "smtp_ok": false,
  ...
}
```

## Usage Examples

### Simple Text Email

```bash
curl -X POST http://localhost:8010/api/send-email \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $BOT_API_KEY" \
  -d '{
    "to": "user@example.com",
    "subject": "Test Email",
    "text_body": "This is a test email from Mabel.",
    "metadata": {"caller": "test-script"}
  }'
```

### HTML Email with Template

```bash
curl -X POST http://localhost:8010/api/send-email \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $BOT_API_KEY" \
  -d '{
    "to": ["newuser@example.com"],
    "subject": "Welcome to Our Service",
    "template": "example_welcome",
    "template_vars": {
      "user_name": "Alice"
    },
    "metadata": {
      "caller": "user-registration-bot",
      "correlation_id": "reg-12345"
    }
  }'
```

### Email with Attachment

```bash
# First, base64 encode your file
FILE_CONTENT=$(base64 -w 0 document.pdf)

curl -X POST http://localhost:8010/api/send-email \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $BOT_API_KEY" \
  -d "{
    \"to\": \"client@example.com\",
    \"subject\": \"Your Document\",
    \"text_body\": \"Please find your document attached.\",
    \"attachments\": [
      {
        \"filename\": \"document.pdf\",
        \"content_type\": \"application/pdf\",
        \"content_base64\": \"$FILE_CONTENT\"
      }
    ]
  }"
```

### Batch Send

```bash
curl -X POST http://localhost:8010/api/send-batch \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $BOT_API_KEY" \
  -d '{
    "emails": [
      {
        "to": "user1@example.com",
        "subject": "Newsletter #1",
        "template": "newsletter",
        "template_vars": {"content": "News 1"}
      },
      {
        "to": "user2@example.com",
        "subject": "Newsletter #2",
        "template": "newsletter",
        "template_vars": {"content": "News 2"}
      }
    ]
  }'
```

## Creating Email Templates

Templates are stored in `templates/emails/` and use Jinja2 syntax.

### Template Files

For a template named `welcome`, create:
- `templates/emails/welcome.txt.j2` (plain text version)
- `templates/emails/welcome.html.j2` (HTML version)

You can have both or just one variant.

### Example Template

**`templates/emails/welcome.txt.j2`**:

```jinja2
Hello {{ user_name }},

Welcome to {{ service_name }}!

We're excited to have you on board.

Best regards,
The Team
```

**`templates/emails/welcome.html.j2`**:

```jinja2
<!DOCTYPE html>
<html>
<body>
  <h1>Welcome, {{ user_name }}!</h1>
  <p>We're excited to have you on board at <strong>{{ service_name }}</strong>.</p>
  <p>Best regards,<br>The Team</p>
</body>
</html>
```

### Using the Template

```json
{
  "to": "user@example.com",
  "subject": "Welcome!",
  "template": "welcome",
  "template_vars": {
    "user_name": "Alice",
    "service_name": "Bot Team"
  }
}
```

## Testing

### Run All Tests

```bash
pytest
```

### Run with Coverage

```bash
pytest --cov=. --cov-report=html
```

### Run Specific Test Suites

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/unit/test_email_models.py
```

### Test Structure

- **Unit Tests**: Test individual components in isolation
  - `test_email_models.py`: Email validation logic
  - `test_email_sender.py`: SMTP sending logic (mocked)
  - `test_templates.py`: Template rendering

- **Integration Tests**: Test API endpoints end-to-end
  - `test_send_email_endpoint.py`: Email sending API
  - `test_health_endpoint.py`: Health check endpoints

## Integration with Other Bots

Other bots in the bot-team ecosystem can use Mabel by:

1. **Using the shared API key**: All bots share the `BOT_API_KEY` from the root `.env` file
2. **Making HTTP requests**: Use the `/api/send-email` endpoint
3. **Including correlation IDs**: Use `X-Correlation-Id` header for request tracking

### Python Example

```python
import os
import requests

MABEL_URL = "http://mabel:8010"
API_KEY = os.getenv("BOT_API_KEY")

def send_email(to, subject, body, correlation_id=None):
    headers = {
        "X-Internal-Api-Key": API_KEY,
        "Content-Type": "application/json"
    }

    if correlation_id:
        headers["X-Correlation-Id"] = correlation_id

    payload = {
        "to": to,
        "subject": subject,
        "text_body": body,
        "metadata": {
            "caller": "my-bot"
        }
    }

    response = requests.post(
        f"{MABEL_URL}/api/send-email",
        json=payload,
        headers=headers
    )

    return response.json()
```

## Security Considerations

- **API Key**: Keep `BOT_API_KEY` secret and rotate regularly (shared across all bots in root `.env`)
- **SMTP Credentials**: Never log or expose `EMAIL_SMTP_PASSWORD`
- **Input Validation**: All inputs are validated via Pydantic models
- **Template Auto-escaping**: Jinja2 auto-escaping prevents XSS in HTML emails
- **Error Redaction**: SMTP errors are redacted in API responses (logged server-side only)
- **HTTPS**: Use HTTPS/TLS in production (configure via reverse proxy like Nginx)

## Troubleshooting

### SMTP Connection Issues

1. Check SMTP credentials in `.env`
2. Verify SMTP server allows connections from your IP
3. Test with `/health/deep` endpoint
4. Check logs for detailed error messages

### Email Not Sending

1. Verify API key is correct
2. Check request validation errors (400 responses)
3. Review Mabel logs for SMTP errors
4. Ensure `to` addresses are valid

### Template Not Found

1. Verify template files exist in `templates/emails/`
2. Check filename matches template name + `.txt.j2` or `.html.j2`
3. Ensure template directory is correctly configured

## Logging

Mabel logs:
- All incoming API requests (method, path, status, duration)
- Email send attempts (recipients, subject, result, duration)
- SMTP connection issues
- Validation errors

Logs include correlation IDs for cross-service tracing.

**Log Level**: Set in `config.yaml` under `server.log_level` (DEBUG, INFO, WARNING, ERROR)

## Future Enhancements

Potential improvements (not yet implemented):

- Email provider abstraction (SendGrid, Mailgun, AWS SES)
- Email queue with retry logic
- Rate limiting per caller
- Email tracking (opens, clicks)
- Template preview endpoint
- Scheduled/delayed sending
- Database for email audit trail

## License

Part of the bot-team ecosystem.

## Support

For issues or questions, contact the bot-team maintainers.
