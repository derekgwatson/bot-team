from flask import Blueprint, request, jsonify
from services.ssh_executor import ssh_executor
from shared.auth.bot_api import api_key_required
from config import config
import time
import uuid

api_bp = Blueprint('api', __name__)

# Store command history
command_history = {}


@api_bp.route('/servers', methods=['GET'])
@api_key_required
def list_servers():
    """List all configured servers"""
    servers = config.servers
    server_list = []

    for name, server_config in servers.items():
        server_list.append({
            'name': name,
            'host': server_config.get('host'),
            'description': server_config.get('description', ''),
            'user': server_config.get('user', config.ssh_default_user)
        })

    return jsonify({
        'servers': server_list,
        'count': len(server_list)
    })

@api_bp.route('/test/<server_name>', methods=['GET'])
@api_key_required
def test_connection(server_name):
    """Test connection to a server"""
    result = ssh_executor.test_connection(server_name)
    return jsonify(result)

@api_bp.route('/execute', methods=['POST'])
@api_key_required
def execute_command():
    """
    Execute a command on a remote server

    Body:
        server: Server name from config
        command: Command to execute
        timeout: Optional timeout in seconds
    """
    data = request.get_json()

    if not data or 'server' not in data or 'command' not in data:
        return jsonify({
            'error': 'Missing required fields: server and command'
        }), 400

    server_name = data['server']
    command = data['command']
    timeout = data.get('timeout')

    # Generate execution ID
    exec_id = str(uuid.uuid4())[:8]

    # Execute command
    result = ssh_executor.execute_command(server_name, command, timeout)
    result['id'] = exec_id
    result['timestamp'] = time.time()

    # Store in history
    command_history[exec_id] = result

    return jsonify(result)

@api_bp.route('/history', methods=['GET'])
@api_key_required
def get_history():
    """Get command execution history"""
    limit = request.args.get('limit', 50, type=int)

    # Get last N commands
    history = list(command_history.values())
    history.reverse()  # Most recent first

    return jsonify({
        'history': history[:limit],
        'total': len(command_history)
    })

@api_bp.route('/history/<exec_id>', methods=['GET'])
@api_key_required
def get_execution(exec_id):
    """Get details of a specific execution"""
    if exec_id not in command_history:
        return jsonify({'error': 'Execution not found'}), 404

    return jsonify(command_history[exec_id])
