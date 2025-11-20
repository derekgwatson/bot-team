# Banji - Browser Automation for Buz

🎭 **Banji** is a Playwright-powered browser automation bot that interacts with the Buz application through its UI. Banji handles tasks that require browser-based workflows, such as refreshing quote pricing and capturing pricing changes.

## Purpose

Banji serves as the **specialized UI automation layer** for Buz operations. Other bots can call Banji's API to trigger browser-based workflows without needing to know how to interact with Buz's UI themselves.

### Key Philosophy

- **Separation of Concerns**: Banji knows HOW to interact with Buz (browser automation). Other orchestrator bots know WHAT needs to be done (business logic).
- **Centralized Playwright Knowledge**: All browser automation code lives in one place.
- **Modular Growth**: Start with quote operations, expand to other Buz domains as needed (inventory, reports, etc.).

## Architecture

```
┌─────────────────┐
│ Orchestrator    │  (Knows WHAT to do)
│ Bot             │
└────────┬────────┘
         │ API call
         ▼
┌─────────────────┐
│ Banji           │  (Knows HOW to do it)
│ Browser Bot     │
└────────┬────────┘
         │ Playwright
         ▼
┌─────────────────┐
│ Buz Application │
└─────────────────┘
```

## Current Capabilities

### Quote Pricing Refresh

Detect pricing changes in quotes by triggering a bulk edit save (which forces price recalculation).

**Workflow:**
1. Login to Buz
2. Navigate to quote
3. Capture current total price
4. Open bulk edit mode
5. Save (without making changes)
6. Capture updated total price
7. Return comparison

**Use Case:** Proactively detect pricing drift before customers notice. Alert if quote prices have changed due to product price updates.

## API Endpoints

Banji provides **atomic, session-based API** for browser automation. Start a session, perform operations, then close when done.

All endpoints require `X-API-Key` header with valid `BOT_API_KEY`.

### Session Management

#### `POST /api/sessions/start`
Start a new browser session for an organization.

**Request:**
```json
{
  "org": "designer_drapes"
}
```

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "org": "designer_drapes",
  "created_at": "2025-01-20T14:30:22",
  "timeout_minutes": 30
}
```

#### `DELETE /api/sessions/{session_id}`
Close a browser session and free resources.

**Response:**
```json
{
  "session_id": "550e8400-...",
  "status": "closed"
}
```

#### `GET /api/sessions/{session_id}`
Get session information.

**Response:**
```json
{
  "session_id": "550e8400-...",
  "org": "designer_drapes",
  "created_at": "2025-01-20T14:30:22",
  "last_activity": "2025-01-20T14:35:10",
  "current_quote_id": "12345",
  "current_order_pk_id": "9b7b351a-..."
}
```

#### `GET /api/sessions/active`
List all active sessions.

**Response:**
```json
{
  "session_count": 2,
  "sessions": [
    {
      "session_id": "550e8400-...",
      "org": "designer_drapes",
      "created_at": "...",
      "last_activity": "..."
    }
  ]
}
```

### Quote Operations

#### `POST /api/sessions/{session_id}/navigate/quote`
Navigate to a specific quote using Quick Lookup.

**Request:**
```json
{
  "quote_id": "12345"
}
```

**Response:**
```json
{
  "quote_id": "12345",
  "order_pk_id": "9b7b351a-...",
  "current_url": "https://go.buzmanager.com/Sales/Summary?orderId=..."
}
```

#### `GET /api/sessions/{session_id}/quote/total`
Get the total price from current quote summary page.

**Response:**
```json
{
  "total_price": 1234.56,
  "quote_id": "12345"
}
```

#### `POST /api/sessions/{session_id}/bulk-edit/open`
Open bulk edit page for current quote.

**Request (optional):**
```json
{
  "order_pk_id": "9b7b351a-..."
}
```

**Response:**
```json
{
  "status": "bulk_edit_opened",
  "order_pk_id": "9b7b351a-...",
  "current_url": "https://go.buzmanager.com/Sales/BulkEditOrder?..."
}
```

#### `POST /api/sessions/{session_id}/bulk-edit/save`
Click Save button on bulk edit page (triggers price recalculation).

**Response:**
```json
{
  "status": "saved",
  "current_url": "..."
}
```

### Legacy Endpoint

#### `POST /api/quotes/refresh-pricing` (Deprecated)
High-level endpoint that performs entire pricing refresh workflow in one call. Still available for backward compatibility, but new integrations should use session-based API for more control.

## Configuration

### Multi-Organization Support

Buz is multi-tenant - different organizations have different authentication sessions. Banji supports multiple organizations simultaneously, allowing you to work with Designer Drapes, Canberra, Tweed, and other organizations from a single bot instance.

### Authentication Approach

**Banji uses Playwright storage state files** instead of storing passwords. This is more secure and handles complex auth flows:

- ✅ **No passwords in .env files** - Only session tokens
- ✅ **Handles MFA automatically** - Auth happens in real browser during bootstrap
- ✅ **Works with complex flows** - Org selection, multiple domains (go.buzmanager.com, console1.buzmanager.com)
- ✅ **Easy to revoke/regenerate** - Just re-run the bootstrap tool

### Environment Variables

**Required:**
- `BUZ_ORGS` - Comma-separated list of organization names (e.g., `designer_drapes,canberra,tweed`)
- `BOT_API_KEY` - Shared API key for bot-to-bot communication

**For each organization:**
- You need a **storage state file** (not passwords!)
- Files are stored in `.secrets/buz_storage_state_{org_name}.json`
- Generated using the bootstrap tool (see Setup section below)

**Example .env:**
```bash
BUZ_ORGS=designer_drapes,canberra,tweed
BOT_API_KEY=your-bot-api-key-here
```

**Optional:**
- `BUZ_HEADLESS` - Override browser mode (true/false). Defaults to headless in production, headed in development.
- `FLASK_DEBUG` - Enable Flask debug mode (default: False)
- `FLASK_SECRET_KEY` - Flask session secret

See `.env.example` for full configuration template.

### Browser Modes

**Headed Mode (Development):**
- Browser window visible
- Useful for debugging and watching workflows
- Automatically enabled when `FLASK_DEBUG=True`

**Headless Mode (Production):**
- Browser runs in background
- Faster, lower resource usage
- Automatically enabled in production
- Screenshots captured on failures for debugging

## Setup

**For production deployment,** see [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) for detailed Linux server setup instructions.

**For development,** follow the steps below:

### 1. Install Dependencies

From the bot-team root directory:

```bash
# Install Python dependencies (includes Playwright)
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 2. Configure Environment

