"""
Monica Web Routes
Dashboard and agent page
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Blueprint, render_template_string, request
from collections import defaultdict
import logging

from monica.database.db import db
from monica.services.status_service import status_service
from monica.config import config
from monica.services.auth import login_required

logger = logging.getLogger(__name__)

web_bp = Blueprint('web', __name__)


@web_bp.route('/')
@login_required
def index():
    """Home page - redirects to dashboard"""
    from flask import redirect, url_for
    return redirect(url_for('web.dashboard'))


@web_bp.route('/help')
@login_required
def help_page():
    """Help page with setup instructions"""
    template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="noindex, nofollow">
    <title>Help - {{ config.name }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 48px;
            max-width: 800px;
            width: 100%;
        }
        h1 {
            font-size: 2.5em;
            margin-bottom: 16px;
            color: #1f2937;
        }
        p.subtitle {
            color: #6b7280;
            line-height: 1.6;
            margin-bottom: 32px;
            font-size: 1.1em;
        }
        .section {
            margin: 32px 0;
            padding: 24px;
            background: #f9fafb;
            border-radius: 12px;
            border-left: 4px solid #667eea;
        }
        .section h2 {
            font-size: 1.3em;
            color: #1f2937;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .section p {
            color: #6b7280;
            line-height: 1.6;
            margin-bottom: 16px;
        }
        .section.device {
            border-left-color: #10b981;
        }
        .btn {
            display: inline-block;
            padding: 12px 24px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.3s;
            font-size: 1em;
        }
        .btn:hover {
            background: #5a67d8;
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
        }
        .instructions {
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 16px;
            border-radius: 8px;
            margin-top: 16px;
        }
        .instructions h3 {
            font-size: 1em;
            color: #92400e;
            margin-bottom: 8px;
            font-weight: 700;
        }
        .instructions p {
            color: #78350f;
            font-size: 0.95em;
            margin-bottom: 8px;
        }
        .instructions code {
            background: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
            color: #92400e;
        }
        .back-link {
            display: inline-block;
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
            margin-bottom: 24px;
        }
        .back-link:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">← Back to Dashboard</a>
        <h1>📡 {{ config.name }} Help</h1>
        <p class="subtitle">{{ config.description }}</p>

        <div class="section device">
            <h2>📡 For Staff Devices: Install Monitoring Agent</h2>
            <p>Monitor your stores using the Monica Chrome extension. Secure registration with one-time codes.</p>

            <div class="instructions">
                <h3>Step 1: Generate Registration Code</h3>
                <p><strong>1.</strong> Go to the <a href="/" style="color: #667eea; text-decoration: underline;">Dashboard</a></p>
                <p><strong>2.</strong> Click "Generate Registration Code" button</p>
                <p><strong>3.</strong> Enter store code and device name</p>
                <p><strong>4.</strong> Copy the generated code (valid for 24 hours)</p>
            </div>

            <div class="instructions" style="margin-top: 16px;">
                <h3>Step 2: Install Chrome Extension</h3>
                <p><strong>1.</strong> Install Monica Store Monitor from Chrome Web Store</p>
                <p><strong>2.</strong> Click the extension icon in your browser toolbar</p>
                <p><strong>3.</strong> Enter the configuration:</p>
                <p>&nbsp;&nbsp;&nbsp;• Monica URL: <code>{{ request.url_root }}</code></p>
                <p>&nbsp;&nbsp;&nbsp;• Registration Code: <code>(from Step 1)</code></p>
                <p>&nbsp;&nbsp;&nbsp;• Store Code: <code>FYSHWICK</code></p>
                <p>&nbsp;&nbsp;&nbsp;• Device Name: <code>Front Counter</code></p>
                <p><strong>4.</strong> Click "Save & Start Monitoring"</p>
                <p><strong>5.</strong> Grant permission when prompted</p>
                <p style="margin-top: 12px; color: #059669;"><strong>✓ Runs in background even when tabs are closed</strong></p>
                <p style="color: #059669;"><strong>✓ Secure one-time codes prevent unauthorized access</strong></p>
                <p style="color: #059669;"><strong>✓ Automatic heartbeats every 60 seconds</strong></p>
            </div>
        </div>
    </div>
</body>
</html>
    """
    return render_template_string(template, config=config)


