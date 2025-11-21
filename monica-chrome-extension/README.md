# Monica Store Monitor - Chrome Extension

A Chrome extension that monitors store network connectivity and sends heartbeats to the Monica monitoring service.

## Features

- 🔄 Automatic heartbeat monitoring (every 60 seconds)
- 📊 Network latency and speed testing (every 5 minutes)
- 🎯 Background monitoring (no need to keep tabs open)
- 📱 Simple configuration popup
- 💾 Persistent settings across browser restarts

## Installation for Testing (Developer Mode)

### Option 1: Test Locally

1. Open Chrome and go to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right corner)
3. Click **Load unpacked**
4. Select the `monica-chrome-extension` folder
5. The extension will appear in your extensions list

### Option 2: Load from ZIP

1. Create a ZIP file: `zip -r monica-monitor.zip . -x "*.py" -x "README.md" -x ".git/*"`
2. Open Chrome and go to `chrome://extensions/`
3. Enable **Developer mode**
4. Click **Load unpacked**
5. Extract the ZIP and select the folder

## Configuration

1. Click the extension icon in your Chrome toolbar
2. Enter the following information:
   - **Monica Server URL**: The URL where Monica is running (e.g., `http://localhost:8015`)
   - **Store Code**: Your store location code (e.g., `FYSHWICK`)
   - **Device Name**: A label for this device (e.g., `Front Counter`)
3. Click **Save & Start Monitoring**

The extension will:
- Test the connection to Monica
- Register the device automatically
- Start sending heartbeats every 60 seconds
- Run network tests every 5 minutes

## How It Works

### Background Service Worker

The extension uses a Chrome service worker that runs in the background, even when you don't have any Monica tabs open. It:

1. **Registers** with the Monica server on first run
2. **Stores** the agent token securely in Chrome storage
3. **Sends heartbeats** every 60 seconds via `/api/heartbeat`
4. **Tests network** every 5 minutes:
   - Latency test (ping to `/health` endpoint)
   - Download speed test (simplified)

### Permissions

The extension requires:
- `storage` - To save your configuration and agent token
- `alarms` - To schedule periodic heartbeats and network tests
- `host_permissions` - To communicate with your Monica server

## Publishing to Chrome Web Store

### Prerequisites

1. **Google Account** with Chrome Web Store developer access
2. **$5 USD** one-time developer registration fee (paid to Google)
3. **Privacy Policy** (see template below)

### Step 1: Register as Chrome Web Store Developer

1. Go to [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole)
2. Sign in with your Google account
3. Pay the $5 one-time registration fee
4. Accept the developer agreement

### Step 2: Prepare Your Extension Package

