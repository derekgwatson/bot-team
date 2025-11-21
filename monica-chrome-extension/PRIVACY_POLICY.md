# Privacy Policy for Monica Store Monitor

**Last Updated:** November 21, 2024

## Overview

Monica Store Monitor is a Chrome extension designed to monitor network connectivity for retail stores by sending periodic heartbeats to a self-hosted Monica monitoring server. This privacy policy explains what data we collect, how we use it, and your rights regarding that data.

## Data We Collect

Monica Store Monitor collects and processes the following data:

### 1. Configuration Data
- **Monica Server URL**: The URL of your self-hosted Monica monitoring server
- **Store Code**: Your store location identifier (e.g., "FYSHWICK")
- **Device Label**: A name you assign to identify the device (e.g., "Front Counter")

This data is provided by you during initial setup.

### 2. Authentication Data
- **Agent Token**: An automatically generated authentication token created by your Monica server
- **Device ID**: A unique identifier assigned by your Monica server

These are generated automatically during device registration and are used to authenticate subsequent communications.

### 3. Network Performance Data
- **Heartbeat Timestamps**: The date and time when heartbeats are sent
- **Network Latency**: Round-trip time to your Monica server (in milliseconds)
- **Download Speed**: Estimated network download speed (in Mbps)
- **Public IP Address**: Your device's public IP address (captured by the Monica server)
- **User Agent**: Browser identification string (captured by the Monica server)

## How We Use Your Data

All data collected by this extension is used solely for the following purposes:

1. **Monitoring Network Connectivity**: To determine if your store's internet connection is operational
2. **Performance Metrics**: To measure network quality and identify potential issues
3. **Device Identification**: To distinguish between different monitoring devices in your dashboard

## Where Your Data Goes

**All data is sent exclusively to YOUR self-configured Monica monitoring server.**

- We (the extension developers) do NOT receive, collect, store, or have access to any of your data
- Data is sent directly from the extension to the Monica server URL you configure
- No third-party services, analytics platforms, or advertising networks are used
- No data is shared with anyone except your own Monica server

## Data Storage

### Local Storage
Configuration data and authentication tokens are stored locally on your device using Chrome's `storage.local` API. This data:
- Remains on your device only
- Persists across browser restarts
- Is deleted when you uninstall the extension

### Remote Storage
Heartbeat data sent to your Monica server is stored according to your Monica server's configuration and retention policies. We have no control over or access to this data.

## Data Security

### In Transit
- Data transmission security depends on your Monica server configuration
- If you configure an HTTPS URL, all communications are encrypted in transit
- If you use HTTP, communications are unencrypted (we recommend HTTPS)

### At Rest
- Configuration data stored locally in Chrome's secure storage API
- Your Monica server's data security is managed by your own infrastructure

## Third-Party Access

**We do not share, sell, or transmit your data to any third parties.**

The extension communicates exclusively with the Monica server URL you configure. There are no:
- Analytics services
- Advertising networks
- Third-party APIs
- External tracking services
- Data brokers or aggregators

## Your Rights

You have the following rights regarding your data:

### Right to Access
You can view all locally stored data by inspecting Chrome's storage for this extension.

### Right to Deletion
You can delete all data by:
- Uninstalling the extension (removes all local data immediately)
- Clearing Chrome's extension data
- Requesting deletion from your Monica server administrator

### Right to Modification
You can reconfigure the extension at any time by clicking the extension icon and using the "Reconfigure" button.

### Right to Data Portability
Since data is stored on your own Monica server, you have full control and can export it according to your server's capabilities.

## Children's Privacy

This extension is not directed at children under the age of 13. We do not knowingly collect data from children. This extension is designed for business/enterprise use in retail environments.

## Changes to This Policy

We may update this privacy policy from time to time. Changes will be reflected by updating the "Last Updated" date at the top of this policy. Continued use of the extension after changes constitutes acceptance of the updated policy.

## Open Source

This extension's source code is available for review, ensuring transparency in how your data is handled.

## Contact Information

If you have questions or concerns about this privacy policy or data handling practices, please contact:

**Email**: [YOUR EMAIL HERE]
**GitHub**: [YOUR GITHUB REPO URL]

## Compliance

This extension complies with:
- Chrome Web Store Developer Program Policies
- General Data Protection Regulation (GDPR) principles
- California Consumer Privacy Act (CCPA) principles

## Summary

**In plain English:**
- You configure where data goes (your own server)
- We don't see or store any of your data
- You control everything
- No third parties involved
- Delete anytime by uninstalling

---

**Monica Store Monitor** is developed for internal business use to monitor store connectivity. All data remains under your control.
