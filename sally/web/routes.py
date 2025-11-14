from flask import Blueprint, render_template_string, request, jsonify
from config import config
from services.ssh_executor import ssh_executor

web_bp = Blueprint('web', __name__)

@web_bp.route('/')
def index():
    """Sally's home page"""
    servers = config.servers

    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sally - SSH Command Executor</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 10px;
                margin-bottom: 30px;
            }
            .header h1 { margin: 0 0 10px 0; }
            .header p { margin: 0; opacity: 0.9; }
            .card {
                background: white;
                padding: 25px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }
            .servers { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; }
            .server-card {
                background: white;
                padding: 20px;
                border-radius: 8px;
                border-left: 4px solid #667eea;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                cursor: pointer;
                transition: all 0.2s ease;
            }
            .server-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.15);
                border-left-color: #5568d3;
            }
            .server-card.selected {
                background: #f0f4ff;
                border-left-color: #5568d3;
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
            }
            .server-card h3 { margin: 0 0 10px 0; color: #667eea; }
            .server-card .info { color: #666; font-size: 0.9em; margin: 5px 0; }
            .execute-form { margin-top: 20px; }
            select, input, textarea, button {
                width: 100%;
                padding: 12px;
                margin: 8px 0;
                border: 1px solid #ddd;
                border-radius: 5px;
                font-size: 14px;
                box-sizing: border-box;
            }
            textarea { min-height: 100px; font-family: monospace; }
            button {
                background: #667eea;
                color: white;
                border: none;
                cursor: pointer;
                font-weight: bold;
            }
            button:hover { background: #5568d3; }
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
            .output { background: #f8f9fa; padding: 10px; border-radius: 4px; margin-top: 10px; }
            .stats { display: flex; gap: 10px; margin-top: 10px; }
            .stat { background: #f8f9fa; padding: 8px 12px; border-radius: 4px; font-size: 0.9em; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>👩‍💼 Sally</h1>
            <p>{{ config.description }}</p>
        </div>

        <div class="card">
            <h2>Available Servers</h2>
            {% if servers %}
            <div class="servers">
                {% for name, server in servers.items() %}
                <div class="server-card" data-server="{{ name }}" onclick="selectServer('{{ name }}')">
                    <h3>{{ name }}</h3>
                    <div class="info">🖥️ {{ server.host }}</div>
                    <div class="info">👤 {{ server.get('user', 'ubuntu') }}</div>
                    {% if server.get('description') %}
                    <div class="info">{{ server.description }}</div>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
            {% else %}
            <p>No servers configured. Add servers in config.yaml</p>
            {% endif %}
        </div>

        <div class="card">
            <h2>Execute Command</h2>
            <form class="execute-form" onsubmit="executeCommand(event)">
                <label>Server:</label>
                <select id="server" required>
                    <option value="">Select a server...</option>
                    {% for name in servers.keys() %}
                    <option value="{{ name }}">{{ name }}</option>
                    {% endfor %}
                </select>

                <label>Command:</label>
                <textarea id="command" placeholder="ls -la" required></textarea>

                <label>Timeout (seconds, optional):</label>
                <input type="number" id="timeout" placeholder="300">

                <button type="submit">Execute Command</button>
            </form>

            <div id="result"></div>
        </div>

        <div class="card">
            <h2>Quick Links</h2>
            <p>🔗 <a href="/api/servers">API: List Servers</a></p>
            <p>🔗 <a href="/api/history">API: Command History</a></p>
            <p>🔗 <a href="/health">Health Check</a></p>
            <p>🔗 <a href="/info">Bot Info</a></p>
        </div>

        <script>
            // Select a server (from clicking card or dropdown change)
            function selectServer(serverName) {
                const serverSelect = document.getElementById('server');
                serverSelect.value = serverName;

                // Update visual selection on cards
                document.querySelectorAll('.server-card').forEach(card => {
                    card.classList.remove('selected');
                });
                const selectedCard = document.querySelector(`[data-server="${serverName}"]`);
                if (selectedCard) {
                    selectedCard.classList.add('selected');
                }

                // Save to localStorage for next time
                localStorage.setItem('sally_last_server', serverName);

                // Scroll to command input for convenience
                document.getElementById('command').focus();
            }

            // Initialize on page load
            window.addEventListener('DOMContentLoaded', () => {
                const serverSelect = document.getElementById('server');
                const serverOptions = Array.from(serverSelect.options).filter(o => o.value);

                // Auto-select if only one server
                if (serverOptions.length === 1) {
                    selectServer(serverOptions[0].value);
                } else if (serverOptions.length > 1) {
                    // Try to restore last selected server
                    const lastServer = localStorage.getItem('sally_last_server');
                    if (lastServer && serverOptions.find(o => o.value === lastServer)) {
                        selectServer(lastServer);
                    }
                }

                // Also update visual when dropdown is changed manually
                serverSelect.addEventListener('change', (e) => {
                    if (e.target.value) {
                        selectServer(e.target.value);
                    }
                });
            });

            async function executeCommand(event) {
                event.preventDefault();

                const server = document.getElementById('server').value;
                const command = document.getElementById('command').value;
                const timeout = document.getElementById('timeout').value;

                const payload = { server, command };
                if (timeout) payload.timeout = parseInt(timeout);

                const resultDiv = document.getElementById('result');
                resultDiv.innerHTML = '<div class="result">⏳ Executing command...</div>';

                try {
                    const response = await fetch('/api/execute', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });

                    const data = await response.json();

                    if (data.success) {
                        resultDiv.innerHTML = `
                            <div class="result success">
                                <strong>✅ Success</strong>
                                <div class="stats">
                                    <span class="stat">Exit Code: ${data.exit_code}</span>
                                    <span class="stat">Time: ${data.execution_time}s</span>
                                    <span class="stat">ID: ${data.id}</span>
                                </div>
                                ${data.stdout ? '<div class="output"><strong>Output:</strong><br>' + data.stdout + '</div>' : ''}
                                ${data.stderr ? '<div class="output"><strong>Stderr:</strong><br>' + data.stderr + '</div>' : ''}
                            </div>
                        `;
                    } else {
                        resultDiv.innerHTML = `
                            <div class="result error">
                                <strong>❌ Error</strong>
                                <div class="output">${data.error || data.stderr}</div>
                                ${data.stdout ? '<div class="output"><strong>Output:</strong><br>' + data.stdout + '</div>' : ''}
                            </div>
                        `;
                    }
                } catch (error) {
                    resultDiv.innerHTML = `
                        <div class="result error">
                            <strong>❌ Request Failed</strong>
                            <div class="output">${error.message}</div>
                        </div>
                    `;
                }
            }
        </script>
    </body>
    </html>
    '''

    return render_template_string(template, config=config, servers=servers)
