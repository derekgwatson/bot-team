"""
Simple web routes for Quinn - just a status page showing sync information
"""
from flask import Blueprint, render_template_string
from services.sync_service import sync_service
from services.peter_client import peter_client
from config import config
from datetime import datetime

simple_web_bp = Blueprint('simple_web', __name__, template_folder='templates')

@simple_web_bp.route('/')
def index():
    """Simple public status page - no authentication required"""

    # Get sync status
    status = sync_service.get_status()

    # Format last sync time
    last_sync_time = None
    if status['last_sync']:
        last_sync_time = datetime.fromtimestamp(status['last_sync']).strftime('%Y-%m-%d %H:%M:%S')

    # Get last sync result summary
    last_result = status['last_sync_result']
    sync_summary = None
    if last_result:
        sync_summary = {
            'success': last_result.get('success', False),
            'desired_count': last_result.get('desired_count', 0),
            'current_count': last_result.get('current_count', 0),
            'added_count': len(last_result.get('added', [])),
            'removed_count': len(last_result.get('removed', [])),
            'elapsed': last_result.get('elapsed_seconds', 0)
        }

    # Get managers list from Peter (internal staff with Google accounts)
    managers = peter_client.get_allstaff_managers()

    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Quinn - All-Staff Group Sync</title>
        <meta name="robots" content="noindex, nofollow">
        <meta name="googlebot" content="noindex, nofollow">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 800px;
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
            .stat {
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                border-bottom: 1px solid #eee;
            }
            .stat:last-child {
                border-bottom: none;
            }
            .stat-label {
                color: #666;
            }
            .stat-value {
                font-weight: bold;
            }
            .link {
                color: #667eea;
                text-decoration: none;
            }
            .link:hover {
                text-decoration: underline;
            }
            .manager-list {
                list-style: none;
                padding: 0;
                margin: 15px 0 0 0;
            }
            .manager-list li {
                padding: 8px 12px;
                background: #f8f9fa;
                border-radius: 4px;
                margin-bottom: 8px;
                font-family: monospace;
            }
            .empty-state {
                color: #999;
                font-style: italic;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>👥 Quinn</h1>
            <p>{{ config.description }}</p>
        </div>

        {% if sync_summary %}
        <div class="card">
            <h2>Last Sync Result</h2>

            <div class="stat">
                <span class="stat-label">Status</span>
                <span class="stat-value">{% if sync_summary.success %}✅ Success{% else %}❌ Failed{% endif %}</span>
            </div>
            <div class="stat">
                <span class="stat-label">When</span>
                <span class="stat-value">{{ last_sync_time }}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Members in Group</span>
                <span class="stat-value">{{ sync_summary.current_count }}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Should Be in Group (from Peter)</span>
                <span class="stat-value">{{ sync_summary.desired_count }}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Members Added</span>
                <span class="stat-value">{{ sync_summary.added_count }}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Members Removed</span>
                <span class="stat-value">{{ sync_summary.removed_count }}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Duration</span>
                <span class="stat-value">{{ "%.2f"|format(sync_summary.elapsed) }}s</span>
            </div>
        </div>
        {% else %}
        <div class="card">
            <h2>Sync Status</h2>
            <p class="empty-state">No sync has run yet since Quinn started.</p>
        </div>
        {% endif %}

        <div class="card">
            <h2>Group Managers</h2>
            <p style="color: #555; margin-bottom: 10px;">
                Internal staff (with Google accounts) who can send emails to the all-staff group.
                Managed in Peter via <code>include_in_allstaff</code> + <code>google_access</code> flags.
            </p>
            {% if managers %}
            <ul class="manager-list">
                {% for email in managers %}
                <li>{{ email }}</li>
                {% endfor %}
            </ul>
            {% else %}
            <p class="empty-state">No managers configured.</p>
            {% endif %}
        </div>

        <div class="card">
            <h2>How It Works</h2>
            <p style="line-height: 1.6; color: #555;">
                Quinn keeps the all-staff Google Group in sync with Peter's HR database.
                <strong>Skye</strong> triggers a sync every 5 minutes, and Quinn:
            </p>
            <ol style="line-height: 1.8; color: #555;">
                <li>Asks Peter for external staff (no Google account) → added as members</li>
                <li>Asks Peter for internal staff (have Google account) → protected as managers</li>
                <li>Compares with current Google Group membership</li>
                <li>Adds/removes members to match, but never removes managers</li>
            </ol>
            <p style="line-height: 1.6; color: #555; margin-top: 20px;">
                <strong>Peter is the source of truth</strong> for both members and managers.
                Set <code>include_in_allstaff = 1</code> on any staff member in Peter.
            </p>
        </div>

        <div class="card">
            <h2>API Endpoints</h2>
            <ul style="line-height: 1.8;">
                <li><a href="/api/sync/status" class="link">GET /api/sync/status</a> - Get sync status</li>
                <li><a href="/api/sync/preview" class="link">GET /api/sync/preview</a> - Preview sync changes</li>
                <li><code>POST /api/sync/now</code> - Trigger immediate sync</li>
            </ul>
            <p style="color: #888; margin-top: 15px; font-size: 0.9em;">
                Managers are managed in Peter, not Quinn.
            </p>
        </div>
    </body>
    </html>
    '''

    return render_template_string(
        template,
        config=config,
        status=status,
        last_sync_time=last_sync_time,
        sync_summary=sync_summary,
        managers=managers
    )
