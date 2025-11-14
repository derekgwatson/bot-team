from flask import Blueprint, render_template_string, request, jsonify
from config import config

web_bp = Blueprint('web', __name__)

@web_bp.route('/')
def index():
    """Dorothy's home page"""
    bots = config.bots

    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dorothy - Deployment Orchestrator</title>
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
            .bot-card .actions { margin-top: 15px; display: flex; gap: 10px; }
            .btn {
                padding: 8px 16px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 0.9em;
                font-weight: bold;
            }
            .btn-verify { background: #4CAF50; color: white; }
            .btn-deploy { background: #f5576c; color: white; }
            .btn-health { background: #2196F3; color: white; }
            .btn:hover { opacity: 0.9; }
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
        </style>
    </head>
    <body>
        <div class="header">
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
                    <div class="info">🌐 {{ bot.domain }}</div>
                    <div class="info">🔌 Port {{ bot.port }}</div>
                    <div class="info">📁 {{ bot.path }}</div>
                    <div class="actions">
                        <button class="btn btn-verify" onclick="verifyBot('{{ name }}')">Verify</button>
                        <button class="btn btn-deploy" onclick="deployBot('{{ name }}')">Deploy</button>
                        <button class="btn btn-health" onclick="healthCheck('{{ name }}')">Health</button>
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

        <script>
            async function verifyBot(botName) {
                const resultDiv = document.getElementById('result-' + botName);
                resultDiv.innerHTML = '<div class="result">⏳ Verifying ' + botName + '...</div>';

                try {
                    const response = await fetch('/api/verify/' + botName, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });

                    const data = await response.json();

                    if (data.all_passed) {
                        let checksHtml = data.checks.map(check =>
                            `<div class="check-result passed">✅ ${check.check}: ${check.success ? 'Passed' : 'Failed'}</div>`
                        ).join('');

                        resultDiv.innerHTML = `
                            <div class="result success">
                                <strong>✅ All Checks Passed</strong>
                                ${checksHtml}
                            </div>
                        `;
                    } else {
                        let checksHtml = data.checks.map(check =>
                            `<div class="check-result ${check.success ? 'passed' : 'failed'}">
                                ${check.success ? '✅' : '❌'} ${check.check}: ${check.success ? 'Passed' : 'Failed'}
                                ${check.details ? '<br><small>' + check.details + '</small>' : ''}
                            </div>`
                        ).join('');

                        resultDiv.innerHTML = `
                            <div class="result warning">
                                <strong>⚠️ Some Checks Failed</strong>
                                ${checksHtml}
                            </div>
                        `;
                    }
                } catch (error) {
                    resultDiv.innerHTML = `
                        <div class="result error">
                            <strong>❌ Verification Failed</strong>
                            <div>${error.message}</div>
                        </div>
                    `;
                }
            }

            async function deployBot(botName) {
                if (!confirm('Deploy ' + botName + ' to production?')) return;

                const resultDiv = document.getElementById('result-' + botName);
                resultDiv.innerHTML = '<div class="result">🚀 Deploying ' + botName + '...</div>';

                try {
                    const response = await fetch('/api/deploy/' + botName, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });

                    const data = await response.json();

                    if (data.status === 'completed') {
                        let stepsHtml = data.steps.map(step =>
                            `<div class="check-result ${step.status === 'completed' ? 'passed' : 'failed'}">
                                ${step.status === 'completed' ? '✅' : '❌'} ${step.name}
                            </div>`
                        ).join('');

                        resultDiv.innerHTML = `
                            <div class="result success">
                                <strong>✅ Deployment Completed</strong>
                                <div>Duration: ${data.duration.toFixed(2)}s</div>
                                ${stepsHtml}
                            </div>
                        `;
                    } else {
                        resultDiv.innerHTML = `
                            <div class="result error">
                                <strong>❌ Deployment Failed</strong>
                                <div>${data.error || 'See steps for details'}</div>
                            </div>
                        `;
                    }
                } catch (error) {
                    resultDiv.innerHTML = `
                        <div class="result error">
                            <strong>❌ Deployment Failed</strong>
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
                        headers: { 'Content-Type': 'application/json' }
                    });

                    const data = await response.json();

                    if (data.healthy) {
                        resultDiv.innerHTML = `
                            <div class="result success">
                                <strong>✅ ${botName} is healthy!</strong>
                                <div class="check-result">Port: ${data.port}</div>
                            </div>
                        `;
                    } else {
                        resultDiv.innerHTML = `
                            <div class="result error">
                                <strong>❌ ${botName} is not responding</strong>
                                <div class="check-result">Port: ${data.port}</div>
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
        </script>
    </body>
    </html>
    '''

    return render_template_string(template, config=config, bots=bots)
