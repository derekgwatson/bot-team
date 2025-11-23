# Mavis - Unleashed Data Integration Bot

Mavis syncs product data from the Unleashed API and serves it to other bots in a stable, normalized format.

## Purpose

- Pull product data from Unleashed API on demand
- Store data in local SQLite database with a clean, normalized schema
- Provide REST endpoints so other bots can query Unleashed data without talking to Unleashed directly

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `UNLEASHED_API_ID` | Yes | Your Unleashed API ID |
| `UNLEASHED_API_KEY` | Yes | Your Unleashed API Key |
| `UNLEASHED_BASE_URL` | No | Override Unleashed API URL (default: `https://api.unleashedsoftware.com`) |
| `FLASK_SECRET_KEY` | Yes | Flask session secret key |
| `BOT_API_KEY` | Yes | Shared API key for bot-to-bot communication |

Copy `.env.example` to `.env` and fill in the values.

## Endpoints

### System Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check with sync status |
| `GET /info` | Bot information |

### API Endpoints (require `X-API-Key` header)

| Endpoint | Description |
|----------|-------------|
| `GET /api/intro` | Bot introduction and capabilities |
| `POST /api/sync/run` | Trigger a full product sync |
| `GET /api/sync/status` | Get current sync status |
| `GET /api/sync/history` | Get sync history |
| `GET /api/products?code=XXX` | Get a product by code |
| `POST /api/products/bulk` | Bulk lookup products by codes |
| `GET /api/products/changed-since?timestamp=XXX` | Get products changed since timestamp |
| `GET /api/products/stats` | Get product statistics |

## Usage Examples

### Trigger a sync

```bash
curl -X POST http://localhost:8017/api/sync/run \
  -H "X-API-Key: your-bot-api-key"
```

### Get a product

```bash
curl http://localhost:8017/api/products?code=FAB123 \
  -H "X-API-Key: your-bot-api-key"
```

### Bulk lookup

```bash
curl -X POST http://localhost:8017/api/products/bulk \
  -H "X-API-Key: your-bot-api-key" \
  -H "Content-Type: application/json" \
  -d '{"codes": ["FAB001", "FAB002", "FAB003"]}'
```

### Get changed products

```bash
curl "http://localhost:8017/api/products/changed-since?timestamp=2025-01-01T00:00:00Z" \
  -H "X-API-Key: your-bot-api-key"
```

## Running

### Development

```bash
cd mavis
python app.py
```

### Production (via Gunicorn)

```bash
gunicorn -w 2 -b 0.0.0.0:8017 app:app
```

## Database

SQLite database stored at `database/mavis.db`. Schema is automatically initialized on startup.

### Tables

- `unleashed_products` - Synced product data
- `sync_metadata` - Sync operation history

## Future Expansion

The codebase is designed to support additional sync types:

- Customers
- Sales Orders
- Stock Levels

These can be added by extending `UnleashedClient` and `SyncService`.
