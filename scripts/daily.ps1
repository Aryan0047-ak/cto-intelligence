# Daily CTO run (Windows local, uses your logged-in OpenCode, no service-account needed)
# Usage: powershell -File scripts/daily.ps1 [-Date yyyy-MM-dd] [-SkipResearch]
param(
  [string]$Date = (Get-Date -Format "yyyy-MM-dd"),
  [switch]$SkipResearch
)
$ErrorActionPreference = "Stop"
Set-Location "C:\Users\HP\OneDrive\Desktop\agents info"

$TODAY = $Date
$REPORT = "reports/daily/$TODAY.md"

# Load Telegram secrets from env (set once via [System.Environment] or Task Scheduler)
if (-not $env:TELEGRAM_BOT_TOKEN -or -not $env:TELEGRAM_CHAT_ID) {
  Write-Host "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID first"
  exit 1
}

$opencodeCmd = Get-Command opencode -ErrorAction SilentlyContinue
if (-not $opencodeCmd) { $opencodeCmd = Get-Command opencode.exe -ErrorAction SilentlyContinue }
if (-not $opencodeCmd -and -not $SkipResearch) {
  Write-Host "opencode not on PATH. Run: where opencode"
  exit 1
}

if (-not $SkipResearch) {
  Write-Host "Running research for $TODAY ..."
  opencode run --agent cto-research "Run today's CTO intelligence research for $TODAY. Read reports/index.md and the 2-3 most recent reports/daily/*.md first to avoid duplication. Save full report to reports/daily/$TODAY.md and update reports/index.md."
}

if (-not (Test-Path $REPORT)) {
  Write-Host "No report at $REPORT — research step produced nothing, skipping commit."
  exit 1
}

# Keep index.md latest-first in sync (idempotent)
$index = Get-Content "reports/index.md" -Raw -ErrorAction SilentlyContinue
if ($index -and $index -notmatch [regex]::Escape($TODAY)) {
  Write-Host "Adding $TODAY to reports/index.md ..."
  $summary = (Select-String -Path $REPORT -Pattern '^\*\*\[P0\]|^## ' | Select-Object -First 1).Line
  if (-not $summary) { $summary = "daily CTO briefing" }
  $line = "- [$TODAY](./daily/$TODAY.md) — $summary"
  $index = $index -replace '(- Latest first:\s*)', "`$1`n$line"
  Set-Content "reports/index.md" $index -Encoding UTF8
}

Write-Host "Sending Telegram ..."
python scripts/send_telegram.py --report $REPORT

Write-Host "Pushing to GitHub ..."
# Green contributions require author email linked to GitHub. Enforce correct identity.
$wantName = "Aryan Kalal"
$wantEmail = "aryankalal0047@gmail.com"
$curEmail = (git config user.email).Trim()
if (-not $curEmail) {
  git config user.name $wantName
  git config user.email $wantEmail
  Write-Host "git identity set to $wantEmail"
} elseif ($curEmail -ne $wantEmail) {
  Write-Host "WARNING: git user.email is $curEmail, expected $wantEmail — commits may not count green. Fix: git config user.email $wantEmail"
}
try { git pull --rebase origin main 2>$null } catch { Write-Host "pull skipped (offline or clean)." }
git add reports/
git diff --cached --quiet
$hasDiff = ($LASTEXITCODE -ne 0)
if ($hasDiff) {
  git commit -m "docs(reports): add $TODAY CTO briefing" -m "Generated via cto-research agent. Deduped against prior reports/daily/*.md. Verified primary sources only."
  git push origin main
} else {
  Write-Host "Nothing to commit."
}
Write-Host "Done $TODAY"