```bash
# Copy example environment file
cp banji/.env.example banji/.env

# Edit .env - just set BUZ_ORGS with your organization names
nano banji/.env
```

Example `.env`:
```bash
BUZ_ORGS=designer_drapes,canberra,tweed
BOT_API_KEY=your-bot-api-key-here
FLASK_DEBUG=True
```

### 3. Bootstrap Authentication

**For each organization**, run the bootstrap tool to generate the authentication storage state:

```bash
cd banji

# Bootstrap Designer Drapes
python tools/buz_auth_bootstrap.py designer_drapes

# Bootstrap Canberra
python tools/buz_auth_bootstrap.py canberra

# Bootstrap Tweed
python tools/buz_auth_bootstrap.py tweed
```

**What the bootstrap tool does:**
1. Opens a browser window
2. You log in to Buz (including MFA if required)
3. You select the correct organization
4. You navigate to Settings > Users to capture console auth
5. You navigate to console1.buzmanager.com to capture multi-domain auth
6. Tool saves authenticated session to `.secrets/buz_storage_state_{org}.json`

This only needs to be done once per org (or when sessions expire - usually months).

### 4. Run Banji

```bash
# Development mode (headed browser)
cd banji
FLASK_DEBUG=True python app.py

# Production mode (headless browser)
python app.py
```

Banji runs on **port 8014** by default.

## Directory Structure

```
banji/
├── app.py                          # Flask application entry point
├── config.py                       # Configuration loader
├── config.yaml                     # Bot configuration
├── .env.example                    # Environment template
├── api/                            # REST API endpoints
│   └── quote_endpoints.py          # Quote-related endpoints
├── services/                       # Business logic
│   ├── browser.py                  # Browser lifecycle management
│   └── quotes/                     # Quote domain
│       ├── login_page.py           # Buz login page object
│       └── quote_page.py           # Quote page object
├── web/                            # Web interface
│   ├── routes.py                   # Web routes
│   └── templates/
│       └── index.html              # Bot info page
└── screenshots/                    # Debug screenshots (auto-generated)
```

## Extending Banji

### Adding New Buz Domains

When you need to automate additional Buz workflows:

