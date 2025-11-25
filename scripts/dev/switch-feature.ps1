# Fetch latest and switch to the most recent feature branch
# Usage:
#   .\switch-feature.ps1                # Find latest claude/* branch
#   .\switch-feature.ps1 "feature/*"    # Use different pattern

param(
    [string]$BranchPattern = "claude/*"
)

$ErrorActionPreference = "Stop"

# ==== Config ====
$MainBranch = "main"
$Remote = "origin"

# ==== Colours ====
function Write-Info { param($Message) Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Success { param($Message) Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
function Write-Warn { param($Message) Write-Host "[WARNING] $Message" -ForegroundColor Yellow }

Write-Info "Fetching latest from $Remote..."
git fetch $Remote --prune
if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }

Write-Info "Pulling $MainBranch..."
git pull $Remote $MainBranch
if ($LASTEXITCODE -ne 0) { throw "git pull failed" }

# Find the latest matching branch
Write-Info "Finding latest remote branch matching: $BranchPattern"
$LatestRemoteBranch = git for-each-ref --sort=-committerdate --format='%(refname:short)' "refs/remotes/$Remote/$BranchPattern" | Select-Object -First 1

if (-not $LatestRemoteBranch) {
    Write-Warn "No remote branches found matching '$BranchPattern'."
    exit 0
}

$LocalBranch = $LatestRemoteBranch -replace "^$Remote/", ""

Write-Host ""
Write-Info "Latest matching branch: $LocalBranch"

# Show recent commits
Write-Host ""
Write-Info "Recent commits on this branch:"
git log --oneline -5 $LatestRemoteBranch 2>$null | ForEach-Object { Write-Host "    $_" }
Write-Host ""

Write-Info "Switching to $LocalBranch..."
git switch --track $LatestRemoteBranch
if ($LASTEXITCODE -ne 0) { throw "git switch failed" }

Write-Host ""
Write-Success "Now on branch '$LocalBranch'"