@web_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard showing all devices with traffic-light status"""
    # Get all devices with store info
    devices = db.get_all_devices_with_stores()

    # Enrich with computed status
    enriched_devices = [status_service.enrich_device(d) for d in devices]

    # Group by store
    stores = defaultdict(list)
    for device in enriched_devices:
        store_code = device['store_code']
        stores[store_code].append(device)

    # Sort stores and devices
    sorted_stores = sorted(stores.items(), key=lambda x: x[0])

    template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="noindex, nofollow">
    <title>📊 Dashboard - {{ config.name }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f3f4f6;
            padding: 20px;
            min-height: 100vh;
        }
        .header {
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }
        h1 {
            font-size: 2em;
            color: #1f2937;
        }
        .refresh-info {
            color: #6b7280;
            font-size: 0.9em;
        }
        .store-section {
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .store-header {
            font-size: 1.5em;
            color: #1f2937;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 2px solid #e5e7eb;
        }
        .devices-grid {
            display: grid;
            gap: 16px;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        }
        .device-card {
            border: 2px solid #e5e7eb;
            border-radius: 8px;
            padding: 16px;
            transition: all 0.3s;
        }
        .device-card:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            transform: translateY(-2px);
        }
        .device-card.online { border-left: 4px solid #10b981; }
        .device-card.degraded { border-left: 4px solid #f59e0b; }
        .device-card.offline { border-left: 4px solid #ef4444; }
        .device-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 12px;
            justify-content: space-between;
        }
        .device-title {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .device-name {
            font-size: 1.2em;
            font-weight: 600;
            color: #1f2937;
        }
        .delete-btn {
            background: #ef4444;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.85em;
            cursor: pointer;
            transition: all 0.2s;
            font-weight: 600;
        }
        .delete-btn:hover {
            background: #dc2626;
            transform: scale(1.05);
        }
        .device-info {
            font-size: 0.9em;
            color: #6b7280;
            line-height: 1.6;
        }
        .device-info strong {
            color: #1f2937;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }
        .status-badge.online {
            background: #d1fae5;
            color: #065f46;
        }
        .status-badge.degraded {
            background: #fef3c7;
            color: #92400e;
        }
        .status-badge.offline {
            background: #fee2e2;
            color: #991b1b;
        }
        .empty-state {
            text-align: center;
            padding: 48px;
            color: #9ca3af;
        }
        .empty-state h2 {
            margin-bottom: 16px;
        }
        .empty-state p {
            margin-bottom: 12px;
        }
        .empty-state code {
            background: #f3f4f6;
            padding: 8px 16px;
            border-radius: 6px;
            font-family: monospace;
            color: #1f2937;
            display: inline-block;
            margin: 8px 0;
        }
        .empty-state-icon {
            font-size: 4em;
            margin-bottom: 16px;
        }
        .back-link {
            display: inline-block;
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
            margin-top: 16px;
        }
        .back-link:hover {
            text-decoration: underline;
        }
        .legend {
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 12px 16px;
            margin: 16px 0;
            max-width: fit-content;
        }
        .legend-label {
            font-size: 0.75em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #9ca3af;
            margin-bottom: 8px;
        }
        .legend-items {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 0.85em;
            color: #6b7280;
        }
        .legend-item span {
            font-size: 0.9em;
            opacity: 0.8;
        }
        .btn-generate {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 0.95em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            white-space: nowrap;
        }
        .btn-generate:hover {
            background: #5a67d8;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        .modal.active {
            display: flex;
        }
        .modal-content {
            background: white;
            border-radius: 12px;
            padding: 32px;
            max-width: 500px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }
        .modal-header {
            font-size: 1.5em;
            font-weight: 700;
            margin-bottom: 20px;
            color: #1f2937;
        }
        .form-group {
            margin-bottom: 16px;
        }
        .form-group label {
            display: block;
            font-weight: 600;
            margin-bottom: 8px;
            color: #1f2937;
        }
        .form-group input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e5e7eb;
            border-radius: 8px;
            font-size: 1em;
            transition: border-color 0.2s;
        }
        .form-group input:focus {
            outline: none;
            border-color: #667eea;
        }
        .modal-actions {
            display: flex;
            gap: 12px;
            margin-top: 24px;
        }
        /* Toast notification styles */
        .toast-container {
            position: fixed;
            top: 24px;
            right: 24px;
            z-index: 10000;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .toast {
            background: white;
            border-radius: 8px;
            padding: 16px 20px;
            min-width: 300px;
            max-width: 400px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            display: flex;
            align-items: center;
            gap: 12px;
            animation: slideIn 0.3s ease-out;
        }
        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        .toast.success {
            border-left: 4px solid #10b981;
        }
        .toast.error {
            border-left: 4px solid #ef4444;
        }
        .toast.info {
            border-left: 4px solid #3b82f6;
        }
        .toast-icon {
            font-size: 1.5em;
        }
        .toast-message {
            flex: 1;
            font-size: 0.95em;
            color: #1f2937;
        }
        /* Confirmation modal styles */
        .confirm-modal .modal-content {
            max-width: 450px;
        }
        .confirm-message {
            color: #374151;
            line-height: 1.6;
            margin-bottom: 24px;
        }
        .confirm-device-name {
            font-weight: 600;
            color: #1f2937;
        }
        .btn-danger {
            background: #ef4444;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 1em;
            cursor: pointer;
            transition: all 0.2s;
            font-weight: 600;
        }
        .btn-danger:hover {
            background: #dc2626;
            transform: scale(1.05);
        }
        .btn-primary {
            flex: 1;
            background: #667eea;
            color: white;
            border: none;
            padding: 12px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-primary:hover {
            background: #5a67d8;
        }
        .btn-secondary {
            flex: 1;
            background: #e5e7eb;
            color: #1f2937;
            border: none;
            padding: 12px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-secondary:hover {
            background: #d1d5db;
        }
        .code-display {
            background: #f3f4f6;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            margin: 20px 0;
        }
        .code-value {
            font-size: 2em;
            font-weight: 700;
            color: #667eea;
            font-family: monospace;
            letter-spacing: 2px;
        }
        .code-info {
            margin-top: 12px;
            color: #6b7280;
            font-size: 0.9em;
        }
        .copy-btn {
            background: #10b981;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 12px;
            transition: all 0.2s;
        }
        .copy-btn:hover {
            background: #059669;
        }
    </style>
    <script>
        // Auto-refresh every {{ config.auto_refresh }} seconds
        let autoRefreshTimer = setTimeout(function() {
            location.reload();
        }, {{ config.auto_refresh * 1000 }});

        // Track if a code was generated (to refresh immediately on modal close)
        let codeWasGenerated = false;

        // Track when tab becomes hidden to detect stale data
        let tabBecameHiddenAt = null;

        // Page Visibility API - refresh when tab becomes visible again if data might be stale
        document.addEventListener('visibilitychange', function() {
            if (document.hidden) {
                // Tab is now hidden - record the time
                tabBecameHiddenAt = Date.now();
            } else {
                // Tab is now visible again
                if (tabBecameHiddenAt) {
                    const hiddenDuration = (Date.now() - tabBecameHiddenAt) / 1000;
                    // If tab was hidden for more than the auto-refresh interval, refresh immediately
                    if (hiddenDuration > {{ config.auto_refresh }}) {
                        console.log(`Tab was hidden for ${hiddenDuration.toFixed(0)}s, refreshing...`);
                        location.reload();
                    }
                }
                tabBecameHiddenAt = null;
            }
        });

        // Show toast notification
        function showToast(message, type = 'success') {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;

            const icons = {
                success: '✓',
                error: '✕',
                info: 'ℹ'
            };

            toast.innerHTML = `
                <div class="toast-icon">${icons[type] || icons.info}</div>
                <div class="toast-message">${message}</div>
            `;

            container.appendChild(toast);

            // Auto remove after 4 seconds
            setTimeout(() => {
                toast.style.animation = 'slideIn 0.3s ease-out reverse';
                setTimeout(() => toast.remove(), 300);
            }, 4000);
        }

        // Show confirmation modal
        function showConfirmModal(message, onConfirm) {
            const modal = document.getElementById('confirm-modal');
            document.getElementById('confirm-message').innerHTML = message;
            modal.classList.add('active');

            // Set up confirm button
            const confirmBtn = document.getElementById('confirm-btn');
            confirmBtn.onclick = () => {
                modal.classList.remove('active');
                onConfirm();
            };
        }

        // Hide confirmation modal
        function hideConfirmModal() {
            document.getElementById('confirm-modal').classList.remove('active');
        }

        // Delete device
        function deleteDevice(deviceId, deviceName) {
            showConfirmModal(
                `Are you sure you want to delete <span class="confirm-device-name">"${deviceName}"</span>?<br><br>This will remove the device and all its heartbeat history.`,
                async () => {
                    try {
                        const response = await fetch(`/api/devices/${deviceId}`, {
                            method: 'DELETE'
                        });

                        const data = await response.json();

                        if (data.success) {
                            showToast(`Device "${deviceName}" deleted successfully`, 'success');
                            // Clear auto-refresh timer and reload after a brief delay
                            clearTimeout(autoRefreshTimer);
                            setTimeout(() => location.reload(), 800);
                        } else {
                            showToast(`Failed to delete device: ${data.error}`, 'error');
                        }
                    } catch (error) {
                        showToast(`Error deleting device: ${error.message}`, 'error');
                    }
                }
            );
        }

        // Show generate code modal
        function showGenerateCodeModal() {
            // Pause auto-refresh while modal is open
            clearTimeout(autoRefreshTimer);
            codeWasGenerated = false; // Reset flag
            document.getElementById('generate-modal').classList.add('active');
            document.getElementById('modal-form').style.display = 'block';
            document.getElementById('modal-result').style.display = 'none';
        }

        // Hide modal
        function hideModal() {
            document.getElementById('generate-modal').classList.remove('active');
            document.getElementById('store-code-input').value = '';
            document.getElementById('device-label-input').value = '';

            // If a code was generated, refresh immediately to see new devices register
            // Otherwise resume normal auto-refresh schedule
            if (codeWasGenerated) {
                setTimeout(() => location.reload(), 500); // Brief delay for modal close animation
            } else {
                autoRefreshTimer = setTimeout(function() {
                    location.reload();
                }, {{ config.auto_refresh * 1000 }});
            }
        }

        // Generate registration code
        async function generateCode() {
            const storeCode = document.getElementById('store-code-input').value.trim().toUpperCase();
            const deviceLabel = document.getElementById('device-label-input').value.trim();

            if (!storeCode || !deviceLabel) {
                showToast('Please enter both store code and device name', 'error');
                return;
            }

            try {
                const response = await fetch('/api/registration-codes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        store_code: storeCode,
                        device_label: deviceLabel
                    })
                });

                const data = await response.json();

                if (data.success) {
                    // Show the generated code
                    codeWasGenerated = true; // Mark that we generated a code
                    document.getElementById('modal-form').style.display = 'none';
                    document.getElementById('modal-result').style.display = 'block';
                    document.getElementById('generated-code').textContent = data.code;
                    document.getElementById('code-store').textContent = data.store_code;
                    document.getElementById('code-device').textContent = data.device_label;
                } else {
                    showToast(`Failed to generate code: ${data.error}`, 'error');
                }
            } catch (error) {
                showToast(`Error generating code: ${error.message}`, 'error');
            }
        }

        // Copy code to clipboard
        function copyCode(btn) {
            const code = document.getElementById('generated-code').textContent;
            navigator.clipboard.writeText(code).then(() => {
                const originalText = btn.textContent;
                btn.textContent = '✓ Copied!';
                setTimeout(() => {
                    btn.textContent = originalText;
                }, 2000);
            });
        }
    </script>
</head>
<body>
    <div class="header">
        <div>
            <h1>📊 Device Dashboard</h1>
            <div style="display: flex; gap: 16px; margin-top: 8px;">
                <a href="/help" class="back-link">❓ Help</a>
                <a href="/logout" class="back-link">👋 Logout</a>
            </div>
        </div>
        <div style="display: flex; gap: 16px; align-items: center;">
            <button onclick="showGenerateCodeModal()" class="btn-generate">🔑 Generate Registration Code</button>
            <div class="refresh-info">Auto-refreshes every {{ config.auto_refresh }}s</div>
        </div>
    </div>

    <div class="legend">
        <div class="legend-label">Status Guide (for reference)</div>
        <div class="legend-items">
            <div class="legend-item">
                <span>🟢</span> <strong>Online:</strong> Last seen ≤ {{ config.online_threshold }} min
            </div>
            <div class="legend-item">
                <span>🟡</span> <strong>Degraded:</strong> Last seen {{ config.online_threshold }}-{{ config.degraded_threshold }} min
            </div>
            <div class="legend-item">
                <span>🔴</span> <strong>Offline:</strong> Last seen > {{ config.degraded_threshold }} min
            </div>
        </div>
    </div>

    {% if stores %}
        {% for store_code, store_devices in stores %}
        <div class="store-section">
            <div class="store-header">
                🏪 {{ store_code }}
            </div>
            <div class="devices-grid">
                {% for device in store_devices %}
                <div class="device-card {{ device.computed_status }}">
                    <div class="device-header">
                        <div class="device-title">
                            <span style="font-size: 1.5em;">{{ device.status_emoji }}</span>
                            <div class="device-name">{{ device.device_label }}</div>
                        </div>
                        <button class="delete-btn" onclick="deleteDevice({{ device.id }}, '{{ device.device_label }}')">Delete</button>
                    </div>
                    <div class="device-info">
                        <strong>Status:</strong>
                        <span class="status-badge {{ device.computed_status }}">
                            {{ device.status_label }}
                        </span>
                        <br>
                        <strong>Last seen:</strong> {{ device.last_seen_text }}<br>
                        {% if device.last_public_ip %}
                        <strong>IP:</strong> {{ device.last_public_ip }}<br>
                        {% endif %}
                        {% if device.last_heartbeat_at %}
                        <strong>Timestamp:</strong> {{ device.last_heartbeat_at }}<br>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endfor %}
    {% else %}
        <div class="store-section">
            <div class="empty-state">
                <div class="empty-state-icon">📡</div>
                <h2>No devices registered yet</h2>
                <p>To register a device, click "Generate Registration Code" above, then install the Chrome extension.</p>
                <a href="/help" class="back-link">❓ View Setup Instructions</a>
            </div>
        </div>
    {% endif %}

    <!-- Generate Registration Code Modal -->
    <div id="generate-modal" class="modal">
        <div class="modal-content">
            <!-- Form to input store and device -->
            <div id="modal-form">
                <div class="modal-header">🔑 Generate Registration Code</div>
                <div class="form-group">
                    <label for="store-code-input">Store Code</label>
                    <input type="text" id="store-code-input" placeholder="FYSHWICK" style="text-transform: uppercase;">
                </div>
                <div class="form-group">
                    <label for="device-label-input">Device Name</label>
                    <input type="text" id="device-label-input" placeholder="Front Counter">
                </div>
                <div class="modal-actions">
                    <button class="btn-secondary" onclick="hideModal()">Cancel</button>
                    <button class="btn-primary" onclick="generateCode()">Generate Code</button>
                </div>
            </div>

            <!-- Result display after generation -->
            <div id="modal-result" style="display: none;">
                <div class="modal-header">✓ Registration Code Generated</div>
                <div class="code-display">
                    <div class="code-value" id="generated-code">ABC12345</div>
                    <button class="copy-btn" onclick="copyCode(this)">📋 Copy Code</button>
                    <div class="code-info">
                        For: <strong><span id="code-store"></span> / <span id="code-device"></span></strong><br>
                        Expires in 24 hours
                    </div>
                </div>
                <p style="color: #6b7280; margin-bottom: 16px;">
                    This code can only be used once. Give it to the staff member who will configure the extension.
                </p>
                <div class="modal-actions">
                    <button class="btn-primary" onclick="hideModal()">Done</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Confirmation Modal -->
    <div id="confirm-modal" class="modal confirm-modal">
        <div class="modal-content">
            <div class="modal-header">⚠️ Confirm Delete</div>
            <div id="confirm-message" class="confirm-message"></div>
            <div class="modal-actions">
                <button class="btn-secondary" onclick="hideConfirmModal()">Cancel</button>
                <button id="confirm-btn" class="btn-danger">Delete</button>
            </div>
        </div>
    </div>

    <!-- Toast Container -->
    <div id="toast-container" class="toast-container"></div>
</body>
</html>
    """
    return render_template_string(template, config=config, stores=sorted_stores)


