# Release script for Monica Chrome Extension
# PowerShell version for Windows

$ErrorActionPreference = "Stop"

$EXTENSION_DIR = "monica-chrome-extension"

Write-Host "`n🚀 Building Monica Store Monitor" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Check we're in the right directory
if (-not (Test-Path $EXTENSION_DIR)) {
    Write-Host "❌ Error: Run this from bot-team\ directory" -ForegroundColor Red
    exit 1
}

# Read version from manifest.json
$manifestPath = Join-Path $EXTENSION_DIR "manifest.json"
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
$VERSION = $manifest.version

Write-Host "Version: $VERSION" -ForegroundColor Green

# Check for uncommitted changes
try {
    $gitStatus = git status --porcelain
    if ($gitStatus) {
        Write-Host "⚠️  Warning: You have uncommitted changes" -ForegroundColor Yellow
        $response = Read-Host "Continue anyway? (y/N)"
        if ($response -ne "y" -and $response -ne "Y") {
            exit 1
        }
    }
} catch {
    Write-Host "⚠️  Warning: Could not check git status" -ForegroundColor Yellow
}

# Create ZIP package
$ZIP_NAME = "monica-monitor-v$VERSION.zip"

Write-Host "`n📦 Creating package: $ZIP_NAME" -ForegroundColor Cyan

# Remove old ZIP if it exists
if (Test-Path $ZIP_NAME) {
    Remove-Item $ZIP_NAME -Force
}

# Create ZIP using PowerShell's Compress-Archive
# We need to exclude certain files
$filesToZip = Get-ChildItem -Path $EXTENSION_DIR -Recurse | Where-Object {
    $_.FullName -notmatch '\.py$' -and
    $_.FullName -notmatch '\.git' -and
    $_.FullName -notmatch '\.DS_Store' -and
    $_.Name -ne 'create_icons.py' -and
    $_.Name -ne 'create_simple_icons.py'
}

# Create a temporary directory structure
$tempDir = "temp_extension_build"
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir | Out-Null

# Copy files maintaining structure
foreach ($file in $filesToZip) {
    if ($file -is [System.IO.DirectoryInfo]) {
        continue
    }

    $relativePath = $file.FullName.Substring((Get-Location).Path.Length + 1)
    $targetPath = Join-Path $tempDir $relativePath
    $targetDir = Split-Path $targetPath -Parent

    if (-not (Test-Path $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }

    Copy-Item $file.FullName $targetPath
}

# Create the ZIP
Compress-Archive -Path "$tempDir\$EXTENSION_DIR\*" -DestinationPath $ZIP_NAME -Force

# Clean up temp directory
Remove-Item $tempDir -Recurse -Force

Write-Host "✅ Package created: $ZIP_NAME" -ForegroundColor Green

# Show next steps
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Go to https://chrome.google.com/webstore/devconsole"
Write-Host "2. Click on Monica Store Monitor"
Write-Host "3. Upload $ZIP_NAME"
Write-Host "4. Submit for review"
Write-Host "`nCurrent version: $VERSION" -ForegroundColor Cyan
Write-Host ""