1. **Create domain directory:**
   ```bash
   mkdir -p banji/services/inventory
   ```

2. **Add page objects:**
   ```python
   # banji/services/inventory/inventory_page.py
   class InventoryPage:
       def check_stock(self, item_id):
           # Implementation
   ```

3. **Create API endpoints:**
   ```python
   # banji/api/inventory_endpoints.py
   @inventory_bp.route('/check-stock', methods=['POST'])
   @api_key_required
   def check_stock():
       # Use InventoryPage
   ```

4. **Register blueprint in app.py:**
   ```python
   from api.inventory_endpoints import inventory_bp
   app.register_blueprint(inventory_bp, url_prefix='/api/inventory')
   ```

### Page Object Pattern

Follow this pattern for new pages:

```python
class SomePage:
    def __init__(self, page: Page, config):
        self.page = page
        self.config = config

    def some_action(self):
        # Use Playwright page API
        self.page.locator('selector').click()
        # Wait for results
        self.page.wait_for_load_state("networkidle")
```

**Key Points:**
- Use descriptive selectors (prefer `data-testid`, IDs, or stable classes)
- Add explicit waits for dynamic content
- Extract reusable helpers into shared methods
- Log important steps for debugging

## TODO: Buz UI Selectors

⚠️ **Important:** The quote page objects currently use **placeholder selectors**. You'll need to:

1. Inspect the actual Buz application UI
2. Identify stable selectors for:
   - Quote page total price element
   - Bulk edit button
   - Save button
   - Success indicators (after save completes)
3. Update the selectors in:
   - `services/quotes/quote_page.py`

Look for elements with `data-testid`, `id`, or stable `class` attributes. Avoid selectors that might break when Buz's UI changes.

**Note:** Login is handled via storage state (no form filling needed), so no login selectors required!

## Testing

Run Banji's tests:

```bash
# From bot-team root
pytest tests/unit/test_banji*.py -v
pytest tests/integration/test_banji*.py -v

# With coverage
pytest tests/ --cov=banji --cov-report=html
```

## Troubleshooting

### "Storage state file not found"
- Error: `Storage state file not found for organization 'designer_drapes'`
- Solution: Run the bootstrap tool to generate the auth file:
  ```bash
  python tools/buz_auth_bootstrap.py designer_drapes
  ```

### "Authentication failed" or "redirected to login"
- Storage state (session) may have expired
- Solution: Regenerate the auth file:
  ```bash
  python tools/buz_auth_bootstrap.py designer_drapes
  ```
- Sessions typically last months but can expire earlier

### "Landed on organization selector page"
- Warning during workflow execution
- Storage state is valid but org wasn't selected during bootstrap
- Solution: Regenerate auth file and make sure to click the organization

### "Could not find price element"
- Quote page may have different structure than expected
- Update selectors in `quote_page.py`
- Run in headed mode to inspect the actual page

### Screenshots not saving
- Check `screenshots/` directory exists and is writable
- Verify `browser_screenshot_on_failure: true` in `config.yaml`

### Browser won't launch
- Ensure Playwright browsers installed: `playwright install chromium`
- Check system dependencies: `playwright install-deps chromium`

## Integration Examples

### Session-Based API Usage

**Basic workflow** for checking a single quote:

```python
from shared.http_client import BotHttpClient

# Initialize client
banji = BotHttpClient("http://localhost:8014")

# Start a browser session
session = banji.post('/api/sessions/start', {'org': 'designer_drapes'})
session_id = session['session_id']

try:
    # Navigate to quote
    banji.post(f'/api/sessions/{session_id}/navigate/quote', {
        'quote_id': '12345'
    })

    # Get price before bulk edit
    price_before = banji.get(f'/api/sessions/{session_id}/quote/total')['total_price']

    # Open bulk edit and save (triggers price recalc)
    banji.post(f'/api/sessions/{session_id}/bulk-edit/open')
    banji.post(f'/api/sessions/{session_id}/bulk-edit/save')

    # Navigate back to summary to get updated price
    banji.post(f'/api/sessions/{session_id}/navigate/quote', {
        'quote_id': '12345'
    })
    price_after = banji.get(f'/api/sessions/{session_id}/quote/total')['total_price']

    # Check for price change
    if abs(price_after - price_before) > 0.01:
        print(f"⚠️ Price changed! ${price_before} → ${price_after}")
    else:
        print(f"✓ Price unchanged: ${price_before}")

finally:
    # Always close the session to free browser resources
    banji.delete(f'/api/sessions/{session_id}')
```

