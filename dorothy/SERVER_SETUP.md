# Dorothy Server Setup Guide

This guide explains how to configure your production server to work with Dorothy's automated deployment system.

## Prerequisites

- Ubuntu/Debian server with sudo access
- SSH access to the server
- Python 3.8+ installed on the server
- Nginx and systemd installed

## 1. Create Deployment User (if needed)

If you don't already have a deployment user:

```bash
sudo adduser derek
sudo usermod -aG sudo derek
```

## 2. Configure Passwordless Sudo

Dorothy needs to run certain commands with sudo privileges during deployment. Create a sudoers file specifically for deployment automation:

```bash
sudo visudo -f /etc/sudoers.d/dorothy-deploy
```

Add the following (replace `derek` with your SSH username):

```bash
# Dorothy deployment automation - passwordless sudo for specific commands
derek ALL=(ALL) NOPASSWD: /usr/sbin/nginx -t
derek ALL=(ALL) NOPASSWD: /bin/systemctl reload nginx
derek ALL=(ALL) NOPASSWD: /bin/systemctl restart *
derek ALL=(ALL) NOPASSWD: /bin/systemctl enable *
derek ALL=(ALL) NOPASSWD: /bin/systemctl disable *
derek ALL=(ALL) NOPASSWD: /bin/systemctl daemon-reload
derek ALL=(ALL) NOPASSWD: /bin/systemctl is-active *
derek ALL=(ALL) NOPASSWD: /bin/systemctl status *
derek ALL=(ALL) NOPASSWD: /usr/bin/tee /etc/nginx/sites-available/*
derek ALL=(ALL) NOPASSWD: /bin/ln -sf /etc/nginx/sites-available/* /etc/nginx/sites-enabled/*
derek ALL=(ALL) NOPASSWD: /bin/mkdir -p *
derek ALL=(ALL) NOPASSWD: /bin/chown -R www-data\:www-data *
derek ALL=(ALL) NOPASSWD: /usr/bin/git *
derek ALL=(ALL) NOPASSWD: /usr/bin/test -f *
derek ALL=(ALL) NOPASSWD: /usr/bin/openssl x509 *
derek ALL=(ALL) NOPASSWD: /usr/bin/certbot *
derek ALL=(ALL) NOPASSWD: /bin/su -c * www-data
```

**Security Note:** This configuration grants passwordless sudo only for specific deployment-related commands, not full system access.

## 3. Set Up SSH Key Authentication

Dorothy uses SSH to connect to your server through Sally. Configure SSH key authentication:

### On your Dorothy/Sally server:

1. Generate SSH key pair (if not already done):
   ```bash
   ssh-keygen -t ed25519 -C "sally-deployment"
   ```

2. Copy the public key:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```

### On your production server:

3. Add the public key to authorized_keys:
   ```bash
   mkdir -p ~/.ssh
   chmod 700 ~/.ssh
   echo "YOUR_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   ```

4. Test SSH connection (from Dorothy/Sally server):
   ```bash
   ssh derek@your-production-server.com
   ```

## 4. Configure Sally with Production Server

Create `sally/config.local.yaml`:

```yaml
servers:
  production:
    host: your-production-server.com
    port: 22
    username: derek
    key_file: /home/user/.ssh/id_ed25519
```

## 5. Create Required Directories

On the production server, create directories for deployments:

```bash
sudo mkdir -p /var/www/bot-team
sudo chown derek:derek /var/www/bot-team
```

## 6. Install Server Dependencies

Ensure required packages are installed:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx git
```

## 7. Configure Dorothy with Production Server

In `dorothy/config.local.yaml`, set your default server:

```yaml
deployment:
  default_server: production

defaults:
  repo: git@github.com:yourorg/bot-team.git
  domain: "{bot_name}.yourdomain.com"

bots:
  fred:
    description: Google Workspace User Management
    nginx_config_name: fred  # Override if your nginx config has a different name
```

## 8. Verify Setup

Test that Dorothy can connect and verify the server configuration:

1. Start Sally and Dorothy
2. In Dorothy's web UI, click "Verify" on a bot
3. Review the verification results

Expected checks:
- ❌ Nginx config (will fail until first deployment)
- ❌ Gunicorn service (will fail until first deployment)
- ❌ SSL certificate (will fail until certbot is run)
- ❌ Repository (will fail until first deployment)
- ❌ Virtualenv (will fail until first deployment)
- ✅ Permissions (should pass if directories exist)

## 9. Deploy Your First Bot

Once verification shows that Dorothy can connect and run sudo commands:

1. Click "Deploy" on a bot in Dorothy's web UI
2. Monitor the deployment progress
3. After deployment, run verification again - more checks should pass

## 10. Set Up SSL (Optional)

For production deployments with SSL:

```bash
sudo certbot --nginx -d yourdomain.com --non-interactive --agree-tos --email your@email.com
```

Or use Dorothy's SSL setup feature in the web UI.

## Troubleshooting

### "Permission denied" errors
- Check that passwordless sudo is configured correctly
- Verify the sudoers file syntax: `sudo visudo -c -f /etc/sudoers.d/dorothy-deploy`

### SSH connection failures
- Verify SSH key is in authorized_keys
- Check SSH service is running: `sudo systemctl status ssh`
- Test connection manually: `ssh derek@your-server.com`

### Sudo password prompts
- Ensure `/etc/sudoers.d/dorothy-deploy` exists and has correct permissions (0440)
- Check file ownership: `ls -la /etc/sudoers.d/dorothy-deploy`
- Verify syntax with visudo

### Deployment failures
- Check Dorothy logs for detailed error messages
- Verify Sally can connect: Test in Sally's web UI
- Review the deployment plan before executing
