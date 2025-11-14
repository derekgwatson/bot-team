# open-sally.ps1
# Opens SSH tunnel to Sally on production server and launches browser

param(
    [string]$Server = "ubuntu@your-prod-server.com",
    [int]$LocalPort = 8004,
    [int]$RemotePort = 8004
)

Write-Host "🔌 Opening SSH tunnel to Sally on $Server..." -ForegroundColor Cyan

# Start SSH tunnel in background
$sshProcess = Start-Process -FilePath "ssh" `
    -ArgumentList "-L ${LocalPort}:localhost:${RemotePort}", "-N", $Server `
    -PassThru `
    -WindowStyle Hidden

if ($sshProcess) {
    Write-Host "✅ Tunnel established (PID: $($sshProcess.Id))" -ForegroundColor Green

    # Give SSH a moment to establish connection
    Start-Sleep -Seconds 2

    # Open browser
    Write-Host "🌐 Opening Sally in browser..." -ForegroundColor Cyan
    Start-Process "http://localhost:$LocalPort"

    Write-Host ""
    Write-Host "Sally is now accessible at http://localhost:$LocalPort" -ForegroundColor Yellow
    Write-Host "Press Ctrl+C to close tunnel and exit" -ForegroundColor Yellow
    Write-Host ""

    # Wait for Ctrl+C
    try {
        while ($true) {
            Start-Sleep -Seconds 1

            # Check if SSH process is still running
            if ($sshProcess.HasExited) {
                Write-Host "❌ SSH tunnel closed unexpectedly" -ForegroundColor Red
                break
            }
        }
    }
    finally {
        # Clean up
        if (-not $sshProcess.HasExited) {
            Write-Host "👋 Closing tunnel..." -ForegroundColor Cyan
            Stop-Process -Id $sshProcess.Id -Force
        }
        Write-Host "Goodbye! 👋" -ForegroundColor Green
    }
}
else {
    Write-Host "❌ Failed to start SSH tunnel" -ForegroundColor Red
    Write-Host "Make sure SSH is available and you can connect to $Server" -ForegroundColor Yellow
    exit 1
}