### Batch Price Checking with Session Reuse

**Efficient workflow** for checking multiple quotes (reuses same browser session):

```python
from shared.http_client import BotHttpClient

def check_quote_prices(org: str, quote_ids: list):
    """Check pricing for multiple quotes in one browser session."""
    banji = BotHttpClient("http://localhost:8014")

    # Start session once
    session = banji.post('/api/sessions/start', {'org': org})
    session_id = session['session_id']

    results = []

    try:
        for quote_id in quote_ids:
            # Navigate to quote
            banji.post(f'/api/sessions/{session_id}/navigate/quote', {
                'quote_id': quote_id
            })

            # Get price before
            price_before = banji.get(
                f'/api/sessions/{session_id}/quote/total'
            )['total_price']

            # Trigger price recalc via bulk edit
            banji.post(f'/api/sessions/{session_id}/bulk-edit/open')
            banji.post(f'/api/sessions/{session_id}/bulk-edit/save')

            # Get price after
            banji.post(f'/api/sessions/{session_id}/navigate/quote', {
                'quote_id': quote_id
            })
            price_after = banji.get(
                f'/api/sessions/{session_id}/quote/total'
            )['total_price']

            # Calculate change
            change_amount = price_after - price_before
            price_changed = abs(change_amount) > 0.01

            results.append({
                'quote_id': quote_id,
                'price_before': price_before,
                'price_after': price_after,
                'price_changed': price_changed,
                'change_amount': change_amount
            })

    finally:
        # Clean up session
        banji.delete(f'/api/sessions/{session_id}')

    return results


# Usage
results = check_quote_prices('designer_drapes', ['12345', '12346', '12347'])

for result in results:
    if result['price_changed']:
        print(f"⚠️ Quote {result['quote_id']}: "
              f"${result['price_before']} → ${result['price_after']}")
```

### Scheduled Price Monitoring

**Automated monitoring** that runs daily:

```python
import schedule
from shared.http_client import BotHttpClient

def get_open_quotes(org: str):
    """Get list of open quotes from your database or Buz API."""
    # Your implementation here
    return ['12345', '12346', '12347']

def check_daily_pricing():
    """Check pricing for all open quotes across all organizations."""
    banji = BotHttpClient("http://localhost:8014")

    orgs = ['designer_drapes', 'canberra', 'tweed']

    for org in orgs:
        print(f"\nChecking {org}...")

        # Get quotes for this org
        quote_ids = get_open_quotes(org)

        # Check prices
        results = check_quote_prices(org, quote_ids)

        # Alert on changes
        for result in results:
            if result['price_changed']:
                alert_someone(
                    f"[{org}] Quote {result['quote_id']} "
                    f"price changed by ${result['change_amount']:.2f}"
                )

# Run daily at 9 AM
schedule.every().day.at("09:00").do(check_daily_pricing)

# Keep scheduler running
while True:
    schedule.run_pending()
    time.sleep(60)
```

### Simple Commands (Atomic Operations)

Banji's atomic API allows orchestrator bots to issue simple commands:

```python
# Go to quote
banji.post(f'/api/sessions/{sid}/navigate/quote', {'quote_id': '12345'})

# Get total
total = banji.get(f'/api/sessions/{sid}/quote/total')['total_price']

# Open bulk edit
banji.post(f'/api/sessions/{sid}/bulk-edit/open')

# Save
banji.post(f'/api/sessions/{sid}/bulk-edit/save')
```

This aligns with the philosophy: **orchestrator bots know WHAT to do, Banji knows HOW**.

## Contributing

When adding new capabilities to Banji:

1. Create page objects for new UI interactions
2. Add API endpoints following existing patterns
3. Use `@api_key_required` decorator for authentication
4. Log important steps with `logger.info()`
5. Handle errors gracefully and return meaningful messages
6. Update this README with new capabilities
7. Add tests for new functionality

## Related Bots

- **Chester** (port 8008) - Service registry, can discover Banji
- **Oscar** (port 8011) - Example orchestrator bot
- **Dorothy** (port 8005) - Another orchestrator example

## Resources

- [Playwright Python Docs](https://playwright.dev/python/docs/intro)
- [Page Object Pattern](https://playwright.dev/python/docs/pom)
- [Selectors Guide](https://playwright.dev/python/docs/selectors)
- [Bot Team Architecture](../README.md)