@web_bp.route('/agent')
def agent():
    """Agent page for ChromeOS devices to register and send heartbeats"""
    store_code = request.args.get('store', '')
    device_label = request.args.get('device', '')

    template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="noindex, nofollow">
    <title>📡 {{ config.name }} Agent</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .agent-container {
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 48px;
            max-width: 600px;
            width: 100%;
        }
        h1 {
            font-size: 2.5em;
            margin-bottom: 16px;
            color: #1f2937;
            text-align: center;
        }
        .status-indicator {
            text-align: center;
            padding: 24px;
            border-radius: 12px;
            margin: 24px 0;
            font-size: 1.2em;
            font-weight: 600;
        }
        .status-indicator.initializing {
            background: #dbeafe;
            color: #1e40af;
        }
        .status-indicator.connected {
            background: #d1fae5;
            color: #065f46;
        }
        .status-indicator.disconnected {
            background: #fee2e2;
            color: #991b1b;
        }
        .info-grid {
            display: grid;
            gap: 16px;
            margin: 24px 0;
        }
        .info-item {
            padding: 16px;
            background: #f9fafb;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .info-label {
            font-size: 0.85em;
            color: #6b7280;
            margin-bottom: 4px;
        }
        .info-value {
            font-size: 1.1em;
            color: #1f2937;
            font-weight: 600;
        }
        .metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 16px;
            margin: 24px 0;
        }
        .metric-card {
            padding: 16px;
            background: #f3f4f6;
            border-radius: 8px;
            text-align: center;
        }
        .metric-label {
            font-size: 0.85em;
            color: #6b7280;
            margin-bottom: 8px;
        }
        .metric-value {
            font-size: 1.8em;
            font-weight: 700;
            color: #1f2937;
        }
        .logs {
            margin-top: 24px;
            padding: 16px;
            background: #1f2937;
            color: #10b981;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            max-height: 200px;
            overflow-y: auto;
        }
        .log-entry {
            margin: 4px 0;
        }
        .log-time {
            color: #6b7280;
        }
        .error-message {
            background: #fee2e2;
            color: #991b1b;
            padding: 16px;
            border-radius: 8px;
            margin: 16px 0;
        }
        .pulse {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #10b981;
            margin-right: 8px;
            animation: pulse 2s ease-in-out infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
    </style>
</head>
<body>
    <div class="agent-container">
        <h1>📡 Monitoring Agent</h1>

        <div id="status" class="status-indicator initializing">
            <span class="pulse"></span>
            <span id="status-text">Initializing...</span>
        </div>

        <div class="info-grid">
            <div class="info-item">
                <div class="info-label">Store</div>
                <div class="info-value" id="store-name">{{ store_code or 'Not specified' }}</div>
            </div>
            <div class="info-item">
                <div class="info-label">Device</div>
                <div class="info-value" id="device-name">{{ device_label or 'Not specified' }}</div>
            </div>
            <div class="info-item">
                <div class="info-label">Device ID</div>
                <div class="info-value" id="device-id">-</div>
            </div>
        </div>

        <div class="metrics">
            <div class="metric-card">
                <div class="metric-label">Heartbeats Sent</div>
                <div class="metric-value" id="heartbeat-count">0</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Latency (ms)</div>
                <div class="metric-value" id="latency">-</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Speed (Mbps)</div>
                <div class="metric-value" id="speed">-</div>
            </div>
        </div>

        <div id="error-container"></div>

        <div class="logs" id="logs">
            <div class="log-entry">Agent starting...</div>
        </div>
    </div>

    <script>
        // Configuration
        const STORE_CODE = "{{ store_code }}";
        const DEVICE_LABEL = "{{ device_label }}";
        const HEARTBEAT_INTERVAL = {{ config.heartbeat_interval * 1000 }};  // ms
        const NETWORK_TEST_INTERVAL = {{ config.network_test_interval * 1000 }};  // ms
        const NETWORK_TEST_FILE_SIZE = {{ config.network_test_file_size }};  // bytes

        // State
        let agentToken = null;
        let deviceId = null;
        let heartbeatCount = 0;
        let heartbeatTimer = null;
        let networkTestTimer = null;
        let lastLatency = null;
        let lastSpeed = null;

        // Logging
        function log(message) {
            const logs = document.getElementById('logs');
            const time = new Date().toLocaleTimeString();
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.innerHTML = `<span class="log-time">[${time}]</span> ${message}`;
            logs.appendChild(entry);
            logs.scrollTop = logs.scrollHeight;
        }

        function setStatus(status, text) {
            const statusDiv = document.getElementById('status');
            const statusText = document.getElementById('status-text');
            statusDiv.className = `status-indicator ${status}`;
            statusText.textContent = text;
        }

        function showError(message) {
            const errorContainer = document.getElementById('error-container');
            errorContainer.innerHTML = `<div class="error-message">⚠️ ${message}</div>`;
        }

        function clearError() {
            document.getElementById('error-container').innerHTML = '';
        }

        // Registration
        async function register() {
            if (!STORE_CODE || !DEVICE_LABEL) {
                showError('Missing store or device parameters in URL. Example: /agent?store=FYSHWICK&device=Front%20Counter');
                setStatus('disconnected', 'Configuration Error');
                return false;
            }

            // Check if already registered
            const stored = localStorage.getItem('monica_agent');
            if (stored) {
                try {
                    const data = JSON.parse(stored);
                    if (data.store_code === STORE_CODE && data.device_label === DEVICE_LABEL) {
                        agentToken = data.agent_token;
                        deviceId = data.device_id;
                        document.getElementById('device-id').textContent = deviceId;
                        log('✓ Loaded existing registration from storage');
                        return true;
                    }
                } catch (e) {
                    log('⚠ Could not parse stored registration, re-registering');
                }
            }

            // Register with server
            log('Registering with server...');
            try {
                const response = await fetch('/api/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        store_code: STORE_CODE,
                        device_label: DEVICE_LABEL
                    })
                });

                const data = await response.json();
                if (data.success) {
                    agentToken = data.agent_token;
                    deviceId = data.device_id;

                    // Save to localStorage
                    localStorage.setItem('monica_agent', JSON.stringify({
                        store_code: STORE_CODE,
                        device_label: DEVICE_LABEL,
                        agent_token: agentToken,
                        device_id: deviceId
                    }));

                    document.getElementById('device-id').textContent = deviceId;
                    log(`✓ Registered successfully (ID: ${deviceId})`);
                    return true;
                } else {
                    throw new Error(data.error || 'Registration failed');
                }
            } catch (error) {
                log(`✗ Registration failed: ${error.message}`);
                showError(`Registration failed: ${error.message}`);
                return false;
            }
        }

        // Heartbeat
        async function sendHeartbeat() {
            if (!agentToken) {
                log('✗ Cannot send heartbeat: not registered');
                return;
            }

            try {
                const payload = {
                    timestamp: new Date().toISOString()
                };

                // Include network metrics if available
                if (lastLatency !== null) {
                    payload.latency_ms = lastLatency;
                }
                if (lastSpeed !== null) {
                    payload.download_mbps = lastSpeed;
                }

                const response = await fetch('/api/heartbeat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Agent-Token': agentToken
                    },
                    body: JSON.stringify(payload)
                });

                const data = await response.json();
                if (data.success) {
                    heartbeatCount++;
                    document.getElementById('heartbeat-count').textContent = heartbeatCount;
                    setStatus('connected', '🟢 Connected');
                    clearError();
                    log(`♥ Heartbeat #${heartbeatCount} sent`);
                } else {
                    throw new Error(data.error || 'Heartbeat failed');
                }
            } catch (error) {
                log(`✗ Heartbeat failed: ${error.message}`);
                setStatus('disconnected', '🔴 Disconnected');
                showError(`Connection error: ${error.message}`);
            }
        }

        // Network test
        async function runNetworkTest() {
            log('Running network test...');

            // Latency test: measure round-trip time to /health endpoint
            try {
                const start = performance.now();
                const response = await fetch('/health', { cache: 'no-store' });
                const end = performance.now();

                if (response.ok) {
                    lastLatency = Math.round(end - start);
                    document.getElementById('latency').textContent = lastLatency;
                    log(`✓ Latency: ${lastLatency}ms`);
                }
            } catch (error) {
                log(`✗ Latency test failed: ${error.message}`);
            }

            // Speed test: download a test payload
            // For MVP, we'll create a simple test by downloading data
            // In production, you'd want a dedicated test file endpoint
            try {
                const start = performance.now();
                // Generate random data of specified size
                const testData = new Array(NETWORK_TEST_FILE_SIZE / 8).fill(0).map(() =>
                    Math.random().toString(36).substring(2, 15)
                ).join('');
                const blob = new Blob([testData]);
                const url = URL.createObjectURL(blob);

                const response = await fetch(url);
                const arrayBuffer = await response.arrayBuffer();
                const end = performance.now();

                const durationSeconds = (end - start) / 1000;
                const sizeMb = arrayBuffer.byteLength / (1024 * 1024);
                lastSpeed = (sizeMb / durationSeconds).toFixed(2);

                document.getElementById('speed').textContent = lastSpeed;
                log(`✓ Download speed: ${lastSpeed} Mbps`);

                URL.revokeObjectURL(url);
            } catch (error) {
                log(`✗ Speed test failed: ${error.message}`);
            }
        }

        // Initialize
        async function init() {
            log('Monica Agent v{{ config.version }}');
            log(`Store: ${STORE_CODE}, Device: ${DEVICE_LABEL}`);

            // Register
            const registered = await register();
            if (!registered) {
                setStatus('disconnected', '⚠️ Registration Failed');
                return;
            }

            // Send initial heartbeat
            await sendHeartbeat();

            // Run initial network test
            await runNetworkTest();

            // Start periodic heartbeats
            heartbeatTimer = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL);
            log(`✓ Heartbeat timer started (every ${HEARTBEAT_INTERVAL / 1000}s)`);

            // Start periodic network tests
            networkTestTimer = setInterval(runNetworkTest, NETWORK_TEST_INTERVAL);
            log(`✓ Network test timer started (every ${NETWORK_TEST_INTERVAL / 1000}s)`);
        }

        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            if (heartbeatTimer) clearInterval(heartbeatTimer);
            if (networkTestTimer) clearInterval(networkTestTimer);
        });

        // Start agent
        init();
    </script>
</body>
</html>
    """
    return render_template_string(template, config=config, store_code=store_code, device_label=device_label)


@web_bp.route('/robots.txt')
def robots():
    """Block search engine crawlers"""
    return """User-agent: *
Disallow: /
""", 200, {'Content-Type': 'text/plain'}