1. **Review the manifest** (`manifest.json`) - make sure all details are correct
2. **Update icons** (optional but recommended):
   - Current icons are simple purple placeholders
   - Replace `icons/icon*.png` with professionally designed icons
   - Use tools like [Figma](https://figma.com) or [Canva](https://canva.com)
3. **Create a ZIP package**:
   ```bash
   cd /home/user/bot-team
   zip -r monica-monitor.zip monica-chrome-extension \
     -x "monica-chrome-extension/*.py" \
     -x "monica-chrome-extension/README.md" \
     -x "monica-chrome-extension/.git/*"
   ```

### Step 3: Create Store Listing Assets

You'll need to create the following for the Chrome Web Store listing:

#### Required Images

1. **Icon (128x128)** - Already created at `icons/icon128.png`
2. **Small promotional tile (440x280)** - Optional but recommended
3. **Screenshots (1280x800 or 640x400)** - At least 1 required
   - Take screenshots of the configuration popup
   - Take screenshots of the status display

#### Store Listing Information

**Name**: Monica Store Monitor

**Summary** (132 characters max):
```
Monitors store network connectivity and sends heartbeats to Monica monitoring service.
```

**Description**:
```
Monica Store Monitor is a lightweight Chrome extension that helps you monitor network connectivity across your retail stores.

Features:
• Automatic heartbeat monitoring every 60 seconds
• Network latency and speed testing every 5 minutes
• Background monitoring - no need to keep tabs open
• Simple configuration popup
• Works seamlessly with Monica monitoring dashboard

Perfect for retail environments where you need reliable connectivity monitoring without dedicated hardware.

How to use:
1. Install the extension
2. Click the icon and configure your Monica server URL, store code, and device name
3. The extension automatically registers and starts monitoring
4. View all your stores on the Monica dashboard

No accounts or sign-ups required - just point it at your Monica server and go!
```

**Category**: Productivity

**Language**: English

**Privacy Policy**: See template below

### Step 4: Upload to Chrome Web Store

1. Go to [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole)
2. Click **New Item**
3. Upload your `monica-monitor.zip` file
4. Fill in the store listing information (use content from Step 3)
5. Upload screenshots and promotional images
6. Set the **visibility** (Public, Unlisted, or Private)
   - **Unlisted**: Best for internal use - only people with the link can install
   - **Public**: Anyone can find and install from Chrome Web Store
7. Click **Submit for Review**

### Step 5: Review Process

- **Review time**: Usually 1-3 business days
- **Automated checks**: Chrome runs automated policy checks
- **Manual review**: Google may manually review your extension
- **Possible outcomes**:
  - ✅ Approved and published
  - ⚠️ Rejected with feedback (you can fix and resubmit)

### Privacy Policy Template

You'll need a privacy policy URL. Here's a template you can host anywhere (GitHub, your website, etc.):

```markdown
# Privacy Policy for Monica Store Monitor

Last updated: [DATE]

## What Data We Collect

Monica Store Monitor collects the following data:
- Store code (configured by you)
- Device label (configured by you)
- Monica server URL (configured by you)
- Network latency measurements
- Network download speed measurements
- Heartbeat timestamps

## How We Use Data

All data collected by this extension is sent directly to YOUR Monica monitoring server that you configure. We (the extension developers) do not collect, store, or have access to any of your data.

The extension operates entirely between your browser and your own Monica server.

## Data Storage

Configuration and agent tokens are stored locally in Chrome's storage API and never leave your device except when communicating with your configured Monica server.

## Third-Party Services

This extension does not use any third-party analytics, advertising, or tracking services.

## Contact

For questions about this privacy policy, contact: [YOUR EMAIL]
```

## Deployment to Staff

Once published to Chrome Web Store:

### For Unlisted Extension

1. Get the extension URL from the Chrome Web Store
2. Send the link to staff
3. Staff clicks link → **Add to Chrome** → Done!

### For Google Workspace (Auto-Install)

If you have Google Workspace admin access:

1. Go to [Google Admin Console](https://admin.google.com)
2. Navigate to **Devices** → **Chrome** → **Apps & Extensions**
3. Click **Add app or extension**
4. Enter your extension ID
5. Set to **Force install** for specific users/groups
6. Configure pre-filled settings (Monica URL, store code) via policy

## Troubleshooting

### Extension not showing in toolbar
- Click the puzzle piece icon in Chrome
- Find "Monica Store Monitor"
- Click the pin icon to pin it to toolbar

### "Cannot connect to Monica server" error
- Check the Monica server URL is correct
- Make sure Monica is running and accessible
- Check for firewall/network issues

### Heartbeats not being sent
- Open the extension popup to check status
- Look for error messages
- Try reconfiguring the extension

### View extension logs
1. Go to `chrome://extensions/`
2. Enable Developer mode
3. Click "service worker" under Monica Store Monitor
4. View console logs in DevTools

## Development

### Files Structure

```
monica-chrome-extension/
├── manifest.json       # Extension manifest (Chrome v3)
├── background.js       # Service worker (heartbeat logic)
├── popup.html         # Configuration/status popup UI
├── popup.js           # Popup logic
├── icons/             # Extension icons
│   ├── icon16.png
│   ├── icon32.png
│   ├── icon48.png
│   └── icon128.png
└── README.md          # This file
```

### Testing Changes

1. Make your code changes
2. Go to `chrome://extensions/`
3. Click the refresh icon on the Monica Store Monitor card
4. Test the changes

### Updating Published Extension

1. Make your changes
2. Update version number in `manifest.json`
3. Create new ZIP package
4. Go to Chrome Web Store Developer Dashboard
5. Click on your extension
6. Click "Upload updated package"
7. Submit for review

## Support

For issues or questions:
- Check the Monica dashboard at `[MONICA_URL]/dashboard`
- View extension logs (see Troubleshooting section)
- Contact your IT administrator

## License

[Your license here]
