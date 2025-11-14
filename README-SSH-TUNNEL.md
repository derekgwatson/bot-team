# Accessing Sally on Production

When Sally is running on your production server (localhost only), you can access her web interface using SSH tunneling.

## Windows (PowerShell)

```powershell
# Edit the server address in open-sally.ps1 first
.\open-sally.ps1
```

Or specify the server:
```powershell
.\open-sally.ps1 -Server "ubuntu@your-server.com"
```

The script will:
1. Create an SSH tunnel to your server
2. Forward port 8004 from prod to your local machine
3. Open your browser to http://localhost:8004
4. Keep the tunnel open until you press Ctrl+C

## Linux/Mac (Bash)

```bash
# One-liner
ssh -L 8004:localhost:8004 ubuntu@your-server.com -N &
open http://localhost:8004  # or 'xdg-open' on Linux

# Or use the script
chmod +x open-sally.sh
./open-sally.sh
```

## Manual SSH Tunnel

If you prefer to do it manually:

```bash
# Open tunnel
ssh -L 8004:localhost:8004 ubuntu@your-server.com

# In another terminal or browser
# Navigate to: http://localhost:8004
```

## How It Works

Sally on production listens only on `127.0.0.1:8004` (localhost), making her inaccessible from the internet. SSH tunneling:

1. Creates an encrypted SSH connection to your server
2. Forwards local port 8004 to the server's localhost:8004
3. Your browser connects to localhost:8004 on your machine
4. Traffic is securely tunneled to Sally on the server

This gives you full access to Sally's web interface while keeping her secure!

## Troubleshooting

**"Connection refused"**
- Make sure Sally is running on the production server
- Check that you can SSH to the server normally
- Verify Sally is listening on port 8004 (run `netstat -tlnp | grep 8004` on server)

**"Permission denied"**
- Make sure your SSH key is set up for the server
- Try connecting normally first: `ssh ubuntu@your-server.com`

**Browser shows "Connection closed"**
- The SSH tunnel may have closed
- Check the terminal for error messages
- Restart the script
