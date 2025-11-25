# Merge the latest claude/* feature branch into main, then optionally delete it
# Usage:
#   .\merge-feature.ps1                # Find latest claude/* branch
#   .\merge-feature.ps1 "feature/*"    # Use different pattern
#   .\merge-feature.ps1 my-branch      # Merge specific branch

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
function Write-Err { param($Message) Write-Host "[ERROR] $Message" -ForegroundColor Red }

function Write-Header {
    param($Message)
    Write-Host ""
    Write-Host "== $Message ==" -ForegroundColor White
    Write-Host ""
}

Write-Header "Merge Feature Branch into $MainBranch"

Write-Info "Branch pattern: $BranchPattern"

Write-Info "Fetching latest from $Remote..."
git fetch $Remote --prune
if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }

Write-Info "Checking for uncommitted changes..."
$diffOutput = git diff --quiet 2>&1
$diffCachedOutput = git diff --cached --quiet 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Err "You have uncommitted changes. Commit or stash them first."
    exit 1
}

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

# Confirm merge
$reply = Read-Host "Merge '$LocalBranch' into $MainBranch? [Y/n]"
if ($reply -match '^[nN]') {
    Write-Warn "Merge cancelled."
    exit 0
}

# Update main first
Write-Header "Updating $MainBranch"
git checkout $MainBranch
if ($LASTEXITCODE -ne 0) { throw "git checkout failed" }

git pull $Remote $MainBranch
if ($LASTEXITCODE -ne 0) { throw "git pull failed" }

# Ensure local tracking branch exists and is up to date
Write-Info "Ensuring local branch '$LocalBranch' is up to date..."
$localBranchExists = git show-ref --verify --quiet "refs/heads/$LocalBranch" 2>$null
if ($LASTEXITCODE -eq 0) {
    git checkout $LocalBranch
    git reset --hard $LatestRemoteBranch
} else {
    git checkout -b $LocalBranch $LatestRemoteBranch
}
if ($LASTEXITCODE -ne 0) { throw "Failed to setup local branch" }

# Merge
Write-Header "Merging $LocalBranch into $MainBranch"
git checkout $MainBranch
if ($LASTEXITCODE -ne 0) { throw "git checkout failed" }

git merge --no-ff $LocalBranch -m "Merge $LocalBranch into $MainBranch"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Err "Merge conflict! Resolve conflicts, then run:"
    Write-Host "  git add <fixed files>"
    Write-Host "  git commit"
    Write-Host "  git push $Remote $MainBranch"
    exit 1
}

Write-Info "Pushing $MainBranch to $Remote..."
git push $Remote $MainBranch
if ($LASTEXITCODE -ne 0) { throw "git push failed" }

Write-Success "Merge complete!"

# Prompt for branch deletion
Write-Header "Cleanup"

Write-Host ""
$reply = Read-Host "Delete branch '$LocalBranch' (local and remote)? [Y/n]"
if ($reply -match '^[nN]') {
    Write-Warn "Keeping branch '$LocalBranch'."
} else {
    # Temporarily allow errors so git stderr doesn't cause exceptions
    $ErrorActionPreference = "Continue"

    Write-Info "Deleting local branch '$LocalBranch'..."
    $null = git branch -d $LocalBranch 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Local branch deleted."
    } else {
        Write-Warn "Could not delete local branch (maybe already gone?)."
    }

    Write-Info "Deleting remote branch '$Remote/$LocalBranch'..."
    $null = git push $Remote --delete $LocalBranch 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Remote branch deleted."
    } else {
        Write-Warn "Could not delete remote branch (maybe already gone?)."
    }

    $ErrorActionPreference = "Stop"
}

Write-Host ""
Write-Success "Done!"
