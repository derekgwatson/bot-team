import paramiko
import time
from typing import Dict, Optional, Tuple
from config import config

class SSHExecutor:
    """Handles SSH connections and command execution"""

    def __init__(self):
        self.connections = {}

    def _get_connection(self, server_name: str) -> paramiko.SSHClient:
        """Get or create SSH connection to server"""
        if server_name not in self.connections:
            servers = config.servers
            if server_name not in servers:
                raise ValueError(f"Server '{server_name}' not configured")

            server_config = servers[server_name]
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Load private key
            try:
                private_key = paramiko.RSAKey.from_private_key_file(config.ssh_key_path)
            except Exception as e:
                raise Exception(f"Failed to load SSH key: {str(e)}")

            # Connect
            try:
                client.connect(
                    hostname=server_config['host'],
                    username=server_config.get('user', config.ssh_default_user),
                    pkey=private_key,
                    timeout=config.ssh_connect_timeout
                )
                self.connections[server_name] = client
            except Exception as e:
                raise Exception(f"Failed to connect to {server_name}: {str(e)}")

        return self.connections[server_name]

    def execute_command(
        self,
        server_name: str,
        command: str,
        timeout: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Execute a command on a remote server

        Args:
            server_name: Name of the server from config
            command: Command to execute
            timeout: Command timeout in seconds (uses config default if None)

        Returns:
            Dict with stdout, stderr, exit_code, and execution time
        """
        if timeout is None:
            timeout = config.ssh_command_timeout

        try:
            client = self._get_connection(server_name)

            start_time = time.time()
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)

            # Wait for command to complete
            exit_code = stdout.channel.recv_exit_status()

            stdout_text = stdout.read().decode('utf-8')
            stderr_text = stderr.read().decode('utf-8')
            execution_time = time.time() - start_time

            return {
                'success': exit_code == 0,
                'exit_code': exit_code,
                'stdout': stdout_text,
                'stderr': stderr_text,
                'execution_time': round(execution_time, 2),
                'server': server_name,
                'command': command
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'server': server_name,
                'command': command
            }

    def test_connection(self, server_name: str) -> Dict[str, any]:
        """Test connection to a server"""
        try:
            result = self.execute_command(server_name, 'echo "Sally is connected!"')
            return {
                'connected': result['success'],
                'server': server_name,
                'message': result.get('stdout', '').strip() if result['success'] else result.get('error', 'Connection failed')
            }
        except Exception as e:
            return {
                'connected': False,
                'server': server_name,
                'error': str(e)
            }

    def close_all(self):
        """Close all SSH connections"""
        for client in self.connections.values():
            try:
                client.close()
            except:
                pass
        self.connections.clear()

# Global instance
ssh_executor = SSHExecutor()
