import paramiko
import subprocess
import time
import socket
from typing import Dict, Optional, Tuple
from config import config

class SSHExecutor:
    """Handles SSH connections and command execution"""

    def __init__(self):
        self.connections = {}
        self._local_hostname = socket.gethostname()
        self._local_fqdn = socket.getfqdn()

    def _is_local_server(self, server_config: dict) -> bool:
        """
        Check if a server is the local machine

        Returns True if the server host matches:
        - localhost
        - 127.0.0.1
        - The current machine's hostname
        - The current machine's FQDN
        """
        host = server_config.get('host', '')

        if host in ['localhost', '127.0.0.1', '::1']:
            return True

        if host == self._local_hostname or host == self._local_fqdn:
            return True

        # Try to resolve hostname and compare IPs
        try:
            target_ip = socket.gethostbyname(host)
            local_ip = socket.gethostbyname(self._local_hostname)
            if target_ip == local_ip:
                return True
        except:
            pass

        return False

    def _execute_local(self, command: str, timeout: Optional[int] = None) -> Dict[str, any]:
        """
        Execute a command locally using subprocess

        Args:
            command: Command to execute
            timeout: Command timeout in seconds

        Returns:
            Dict with stdout, stderr, exit_code, and execution time
        """
        if timeout is None:
            timeout = config.ssh_command_timeout

        try:
            start_time = time.time()

            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            execution_time = time.time() - start_time

            return {
                'success': result.returncode == 0,
                'exit_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'execution_time': round(execution_time, 2),
                'command': command,
                'execution_mode': 'local'
            }

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f'Command timed out after {timeout} seconds',
                'command': command,
                'execution_mode': 'local'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'command': command,
                'execution_mode': 'local'
            }

    def _get_friendly_error(self, error_type: str, details: str, server_config: dict) -> str:
        """Generate friendly, helpful error messages with troubleshooting steps"""
        if error_type == "key_not_found":
            server_host = server_config.get('host', 'unknown')
            return (
                f"🔑 SSH Key Not Found!\n\n"
                f"I couldn't find the SSH key at: {config.ssh_key_path}\n\n"
                f"💡 WAIT! If Sally is running ON {server_host}, you don't need SSH!\n"
                f"   Configure {server_host} to use localhost for local execution (faster, no keys needed):\n\n"
                f"   1. Edit sally/config.local.yaml:\n"
                f"      servers:\n"
                f"        prod:  # or whatever server name you're using\n"
                f"          host: localhost\n"
                f"          user: ubuntu\n"
                f"          description: Production Server (Local)\n\n"
                f"   2. Remove or comment out SSH_PRIVATE_KEY_PATH in sally/.env\n"
                f"   3. Restart Sally - she'll use local execution (subprocess) instead of SSH\n\n"
                f"Otherwise, if Sally is REMOTE from {server_host}, here's how to set up SSH:\n\n"
                f"1. Check if the key exists:\n"
                f"   ls -la {config.ssh_key_path}\n\n"
                f"2. If it doesn't exist, generate one:\n"
                f"   cd sally && python3 -c \"import paramiko; key = paramiko.RSAKey.generate(4096); key.write_private_key_file('sally_id_rsa'); pub = f'{{key.get_name()}} {{key.get_base64()}} sally-bot-ssh-key'; open('sally_id_rsa.pub', 'w').write(pub); print('✅ Key pair generated!'); print('Private: sally_id_rsa'); print('Public: sally_id_rsa.pub')\"\n\n"
                f"3. Update sally/.env to point to the key:\n"
                f"   SSH_PRIVATE_KEY_PATH=/var/www/bot-team/sally/sally_id_rsa\n\n"
                f"4. Copy the public key to your server:\n"
                f"   cat sally_id_rsa.pub\n"
                f"   # Then on {server_host}: echo \"<paste_the_public_key_here>\" >> ~/.ssh/authorized_keys\n\n"
                f"Error details: {details}"
            )
        elif error_type == "connection_failed":
            return (
                f"🔌 Connection Failed!\n\n"
                f"I couldn't connect to {server_config.get('host')} as user {server_config.get('user', config.ssh_default_user)}\n\n"
                f"Let's troubleshoot step-by-step:\n\n"
                f"1. Can you reach the server?\n"
                f"   ping {server_config.get('host')}\n\n"
                f"2. Is SSH running on the server?\n"
                f"   telnet {server_config.get('host')} 22\n\n"
                f"3. Try connecting manually with the same key:\n"
                f"   ssh -i {config.ssh_key_path} {server_config.get('user', config.ssh_default_user)}@{server_config.get('host')}\n\n"
                f"4. Check if the public key is installed on the server:\n"
                f"   # On the server, check: cat ~/.ssh/authorized_keys\n"
                f"   # It should contain the public key from: cat {config.ssh_key_path}.pub\n\n"
                f"5. Verify server firewall allows SSH (port 22):\n"
                f"   # On server: sudo ufw status\n\n"
                f"6. Check file permissions:\n"
                f"   # On server: chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys\n"
                f"   # Locally: chmod 600 {config.ssh_key_path}\n\n"
                f"Error details: {details}"
            )
        elif error_type == "server_not_configured":
            return (
                f"⚙️ Server Not Configured!\n\n"
                f"I don't know about a server called '{details}'.\n\n"
                f"To add it, edit sally/config.yaml:\n\n"
                f"servers:\n"
                f"  {details}:\n"
                f"    host: your-server.com\n"
                f"    user: ubuntu\n"
                f"    description: Your server description\n\n"
                f"Then restart me and try again!"
            )
        else:
            return f"Error: {details}"

    def _get_connection(self, server_name: str) -> paramiko.SSHClient:
        """Get or create SSH connection to server"""
        if server_name not in self.connections:
            servers = config.servers
            if server_name not in servers:
                raise ValueError(self._get_friendly_error("server_not_configured", server_name, {}))

            server_config = servers[server_name]
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Load private key
            try:
                private_key = paramiko.RSAKey.from_private_key_file(config.ssh_key_path)
            except FileNotFoundError as e:
                raise Exception(self._get_friendly_error("key_not_found", str(e), server_config))
            except Exception as e:
                raise Exception(self._get_friendly_error("key_not_found", str(e), server_config))

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
                raise Exception(self._get_friendly_error("connection_failed", str(e), server_config))

        return self.connections[server_name]

    def execute_command(
        self,
        server_name: str,
        command: str,
        timeout: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Execute a command on a server (local or remote)

        Automatically detects if the target server is the local machine and uses
        subprocess instead of SSH for better performance. Falls back to SSH for
        remote servers.

        Args:
            server_name: Name of the server from config
            command: Command to execute
            timeout: Command timeout in seconds (uses config default if None)

        Returns:
            Dict with stdout, stderr, exit_code, and execution time
        """
        if timeout is None:
            timeout = config.ssh_command_timeout

        # Get server config
        servers = config.servers
        if server_name not in servers:
            return {
                'success': False,
                'error': self._get_friendly_error("server_not_configured", server_name, {}),
                'server': server_name,
                'command': command
            }

        server_config = servers[server_name]

        # Check if this is a local server
        if self._is_local_server(server_config):
            result = self._execute_local(command, timeout)
            result['server'] = server_name
            return result

        # Remote server - use SSH
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
                'command': command,
                'execution_mode': 'ssh'
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
