from flask import Blueprint, render_template_string, request, jsonify
from flask_login import current_user
from config import config
from services.auth import login_required

web_bp = Blueprint('web', __name__)

@web_bp.route('/')
@login_required
def index():
    """Dorothy's home page"""
    # Get all bots with defaults applied
    bots = {name: config.get_bot_config(name) for name in config.bots.keys()}

    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dorothy - Deployment Orchestrator</title>
        <meta name="robots" content="noindex, nofollow">
        <meta name="googlebot" content="noindex, nofollow">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .header {
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                color: white;
                padding: 30px;
                border-radius: 10px;
                margin-bottom: 30px;
                position: relative;
            }
            .header h1 { margin: 0 0 10px 0; }
            .header p { margin: 0; opacity: 0.9; }
            .user-info {
                position: absolute;
                top: 20px;
                right: 30px;
                text-align: right;
                font-size: 0.9em;
            }
            .user-email {
                margin-bottom: 8px;
                opacity: 0.9;
            }
            .btn-logout {
                background: rgba(255,255,255,0.2);
                color: white;
                border: 1px solid rgba(255,255,255,0.3);
                padding: 6px 16px;
                border-radius: 4px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                font-size: 0.85em;
            }
            .btn-logout:hover {
                background: rgba(255,255,255,0.3);
            }
            .card {
                background: white;
                padding: 25px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }
            .bots { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; }
            .bot-card {
                background: white;
                padding: 20px;
                border-radius: 8px;
                border-left: 4px solid #f5576c;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .bot-card h3 { margin: 0 0 10px 0; color: #f5576c; }
            .bot-card .info { color: #666; font-size: 0.9em; margin: 5px 0; }
            .bot-card .actions { margin-top: 15px; display: flex; gap: 8px; flex-wrap: wrap; }
            .btn {
                padding: 6px 12px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 0.85em;
                font-weight: bold;
            }
            .btn-verify { background: #4CAF50; color: white; }
            .btn-plan { background: #FF9800; color: white; }
            .btn-deploy { background: #f5576c; color: white; }
            .btn-update { background: #9C27B0; color: white; }
            .btn-start-service { background: #00BCD4; color: white; }
            .btn-health { background: #2196F3; color: white; }
            .btn-teardown { background: #DC3545; color: white; }
            .btn:hover { opacity: 0.9; }
            .plan-step {
                background: #f8f9fa;
                padding: 15px;
                margin: 10px 0;
                border-radius: 5px;
                border-left: 3px solid #FF9800;
            }
            .plan-step h4 { margin: 0 0 10px 0; color: #FF9800; }
            .plan-command {
                background: #2d2d2d;
                color: #f8f8f2;
                padding: 10px;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                margin: 5px 0;
                overflow-x: auto;
            }
            .plan-config {
                background: #2d2d2d;
                color: #f8f8f2;
                padding: 10px;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 11px;
                margin: 5px 0;
                max-height: 300px;
                overflow: auto;
                white-space: pre;
            }
            .result {
                margin-top: 20px;
                padding: 15px;
                border-radius: 5px;
                font-family: monospace;
                font-size: 13px;
                white-space: pre-wrap;
            }
            .success { background: #d4edda; border-left: 4px solid #28a745; }
            .error { background: #f8d7da; border-left: 4px solid #dc3545; }
            .warning { background: #fff3cd; border-left: 4px solid #ffc107; }
            .check-result {
                background: #f8f9fa;
                padding: 10px;
                border-radius: 4px;
                margin: 5px 0;
                border-left: 3px solid #ddd;
            }
            .check-result.passed { border-left-color: #28a745; }
            .check-result.failed { border-left-color: #dc3545; }

            /* Modal styles */
            .modal-overlay {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                z-index: 1000;
                align-items: center;
                justify-content: center;
            }
            .modal-overlay.show {
                display: flex;
            }
            .modal-dialog {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
                max-width: 500px;
                width: 90%;
                animation: modalSlideIn 0.2s ease-out;
            }
            @keyframes modalSlideIn {
                from {
                    transform: translateY(-50px);
                    opacity: 0;
                }
                to {
                    transform: translateY(0);
                    opacity: 1;
                }
            }
            .modal-title {
                font-size: 1.3em;
                font-weight: bold;
                margin: 0 0 15px 0;
                color: #333;
            }
            .modal-message {
                color: #666;
                margin-bottom: 25px;
                line-height: 1.5;
            }
            .modal-actions {
                display: flex;
                gap: 10px;
                justify-content: flex-end;
            }
            .btn-cancel {
                background: #6c757d;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 0.95em;
            }
            .btn-confirm {
                background: #f5576c;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 0.95em;
                font-weight: bold;
            }
            .btn-cancel:hover, .btn-confirm:hover {
                opacity: 0.9;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <div class="user-info">
                <div class="user-email">{{ current_user.email }}</div>
                <a href="{{ url_for('auth.logout') }}" class="btn-logout">Logout</a>
            </div>
            <h1>🚀 Dorothy</h1>
            <p>{{ config.description }}</p>
        </div>

        <div class="card">
            <h2>Managed Bots</h2>
            {% if bots %}
            <div class="bots">
                {% for name, bot in bots.items() %}
                <div class="bot-card">
                    <h3>{{ name.title() }}</h3>
                    {% if bot.description %}
                    <p style="color: #666; font-size: 0.95em; margin: 8px 0 15px 0; font-style: italic;">{{ bot.description }}</p>
                    {% endif %}
                    <div class="info">🌐 {{ bot.domain }}</div>
                    <div class="info">🖥️ Server: {{ config.default_server }}</div>
                    <div class="info">📁 {{ bot.path }}</div>
                    <div class="info">⚙️ {{ bot.service }}</div>
                    <div class="info">👥 Workers: {{ bot.workers }}</div>
                    <div class="actions">
                        <button class="btn btn-verify" onclick="verifyBot('{{ name }}')">Verify</button>
                        <button class="btn btn-plan" onclick="showPlan('{{ name }}')">Show Plan</button>
                        <button class="btn btn-deploy" onclick="deployBot('{{ name }}')">Deploy</button>
                        <button class="btn btn-update" onclick="updateBot('{{ name }}')">Update</button>
                        <button class="btn btn-health" onclick="healthCheck('{{ name }}')">Health</button>
                        <button class="btn btn-teardown" onclick="teardownBot('{{ name }}')">Teardown</button>
                    </div>
                    <div id="result-{{ name }}"></div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <p>No bots configured. Add bots in config.yaml</p>
            {% endif %}
        </div>

        <div class="card">
            <h2>Quick Links</h2>
            <p>🔗 <a href="/api/bots">API: List Bots</a></p>
            <p>🔗 <a href="/api/deployments">API: Deployment History</a></p>
            <p>🔗 <a href="/health">Health Check</a></p>
            <p>🔗 <a href="/info">Bot Info</a></p>
            <p>🔗 <a href="{{ config.sally_url }}" target="_blank">Sally (SSH Executor)</a></p>
        </div>

        <div class="card">
            <h2>Managing Bots</h2>

            <h3 style="margin-top: 15px; color: #f5576c;">➕ Add New Bot</h3>
            <p style="color: #666; font-size: 0.9em;">Add a new bot directly from the UI - Sally will update the config for you!</p>

            <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                    <div>
                        <label style="display: block; font-size: 0.85em; color: #666; margin-bottom: 3px;">Bot Name*</label>
                        <input type="text" id="new-bot-name" placeholder="e.g., peter" style="width: 100%; padding: 6px; border: 1px solid #ddd; border-radius: 4px;">
                    </div>
                    <div>
                        <label style="display: block; font-size: 0.85em; color: #666; margin-bottom: 3px;">Domain*</label>
                        <input type="text" id="new-bot-domain" placeholder="e.g., peter.example.com" style="width: 100%; padding: 6px; border: 1px solid #ddd; border-radius: 4px;">
                    </div>
                    <div>
                        <label style="display: block; font-size: 0.85em; color: #666; margin-bottom: 3px;">Workers</label>
                        <input type="number" id="new-bot-workers" value="2" min="1" max="8" style="width: 100%; padding: 6px; border: 1px solid #ddd; border-radius: 4px;">
                    </div>
                    <div>
                        <label style="display: block; font-size: 0.85em; color: #666; margin-bottom: 3px;">Description</label>
                        <input type="text" id="new-bot-description" placeholder="e.g., Project management bot" style="width: 100%; padding: 6px; border: 1px solid #ddd; border-radius: 4px;">
                    </div>
                </div>

                <!-- Advanced Options Toggle -->
                <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #ddd;">
                    <button type="button" onclick="toggleAdvancedOptions()" style="background: none; border: none; color: #007bff; cursor: pointer; font-size: 0.85em; padding: 0; text-decoration: underline;">
                        <span id="advanced-toggle-text">⚙️ Show Advanced Options</span>
                    </button>
                </div>

                <!-- Advanced Options (Hidden by default) -->
                <div id="advanced-options" style="display: none; margin-top: 10px; padding: 10px; background: #fff; border: 1px solid #ddd; border-radius: 4px;">
                    <p style="font-size: 0.85em; color: #856404; background: #fff3cd; padding: 8px; border-radius: 4px; margin: 0 0 10px 0;">
                        ⚠️ <strong>Advanced:</strong> For internal-only bots (like Sally) that don't need nginx/public domain.<br>
                        If you enter a port, nginx will be skipped and the bot will be accessible directly on that port.
                    </p>
                    <div>
                        <label style="display: block; font-size: 0.85em; color: #666; margin-bottom: 3px;">Port (optional - for internal-only bots)</label>
                        <input type="number" id="new-bot-port" placeholder="e.g., 8005" style="width: 100%; padding: 6px; border: 1px solid #ddd; border-radius: 4px;">
                    </div>
                </div>

                <button class="btn btn-deploy" onclick="addNewBot()" style="width: 100%; margin-top: 15px;">
                    ✨ Add Bot & Restart Dorothy
                </button>
                <div id="add-bot-result"></div>
            </div>

            <h3 style="margin-top: 15px; color: #DC3545;">➖ Removing a Bot</h3>
            <p style="color: #666; font-size: 0.9em; line-height: 1.6;">
                Use the <strong>Teardown</strong> button on any bot card. You'll have options to:
            </p>
            <ul style="color: #666; font-size: 0.9em; line-height: 1.6;">
                <li><strong>Remove from config:</strong> Sally will edit config.local.yaml and restart Dorothy (bot disappears from UI)</li>
                <li><strong>Delete code:</strong> Permanently remove the code directory from the server</li>
                <li>Or just teardown infrastructure and keep bot in config for future redeployment</li>
            </ul>

            <h3 style="margin-top: 15px; color: #17a2b8;">🔒 Accessing Internal-Only Bots</h3>
            <p style="color: #666; font-size: 0.9em; line-height: 1.6;">
                Internal-only bots (like Sally) aren't exposed via nginx. Access them locally using SSH port forwarding:
            </p>
            <div style="background: #f8f9fa; padding: 12px; border-radius: 4px; margin: 10px 0; font-family: monospace; font-size: 0.85em;">
                ssh -L &lt;port&gt;:localhost:&lt;port&gt; &lt;user&gt;@&lt;server&gt;
            </div>
            <p style="color: #666; font-size: 0.85em; margin-top: 8px;">
                <strong>Example for Sally (port 8004):</strong>
            </p>
            <div style="background: #f8f9fa; padding: 12px; border-radius: 4px; margin: 10px 0; font-family: monospace; font-size: 0.85em;">
                ssh -L 8004:localhost:8004 ubuntu@watsonblinds.com.au
            </div>
            <p style="color: #666; font-size: 0.85em;">
                Then access at <code>http://localhost:8004</code> in your browser while the SSH connection is active.
            </p>

            <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid #ddd;">
                <button class="btn btn-deploy" onclick="restartDorothy()" style="width: 100%;">
                    🔄 Restart Dorothy
                </button>
                <div id="restart-result"></div>
            </div>
        </div>

        <!-- Confirmation Modal -->
        <div id="confirmModal" class="modal-overlay">
            <div class="modal-dialog">
                <div class="modal-title" id="modalTitle">Confirm Action</div>
                <div class="modal-message" id="modalMessage"></div>
                <div id="modalOptions" style="margin: 15px 0; display: none;"></div>
                <div class="modal-actions">
                    <button class="btn-cancel" onclick="closeConfirmModal()">Cancel</button>
                    <button class="btn-confirm" id="modalConfirmBtn">Deploy</button>
                </div>
            </div>
        </div>

        <script>
            async function verifyBot(botName) {
                const resultDiv = document.getElementById('result-' + botName);
                resultDiv.innerHTML = '<div class="result">⏳ Starting verification for ' + botName + '...</div>';

                try {
                    // Start verification
                    const response = await fetch('/api/verify/' + botName, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({})
                    });

                    const startData = await response.json();

                    if (startData.error) {
                        resultDiv.innerHTML = `
                            <div class="result error">
                                <strong>❌ Verification Failed</strong>
                                <div>${startData.error}</div>
                            </div>
                        `;
                        return;
                    }

                    const verificationId = startData.verification_id;

                    // Poll for updates
                    const pollInterval = setInterval(async () => {
                        try {
                            const statusResponse = await fetch('/api/verifications/' + verificationId);
                            const data = await statusResponse.json();

                            // Check if verification was found
                            if (data.error) {
                                clearInterval(pollInterval);
                                resultDiv.innerHTML = `
                                    <div class="result error">
                                        <strong>❌ Verification Failed</strong>
                                        <div>${data.error}</div>
                                    </div>
                                `;
                                return;
                            }

                            // Build checks HTML showing current progress
                            let checksHtml = (data.checks || []).map(check => {
                                let checkName = (check.check || 'Check').replace(/_/g, ' ');
                                let icon, statusText, bgColor;

                                if (check.status === 'skipped') {
                                    icon = '⊝';
                                    statusText = 'Skipped';
                                    bgColor = '#f5f5f5';
                                } else if (check.status === 'in_progress') {
                                    icon = '⏳';
                                    statusText = 'Checking...';
                                    bgColor = '#fffbeb';
                                } else {
                                    icon = check.success ? '✅' : '❌';
                                    statusText = check.success ? 'Passed' : 'Failed';
                                    bgColor = check.success ? '#f0f9ff' : '#fff5f5';
                                }

                                // Build detailed info
                                let details = [];
                                if (check.path) details.push(`<strong>Path:</strong> <code>${check.path}</code>`);
                                if (check.bot_path) details.push(`<strong>Bot Path:</strong> <code>${check.bot_path}</code>`);
                                if (check.service_name) details.push(`<strong>Service:</strong> ${check.service_name}`);
                                if (check.domain) details.push(`<strong>Domain:</strong> ${check.domain}`);
                                if (check.branch) details.push(`<strong>Branch:</strong> ${check.branch}`);
                                if (check.details) details.push(`<strong>Details:</strong> ${check.details}`);
                                if (check.command) details.push(`<strong>Command:</strong> <code style="font-size: 0.85em;">${check.command}</code>`);
                                if (check.error) details.push(`<strong>Error:</strong><pre style="margin: 5px 0; padding: 8px; background: #fff3cd; border-left: 3px solid #ffc107;">${check.error}</pre>`);
                                if (check.stdout) details.push(`<strong>Output:</strong><pre style="margin: 5px 0; padding: 8px; background: #d4edda; border-left: 3px solid #28a745;">${check.stdout}</pre>`);
                                if (check.stderr) details.push(`<strong>Error Output:</strong><pre style="margin: 5px 0; padding: 8px; background: #f8d7da; border-left: 3px solid #dc3545;">${check.stderr}</pre>`);
                                if (check.exit_code !== undefined) details.push(`<strong>Exit Code:</strong> ${check.exit_code}`);

                                let detailsHtml = details.length > 0 ? '<div style="margin-top: 8px; font-size: 0.9em; color: #555;">' + details.join('<br>') + '</div>' : '';

                                return `<div class="check-result ${check.success ? 'passed' : 'failed'}" style="margin-bottom: 15px; padding: 10px; border-radius: 5px; background: ${bgColor};">
                                    ${icon} <strong>${checkName}</strong>: ${statusText}
                                    ${detailsHtml}
                                </div>`;
                            }).join('');

                            // Update display
                            if (data.status === 'completed') {
                                clearInterval(pollInterval);

                                if (data.all_passed) {
                                    resultDiv.innerHTML = `
                                        <div class="result success">
                                            <strong>✅ All Checks Passed</strong>
                                            ${checksHtml}
                                        </div>
                                    `;
                                } else {
                                    resultDiv.innerHTML = `
                                        <div class="result warning">
                                            <strong>⚠️ Some Checks Failed</strong>
                                            ${checksHtml}
                                        </div>
                                    `;
                                }
                            } else {
                                // Still in progress, update display
                                resultDiv.innerHTML = `
                                    <div class="result">
                                        <strong>⏳ Verification in progress...</strong>
                                        ${checksHtml}
                                    </div>
                                `;
                            }
                        } catch (pollError) {
                            clearInterval(pollInterval);
                            resultDiv.innerHTML = `
                                <div class="result error">
                                    <strong>❌ Error polling verification status</strong>
                                    <div>${pollError.message}</div>
                                </div>
                            `;
                        }
                    }, 500);  // Poll every 500ms

                } catch (error) {
                    resultDiv.innerHTML = `
                        <div class="result error">
                            <strong>❌ Verification Failed</strong>
                            <div>${error.message}</div>
                        </div>
                    `;
                }
            }

            let confirmModalCallback = null;

            function showConfirmModal(title, message, onConfirm, optionsHtml = null) {
                document.getElementById('modalTitle').textContent = title;
                document.getElementById('modalMessage').textContent = message;

                const modalOptions = document.getElementById('modalOptions');
                if (optionsHtml) {
                    modalOptions.innerHTML = optionsHtml;
                    modalOptions.style.display = 'block';
                } else {
                    modalOptions.innerHTML = '';
                    modalOptions.style.display = 'none';
                }

                document.getElementById('confirmModal').classList.add('show');
                confirmModalCallback = onConfirm;
            }

            function closeConfirmModal() {
                document.getElementById('confirmModal').classList.remove('show');
                confirmModalCallback = null;
            }

            document.getElementById('modalConfirmBtn').onclick = function() {
                if (confirmModalCallback) {
                    confirmModalCallback();
                }
                closeConfirmModal();
            };

            // Close on outside click
            document.getElementById('confirmModal').onclick = function(e) {
                if (e.target.id === 'confirmModal') {
                    closeConfirmModal();
                }
            };

            async function deployBot(botName) {
                const resultDiv = document.getElementById('result-' + botName);

                showConfirmModal(
                    '🚀 Deploy ' + botName + '?',
                    'This will deploy ' + botName + ' to the production server. The deployment process will update code, install dependencies, and restart the service.',
                    async function() {
                resultDiv.innerHTML = '<div class="result">🚀 Starting deployment...</div>';

                try {
                    // Start deployment
                    const response = await fetch('/api/deploy/' + botName, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({})
                    });

                    const startData = await response.json();

                    if (startData.error) {
                        resultDiv.innerHTML = `
                            <div class="result error">
                                <strong>❌ Deployment Failed</strong>
                                <div>${startData.error}</div>
                            </div>
                        `;
                        return;
                    }

                    const deploymentId = startData.deployment_id;

                    // Poll for updates
                    const pollInterval = setInterval(async () => {
                        try {
                            const statusResponse = await fetch('/api/deployments/' + deploymentId);
                            const data = await statusResponse.json();

                            if (data.error) {
                                clearInterval(pollInterval);
                                resultDiv.innerHTML = `
                                    <div class="result error">
                                        <strong>❌ Deployment Error</strong>
                                        <div>${data.error}</div>
                                    </div>
                                `;
                                return;
                            }

                            // Build detailed steps HTML
                            let stepsHtml = '';
                            if (data.steps && data.steps.length > 0) {
                                stepsHtml = data.steps.map(step => {
                                    let icon = step.status === 'in_progress' ? '⏳' : (step.status === 'completed' ? '✅' : '❌');
                                    let statusClass = step.status === 'completed' ? 'passed' : 'failed';

                                    let detailsHtml = '';
                                    if (step.result) {
                                        const isFailed = step.status === 'failed';

                                        // Show stdout if available
                                        if (step.result.stdout && step.result.stdout.trim()) {
                                            detailsHtml += `<div style="margin-top: 8px; font-size: 0.9em;">
                                                <strong>Output:</strong>
                                                <pre style="margin: 5px 0; padding: 8px; background: #f8f9fa; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; font-size: 0.85em;">${step.result.stdout}</pre>
                                            </div>`;
                                        }

                                        // Show stderr - only highlight as error if step actually failed
                                        if (step.result.stderr && step.result.stderr.trim()) {
                                            if (isFailed) {
                                                // Failed step - show stderr as error
                                                detailsHtml += `<div style="margin-top: 8px; font-size: 0.9em;">
                                                    <strong style="color: #dc3545;">Error Output:</strong>
                                                    <pre style="margin: 5px 0; padding: 8px; background: #fff3cd; border-left: 3px solid #dc3545; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; color: #721c24; font-size: 0.85em;">${step.result.stderr}</pre>
                                                </div>`;
                                            } else {
                                                // Successful step - show stderr as info (some commands like git write to stderr)
                                                detailsHtml += `<div style="margin-top: 8px; font-size: 0.9em;">
                                                    <strong>Info:</strong>
                                                    <pre style="margin: 5px 0; padding: 8px; background: #e7f3ff; border-left: 3px solid #0066cc; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; color: #004085; font-size: 0.85em;">${step.result.stderr}</pre>
                                                </div>`;
                                            }
                                        }

                                        // Show error message if available (only for failures)
                                        if (step.result.error && isFailed) {
                                            detailsHtml += `<div style="margin-top: 8px; font-size: 0.9em; color: #dc3545;"><strong>Error:</strong> ${step.result.error}</div>`;
                                        }

                                        // Show exit code if non-zero
                                        if (step.result.exit_code !== undefined && step.result.exit_code !== 0) {
                                            detailsHtml += `<div style="margin-top: 8px; font-size: 0.9em; color: #856404;"><strong>Exit Code:</strong> ${step.result.exit_code}</div>`;
                                        }
                                    }

                                    let bgColor = step.status === 'completed' ? '#f0f9ff' : (step.status === 'failed' ? '#fff5f5' : '#fffbeb');
                                    return `<div class="check-result ${statusClass}" style="margin-bottom: 15px; padding: 12px; border-radius: 5px; background: ${bgColor};">
                                        ${icon} <strong>${step.name}</strong>
                                        ${detailsHtml}
                                    </div>`;
                                }).join('');
                            }

                            if (data.status === 'completed' || data.status === 'partial') {
                                clearInterval(pollInterval);
                                const isSuccess = data.status === 'completed';

                                // Check if last step is "Manual configuration required"
                                const lastStep = data.steps && data.steps.length > 0 ? data.steps[data.steps.length - 1] : null;
                                const needsManualConfig = lastStep && lastStep.name === 'Manual configuration required';
                                const configMessage = lastStep && lastStep.result && lastStep.result.message ? lastStep.result.message : '';

                                let startServiceButton = '';
                                if (isSuccess && needsManualConfig) {
                                    startServiceButton = `
                                        <div style="margin-top: 20px; padding: 15px; background: #e7f3ff; border: 2px solid #0066cc; border-radius: 8px;">
                                            <div style="color: #004085; margin-bottom: 10px; white-space: pre-line;">${configMessage}</div>
                                            <button class="btn btn-start-service" onclick="startService('${botName}')" style="margin-top: 10px;">
                                                🚀 Start Service
                                            </button>
                                        </div>
                                    `;
                                }

                                resultDiv.innerHTML = `
                                    <div class="result ${isSuccess ? 'success' : 'error'}">
                                        <strong>${isSuccess ? '✅ Deployment Completed' : '❌ Deployment Failed'}</strong>
                                        ${data.duration ? `<div>Duration: ${data.duration.toFixed(2)}s</div>` : ''}
                                        ${data.error ? `<div style="margin: 10px 0; padding: 10px; background: #fff3cd; border-radius: 5px;">${data.error}</div>` : ''}
                                        <div style="margin-top: 15px;">
                                            ${stepsHtml}
                                        </div>
                                        ${startServiceButton}
                                    </div>
                                `;
                            } else {
                                // Still in progress
                                resultDiv.innerHTML = `
                                    <div class="result">
                                        <strong>🚀 Deployment in progress...</strong>
                                        ${stepsHtml}
                                    </div>
                                `;
                            }
                        } catch (pollError) {
                            clearInterval(pollInterval);
                            resultDiv.innerHTML = `
                                <div class="result error">
                                    <strong>❌ Error polling deployment status</strong>
                                    <div>${pollError.message}</div>
                                </div>
                            `;
                        }
                    }, 500);  // Poll every 500ms

                } catch (error) {
                    resultDiv.innerHTML = `
                        <div class="result error">
                            <strong>❌ Deployment Failed</strong>
                            <div>${error.message}</div>
                        </div>
                    `;
                }
                    }
                );
            }

            async function showPlan(botName) {
                const resultDiv = document.getElementById('result-' + botName);
                resultDiv.innerHTML = '<div class="result">📋 Loading deployment plan...</div>';

                try {
                    const response = await fetch('/api/plan/' + botName, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({})
                    });

                    const plan = await response.json();

                    if (plan.error) {
                        resultDiv.innerHTML = `
                            <div class="result error">
                                <strong>❌ Error</strong>
                                <div>${plan.error}</div>
                            </div>
                        `;
                        return;
                    }

                    // Build the plan HTML
                    let configHtml = `
                        <div style="margin: 10px 0;">
                            <strong>Configuration:</strong><br>
                            📁 Path: ${plan.config.path}<br>
                            🔗 Repo: ${plan.config.repo}<br>
                            🌐 Domain: ${plan.config.domain}<br>
                            ⚙️ Service: ${plan.config.service}<br>
                            👷 Workers: ${plan.config.workers}
                        </div>
                    `;

                    let stepsHtml = plan.steps.map((step, index) => {
                        let content = `<h4>Step ${index + 1}: ${step.name}</h4>`;
                        content += `<p>${step.description || ''}</p>`;

                        if (step.error) {
                            content += `<div class="error">Error: ${step.error}</div>`;
                        }

                        if (step.command) {
                            content += `<div class="plan-command">${step.command}</div>`;
                        }

                        if (step.commands) {
                            if (Array.isArray(step.commands)) {
                                step.commands.forEach(cmd => {
                                    content += `<div class="plan-command">${cmd}</div>`;
                                });
                            } else {
                                content += `<div class="plan-command"># If repo exists:\n${step.commands.if_exists}</div>`;
                                content += `<div class="plan-command"># If repo missing:\n${step.commands.if_missing}</div>`;
                            }
                        }

                        if (step.config_content) {
                            content += `<details style="margin-top: 10px;">
                                <summary style="cursor: pointer;">📄 Show config file</summary>
                                <div class="plan-config">${step.config_content}</div>
                            </details>`;
                        }

                        return `<div class="plan-step">${content}</div>`;
                    }).join('');

                    resultDiv.innerHTML = `
                        <div class="result warning">
                            <strong>📋 Deployment Plan for ${botName}</strong>
                            ${configHtml}
                            ${stepsHtml}
                            <div style="margin-top: 20px; padding: 15px; background: #fff3cd; border-radius: 5px;">
                                <strong>⚠️ Ready to deploy?</strong><br>
                                Review the commands above, then click <strong>Deploy</strong> to execute.
                            </div>
                        </div>
                    `;
                } catch (error) {
                    resultDiv.innerHTML = `
                        <div class="result error">
                            <strong>❌ Failed to load plan</strong>
                            <div>${error.message}</div>
                        </div>
                    `;
                }
            }

            async function healthCheck(botName) {
                const resultDiv = document.getElementById('result-' + botName);
                resultDiv.innerHTML = '<div class="result">🏥 Checking health...</div>';

                try {
                    const response = await fetch('/api/health-check/' + botName, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({})
                    });

                    const data = await response.json();

                    // Handle errors from API
                    if (data.error) {
                        resultDiv.innerHTML = `
                            <div class="result error">
                                <strong>❌ Health Check Failed</strong>
                                <div>${data.error}</div>
                            </div>
                        `;
                        return;
                    }

                    // Build access info based on method
                    let accessInfo = '';
                    if (data.access_method === 'direct_port') {
                        accessInfo = `<div class="check-result"><strong>Port:</strong> ${data.port || 'N/A'}</div>`;
                    } else if (data.access_method === 'nginx_domain') {
                        accessInfo = `<div class="check-result"><strong>Domain:</strong> ${data.domain || 'N/A'}</div>`;
                    } else if (data.access_method === 'systemd_service') {
                        accessInfo = `<div class="check-result"><strong>Service:</strong> ${data.service || 'N/A'}</div>`;
                    }

                    if (data.response) {
                        accessInfo += `<div class="check-result"><strong>Response:</strong> <code>${data.response}</code></div>`;
                    }

                    const displayName = data.bot || botName;

                    if (data.healthy) {
                        resultDiv.innerHTML = `
                            <div class="result success">
                                <strong>✅ ${displayName} is healthy!</strong>
                                ${accessInfo}
                            </div>
                        `;
                    } else {
                        resultDiv.innerHTML = `
                            <div class="result error">
                                <strong>❌ ${displayName} is not responding</strong>
                                ${accessInfo}
                            </div>
                        `;
                    }
                } catch (error) {
                    resultDiv.innerHTML = `
                        <div class="result error">
                            <strong>❌ Health Check Failed</strong>
                            <div>${error.message}</div>
                        </div>
                    `;
                }
            }

            async function updateBot(botName) {
                const resultDiv = document.getElementById('result-' + botName);

                showConfirmModal(
                    '🔄 Update ' + botName + '?',
                    'This will pull the latest code, install dependencies, and restart the service. Use this for regular deployments after initial setup.',
                    async function() {
                        resultDiv.innerHTML = '<div class="result">🔄 Updating bot...</div>';

                        try {
                            const response = await fetch('/api/update/' + botName, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({})
                            });

                            const data = await response.json();

                            if (data.error) {
                                resultDiv.innerHTML = `
                                    <div class="result error">
                                        <strong>❌ Update Failed</strong>
                                        <div>${data.error}</div>
                                    </div>
                                `;
                                return;
                            }

                            // Build steps HTML
                            let stepsHtml = '';
                            if (data.steps && data.steps.length > 0) {
                                stepsHtml = data.steps.map(step => {
                                    let icon = step.status === 'completed' ? '✅' : '❌';
                                    let bgColor = step.status === 'completed' ? '#f0f9ff' : '#fff5f5';

                                    return `<div class="check-result" style="margin-bottom: 15px; padding: 12px; border-radius: 5px; background: ${bgColor};">
                                        ${icon} <strong>${step.name}</strong>
                                    </div>`;
                                }).join('');
                            }

                            const isSuccess = data.success;
                            resultDiv.innerHTML = `
                                <div class="result ${isSuccess ? 'success' : 'error'}">
                                    <strong>${isSuccess ? '✅ Update Completed' : '❌ Update Failed'}</strong>
                                    <div style="margin-top: 15px;">
                                        ${stepsHtml}
                                    </div>
                                </div>
                            `;

                        } catch (error) {
                            resultDiv.innerHTML = `
                                <div class="result error">
                                    <strong>❌ Update Failed</strong>
                                    <div>${error.message}</div>
                                </div>
                            `;
                        }
                    }
                );
            }

            async function startService(botName) {
                const resultDiv = document.getElementById('result-' + botName);
                resultDiv.innerHTML = '<div class="result">🚀 Starting service...</div>';

                try {
                    const response = await fetch('/api/start-service/' + botName, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({})
                    });

                    const data = await response.json();

                    if (data.error) {
                        resultDiv.innerHTML = `
                            <div class="result error">
                                <strong>❌ Failed to Start Service</strong>
                                <div>${data.error}</div>
                            </div>
                        `;
                        return;
                    }

                    if (data.success) {
                        resultDiv.innerHTML = `
                            <div class="result success">
                                <strong>✅ Service Started Successfully!</strong>
                                <div class="check-result" style="margin-top: 10px;">
                                    <strong>Service:</strong> ${data.service || botName}
                                </div>
                                <div style="margin-top: 10px;">
                                    <button class="btn btn-health" onclick="healthCheck('${botName}')">Check Health</button>
                                </div>
                            </div>
                        `;
                    } else {
                        let errorDetails = '';
                        if (data.stderr) errorDetails += `<div><strong>Error:</strong> ${data.stderr}</div>`;
                        if (data.stdout) errorDetails += `<div><strong>Output:</strong> ${data.stdout}</div>`;
                        if (data.exit_code !== undefined) errorDetails += `<div><strong>Exit Code:</strong> ${data.exit_code}</div>`;

                        resultDiv.innerHTML = `
                            <div class="result error">
                                <strong>❌ Failed to Start Service</strong>
                                ${errorDetails}
                            </div>
                        `;
                    }

                } catch (error) {
                    resultDiv.innerHTML = `
                        <div class="result error">
                            <strong>❌ Failed to Start Service</strong>
                            <div>${error.message}</div>
                        </div>
                    `;
                }
            }

            async function teardownBot(botName) {
                const resultDiv = document.getElementById('result-' + botName);

                const optionsHtml = `
                    <div style="background: #f8f9fa; padding: 10px; border-radius: 4px; text-align: left;">
                        <p style="margin: 0 0 10px 0; font-weight: bold; font-size: 0.9em;">Teardown Options:</p>
                        <label style="display: flex; align-items: center; margin-bottom: 8px; font-size: 0.9em;">
                            <input type="checkbox" id="teardown-remove-from-config" style="margin-right: 8px;">
                            Remove bot from config.local.yaml and restart Dorothy
                        </label>
                        <label style="display: flex; align-items: center; font-size: 0.9em;">
                            <input type="checkbox" id="teardown-remove-code" style="margin-right: 8px;">
                            Delete code directory (⚠️ Cannot be undone!)
                        </label>
                    </div>
                `;

                showConfirmModal(
                    '⚠️ Teardown ' + botName + '?',
                    'This will stop the service and remove systemd/nginx configs from the server.',
                    async function() {
                        const removeFromConfig = document.getElementById('teardown-remove-from-config').checked;
                        const removeCode = document.getElementById('teardown-remove-code').checked;

                        resultDiv.innerHTML = '<div class="result">🗑️ Tearing down bot...</div>';

                        try {
                            const response = await fetch('/api/teardown/' + botName, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    remove_code: removeCode,
                                    remove_from_config: removeFromConfig
                                })
                            });

                            const data = await response.json();

                            if (data.error) {
                                resultDiv.innerHTML = `
                                    <div class="result error">
                                        <strong>❌ Teardown Failed</strong>
                                        <div>${data.error}</div>
                                    </div>
                                `;
                                return;
                            }

                            // Build steps HTML
                            let stepsHtml = '';
                            if (data.steps && data.steps.length > 0) {
                                stepsHtml = data.steps.map(step => {
                                    let icon = step.status === 'completed' ? '✅' : '❌';
                                    let bgColor = step.status === 'completed' ? '#f0f9ff' : '#fff5f5';

                                    return `<div class="check-result" style="margin-bottom: 15px; padding: 12px; border-radius: 5px; background: ${bgColor};">
                                        ${icon} <strong>${step.name}</strong>
                                    </div>`;
                                }).join('');
                            }

                            const isSuccess = data.success;
                            const removedFromConfig = data.removed_from_config;

                            let statusMessage = '';
                            if (isSuccess) {
                                if (removedFromConfig) {
                                    statusMessage = '<div style="margin-top: 10px; color: #666;">Bot removed from server and config. Dorothy is restarting... Page will reload in 3 seconds.</div>';
                                    // Reload page after 3 seconds to reflect config change
                                    setTimeout(() => { window.location.reload(); }, 3000);
                                } else {
                                    statusMessage = '<div style="margin-top: 10px; color: #666;">Bot removed from server. Still listed in config - use Teardown again to remove from config, or Deploy to bring it back.</div>';
                                }
                            }

                            resultDiv.innerHTML = `
                                <div class="result ${isSuccess ? 'success' : 'error'}">
                                    <strong>${isSuccess ? '✅ Teardown Completed' : '❌ Teardown Failed'}</strong>
                                    <div style="margin-top: 15px;">
                                        ${stepsHtml}
                                    </div>
                                    ${statusMessage}
                                </div>
                            `;

                        } catch (error) {
                            resultDiv.innerHTML = `
                                <div class="result error">
                                    <strong>❌ Teardown Failed</strong>
                                    <div>${error.message}</div>
                                </div>
                            `;
                        }
                    },
                    optionsHtml  // Pass the options HTML to the modal
                );
            }

            function toggleAdvancedOptions() {
                const advancedOptions = document.getElementById('advanced-options');
                const toggleText = document.getElementById('advanced-toggle-text');

                if (advancedOptions.style.display === 'none') {
                    advancedOptions.style.display = 'block';
                    toggleText.textContent = '⚙️ Hide Advanced Options';
                } else {
                    advancedOptions.style.display = 'none';
                    toggleText.textContent = '⚙️ Show Advanced Options';
                }
            }

            async function addNewBot() {
                const resultDiv = document.getElementById('add-bot-result');

                // Get form values
                const botName = document.getElementById('new-bot-name').value.trim();
                const port = document.getElementById('new-bot-port').value;
                const domain = document.getElementById('new-bot-domain').value.trim();
                const workers = document.getElementById('new-bot-workers').value;
                const description = document.getElementById('new-bot-description').value.trim();

                // Automatically determine skip_nginx based on whether port is provided
                const skipNginx = !!port;

                // Validate required fields
                if (!botName) {
                    resultDiv.innerHTML = `
                        <div class="result error" style="margin-top: 10px;">
                            <strong>❌ Validation Error</strong>
                            <div>Bot name is required</div>
                        </div>
                    `;
                    return;
                }

                if (!domain) {
                    resultDiv.innerHTML = `
                        <div class="result error" style="margin-top: 10px;">
                            <strong>❌ Validation Error</strong>
                            <div>Domain is required</div>
                        </div>
                    `;
                    return;
                }

                resultDiv.innerHTML = '<div class="result" style="margin-top: 10px;">✨ Adding bot and restarting Dorothy...</div>';

                try {
                    // Build request body
                    const requestBody = {
                        name: botName,
                        domain: domain,
                        workers: parseInt(workers),
                        description: description || undefined,
                        skip_nginx: skipNginx
                    };

                    // Include port if provided (automatically sets skip_nginx=true)
                    if (port) {
                        requestBody.port = parseInt(port);
                    }

                    const response = await fetch('/api/add-bot', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(requestBody)
                    });

                    const data = await response.json();

                    if (data.error) {
                        resultDiv.innerHTML = `
                            <div class="result error" style="margin-top: 10px;">
                                <strong>❌ Failed to Add Bot</strong>
                                <div>${data.error}</div>
                            </div>
                        `;
                        return;
                    }

                    if (data.success) {
                        resultDiv.innerHTML = `
                            <div class="result success" style="margin-top: 10px;">
                                <strong>✅ Bot Added Successfully!</strong>
                                <div style="margin-top: 5px; color: #666;">Bot "${data.bot_name}" has been added to config.</div>
                                <div style="margin-top: 5px; color: #666;">Dorothy is restarting... Page will reload in 3 seconds.</div>
                            </div>
                        `;
                        // Reload page after 3 seconds to show new bot
                        setTimeout(() => {
                            window.location.reload();
                        }, 3000);
                    } else {
                        resultDiv.innerHTML = `
                            <div class="result error" style="margin-top: 10px;">
                                <strong>❌ Failed to Add Bot</strong>
                                <div>An unexpected error occurred</div>
                            </div>
                        `;
                    }

                } catch (error) {
                    resultDiv.innerHTML = `
                        <div class="result error" style="margin-top: 10px;">
                            <strong>❌ Failed to Add Bot</strong>
                            <div>${error.message}</div>
                        </div>
                    `;
                }
            }

            async function restartDorothy() {
                const resultDiv = document.getElementById('restart-result');
                resultDiv.innerHTML = '<div class="result" style="margin-top: 10px;">🔄 Restarting Dorothy...</div>';

                try {
                    const response = await fetch('/api/restart-dorothy', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({})
                    });

                    const data = await response.json();

                    if (data.error) {
                        resultDiv.innerHTML = `
                            <div class="result error" style="margin-top: 10px;">
                                <strong>❌ Restart Failed</strong>
                                <div>${data.error}</div>
                            </div>
                        `;
                        return;
                    }

                    if (data.success) {
                        resultDiv.innerHTML = `
                            <div class="result success" style="margin-top: 10px;">
                                <strong>✅ Dorothy Restarted!</strong>
                                <div style="margin-top: 5px; color: #666;">Page will reload in 3 seconds...</div>
                            </div>
                        `;
                        // Reload page after 3 seconds to show updated config
                        setTimeout(() => {
                            window.location.reload();
                        }, 3000);
                    } else {
                        let errorDetails = '';
                        if (data.stderr) errorDetails += `<div><strong>Error:</strong> ${data.stderr}</div>`;
                        if (data.stdout) errorDetails += `<div><strong>Output:</strong> ${data.stdout}</div>`;

                        resultDiv.innerHTML = `
                            <div class="result error" style="margin-top: 10px;">
                                <strong>❌ Restart Failed</strong>
                                ${errorDetails}
                            </div>
                        `;
                    }

                } catch (error) {
                    resultDiv.innerHTML = `
                        <div class="result error" style="margin-top: 10px;">
                            <strong>❌ Restart Failed</strong>
                            <div>${error.message}</div>
                        </div>
                    `;
                }
            }
        </script>
    </body>
    </html>
    '''

    return render_template_string(template, config=config, bots=bots, current_user=current_user)
