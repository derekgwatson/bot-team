# Monica Monitor - Quick Start Guide

Get your Chrome extension up and running in 10 minutes!

## Step 1: Test Locally First (5 minutes)

Before publishing to Chrome Web Store, test that everything works:

### Load the Extension

1. Open Chrome
2. Go to `chrome://extensions/`
3. Turn on **Developer mode** (toggle in top-right)
4. Click **Load unpacked**
5. Navigate to and select the `monica-chrome-extension` folder
6. You should see "Monica Store Monitor" appear in your extensions

### Configure It

1. Click the extension icon in your Chrome toolbar (or click the puzzle piece → Monica Store Monitor)
2. Fill in the configuration:
   - **Monica Server URL**: `http://localhost:8015` (or wherever Monica is running)
   - **Store Code**: `TEST` (or your actual store code)
   - **Device Name**: `Test Device`
3. Click **Save & Start Monitoring**

### Verify It Works

1. The popup should show "Connected and monitoring"
2. Open Monica dashboard at `http://localhost:8015/dashboard`
3. You should see your test device appear with a green status
4. Wait 60 seconds and the heartbeat count should increase

**If it works, you're ready for Chrome Web Store!** 🎉

---

## Step 2: Publish to Chrome Web Store (5 minutes)

### One-Time Setup (First time only)

1. Go to https://chrome.google.com/webstore/devconsole
2. Sign in with your Google account
3. Pay the $5 developer registration fee (one-time, forever)
4. Accept the developer agreement

### Upload Your Extension

1. In the [Developer Dashboard](https://chrome.google.com/webstore/devconsole), click **New Item**
2. Upload the `monica-monitor.zip` file (already created in parent directory)
3. Click **Continue**

### Fill in Store Listing

#### Store Listing Tab

**Item Name**: Monica Store Monitor

**Summary** (short description):
```
Monitor store network connectivity with automatic heartbeats to your Monica server.
```

**Description** (detailed):
```
Monica Store Monitor automatically monitors network connectivity for retail stores.

✓ Automatic heartbeat every 60 seconds
✓ Network speed and latency testing
✓ Background monitoring (no tabs needed)
✓ Simple one-time configuration
✓ View all stores on Monica dashboard

Perfect for multi-location retail businesses needing reliable connectivity monitoring.

Setup in 30 seconds:
1. Install extension
2. Enter your Monica server URL and store details
3. Done! View status on Monica dashboard

No accounts required - works with your own Monica server.
```

**Category**: Productivity

**Language**: English (or your language)

#### Privacy Practices Tab

**Single purpose**: Monitoring store network connectivity

**Host permissions justification**:
```
Required to communicate with user's self-hosted Monica monitoring server for sending heartbeats and network metrics.
```

**Privacy policy**: You'll need to host a privacy policy. Options:
- Create a simple GitHub Gist (free and easy)
- Add a page to your website
- Use the template from README.md

**Quick privacy policy** (copy this to a public URL):
```
This extension sends data only to your own Monica server that you configure.
We do not collect, store, or access any of your data. All communication is
between your browser and your server.
```

#### Graphics Tab

**Icon**: Already set (128x128 icon from your extension)

**Screenshots** (at least 1 required):
- Take a screenshot of the configuration popup
- Take a screenshot of the status display
- Screenshot size: 1280x800 or 640x400

**To take screenshots**:
1. Load the extension
2. Click the icon to open popup
3. Use your OS screenshot tool (or Chrome DevTools)
4. Crop to 640x400 or 1280x800

#### Distribution Tab

**Visibility**: Choose one:
- **Public**: Anyone can find it in Chrome Web Store (good for showing off!)
- **Unlisted**: Only people with the link can install (good for internal use)
- **Private**: Only specific Google Groups (requires Google Workspace)

**For your use case, I recommend UNLISTED** - keeps it professional but not searchable by random people.

**Regions**: All regions (or select specific countries)

### Submit for Review

1. Click **Submit for Review** (bottom right)
2. Wait 1-3 days for review
3. You'll get an email when approved

---

## Step 3: Deploy to Staff (30 seconds per person)

### Once Published - Simple Deployment

**You get a link like**: `https://chrome.google.com/webstore/detail/[extension-id]`

**Send this to staff with instructions**:

```
Hi team!

Please install our store monitor:

1. Click this link: [YOUR_CHROME_WEB_STORE_LINK]
2. Click "Add to Chrome"
3. Click the extension icon (puzzle piece → Monica Store Monitor)
4. Enter these details:
   - Monica URL: http://[YOUR_MONICA_SERVER]:8015
   - Store Code: [THEIR_STORE_CODE]
   - Device Name: [THEIR_DEVICE_NAME]
5. Click Save

That's it! Leave Chrome running and it'll monitor automatically.
```

### Pre-Configuration (Advanced)

If you have Google Workspace, you can push the extension with pre-filled settings:

1. Google Admin Console → Devices → Chrome → Apps & Extensions
2. Add your extension
3. Set policy to Force Install
4. Configure URLs in policy JSON:
```json
{
  "monicaUrl": {"Value": "http://your-server:8015"},
  "storeCode": {"Value": "FYSHWICK"}
}
```

Then staff don't configure anything - it just works!

---

## Tips for Success

### Better Icons (Optional but Recommended)

Current icons are simple purple squares. For a professional look:

1. Use [Figma](https://figma.com) or [Canva](https://canva.com)
2. Create a simple radar/monitoring icon design
3. Export as PNG in sizes: 16x16, 32x32, 48x48, 128x128
4. Replace files in `icons/` folder
5. Re-zip and re-upload

### Testing Different Stores

Test with multiple configurations:
```
Store 1: FYSHWICK / Front Counter
Store 2: FYSHWICK / Back Office
Store 3: BELCONNEN / Front Counter
```

Each should appear separately on Monica dashboard.

### Troubleshooting

**Extension not appearing in toolbar?**
- Click puzzle piece icon → Pin "Monica Store Monitor"

**Can't connect to Monica?**
- Check Monica is running: `http://localhost:8015/health`
- Check firewall settings
- Use the actual server IP/domain, not localhost (if Monica is on different machine)

**Heartbeats not showing on dashboard?**
- Wait 60 seconds for first heartbeat
- Check extension popup for errors
- Check Monica logs

---

## Success Checklist

- [ ] Extension loads in developer mode
- [ ] Configuration popup works
- [ ] Device appears on Monica dashboard
- [ ] Heartbeat count increases
- [ ] Registered Chrome Web Store developer account
- [ ] Extension uploaded to Chrome Web Store
- [ ] Store listing filled out
- [ ] Privacy policy created and linked
- [ ] Screenshots uploaded
- [ ] Extension submitted for review
- [ ] Approval email received
- [ ] Chrome Web Store link shared with staff

---

## What's Next?

Once deployed:

1. **Monitor the dashboard** - See all your stores in one place
2. **Show management** - Demo the live dashboard with traffic lights
3. **Get feedback** - Staff will love how easy it is
4. **Iterate** - Add features based on what you learn

## Questions?

- Check the full README.md for detailed documentation
- View Chrome DevTools console for extension logs
- Check Monica dashboard for device status

---

**You're all set! Good luck with your Chrome Web Store debut! 🚀**
