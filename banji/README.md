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

### `POST /api/quotes/refresh-pricing`

Refresh pricing for a quote and return before/after comparison.

**Request:**
```json
{
  "quote_id": "Q-12345"
}
```

**Response:**
```json
{
  "success": true,
  "quote_id": "Q-12345",
  "price_before": 1000.00,
  "price_after": 1200.00,
  "price_changed": true,
  "change_amount": 200.00,
  "change_percent": 20.0
}
```

**Authentication:** Requires `X-API-Key` header with valid `BOT_API_KEY`.

## Configuration

### Environment Variables

Required:
- `BUZ_BASE_URL` - Base URL for Buz application (e.g., https://buz.example.com)
- `BUZ_USERNAME` - Buz login username
- `BUZ_PASSWORD` - Buz login password
- `BOT_API_KEY` - Shared API key for bot-to-bot communication

Optional:
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

# Edit .env with your Buz credentials
nano banji/.env
```

### 3. Run Banji

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

⚠️ **Important:** The page objects currently use **placeholder selectors**. You'll need to:

1. Inspect the actual Buz application UI
2. Identify stable selectors for:
   - Login form fields and button
   - Quote page total price element
   - Bulk edit button
   - Save button
   - Success indicators
3. Update the selectors in:
   - `services/quotes/login_page.py`
   - `services/quotes/quote_page.py`

Look for elements with `data-testid`, `id`, or stable `class` attributes. Avoid selectors that might break when Buz's UI changes.

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

### "Login failed - timeout"
- Check `BUZ_BASE_URL` is correct
- Verify credentials in `.env`
- Update login selectors in `login_page.py`
- Try headed mode to see what's happening: `BUZ_HEADLESS=false`

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

### Calling Banji from Another Bot

```python
from shared.http_client import BotHttpClient

# Initialize client
banji = BotHttpClient("http://localhost:8014")

# Refresh quote pricing
response = banji.post('/api/quotes/refresh-pricing', {
    'quote_id': 'Q-12345'
})

if response['success']:
    if response['price_changed']:
        print(f"⚠️ Price changed!")
        print(f"  Before: ${response['price_before']}")
        print(f"  After: ${response['price_after']}")
        print(f"  Change: {response['change_percent']}%")
    else:
        print("✓ Price unchanged")
```

### Scheduled Price Checks (Example)

```python
# Example orchestrator bot that checks quotes daily
import schedule

def check_open_quotes():
    # Get open quotes from Buz API or database
    quotes = get_open_quotes()

    for quote in quotes:
        # Call Banji to refresh pricing
        result = banji.post('/api/quotes/refresh-pricing', {
            'quote_id': quote['id']
        })

        if result['price_changed']:
            # Alert someone about the price change
            send_alert(f"Quote {quote['id']} price changed by {result['change_percent']}%")

# Schedule daily at 9 AM
schedule.every().day.at("09:00").do(check_open_quotes)
```

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
