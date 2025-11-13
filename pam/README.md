# Pam - Phone Directory Presenter

Pam is your friendly phone directory bot. She presents the company phone directory in a beautiful, easy-to-use format for everyone in the organization.

## What Pam Does

Pam is the public-facing interface for your phone directory. Think of her as the receptionist - she helps everyone find contact information quickly and easily.

**Key Features:**
- Beautiful card-based directory layout
- Search functionality (by name, position, or extension)
- Organized by department
- Click-to-call and click-to-email links
- Read-only access (safe for company-wide use)
- Mobile responsive design

## How Pam Works

Pam gets her data from **Peter** (the phone directory manager). She doesn't access the Google Sheet directly - instead, she calls Peter's API. This creates a clean separation:

- **Peter** = Admin tool (manages data, writes to Google Sheets)
- **Pam** = Public viewer (presents data beautifully, read-only)

```
Google Sheet <-> Peter (API) <-> Pam (Web UI)
```

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Pam:**
   Edit `config.yaml` to point to Peter's API URL (default: `http://localhost:8003`)

3. **Make sure Peter is running:**
   Pam needs Peter to be running on port 8003 to get contact data

4. **Run Pam:**
   ```bash
   python app.py
   ```

5. **Access Pam:**
   - Web UI: http://localhost:8004
   - API: http://localhost:8004/api/intro
   - Health: http://localhost:8004/health

## Endpoints

### Web UI
- `/` - Browse the phone directory
- `/search` - Search for contacts

### API
- `GET /api/intro` - Get Pam's introduction and capabilities
- `GET /health` - Health check
- `GET /info` - Bot information

## Architecture

Pam follows the Unix philosophy: **do one thing well**

- **Single responsibility:** Present the phone directory beautifully
- **No data management:** Peter handles all CRUD operations
- **API-driven:** Gets data from Peter's API
- **Read-only:** Safe for company-wide access

## Design

Pam uses a warm coral/red color scheme with:
- Card-based layout (not tables!)
- Generous whitespace
- Icons for contact methods (📞 📱 ✉️)
- Prominent extension badges
- Position titles clearly visible
- Smooth hover effects

Perfect for company-wide deployment - everyone can access Pam to find contact info!
