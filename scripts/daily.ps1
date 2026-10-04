# Daily CTO run (Windows local, uses your logged-in OpenCode, no service-account needed)
$ErrorActionPreference = "Stop"
Set-Location "C:\Users\HP\OneDrive\Desktop\agents info"

$TODAY = Get-Date -Format "yyyy-MM-dd"

# Load Telegram secrets from env (set once via [System.Environment] or Task Scheduler)
if (-not $env:TELEGRAM_BOT_TOKEN -or -not $env:TELEGRAM_CHAT_ID) {
  Write-Host "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID first"
  exit 1
}

Write-Host "Running research for $TODAY ..."
opencode run --agent cto-research "Run today's CTO intelligence research for $TODAY. Read reports/index.md and the 2-3 most recent reports/daily/*.md first to avoid duplication. Save full report to reports/daily/$TODAY.md and update reports/index.md."

Write-Host "Sending Telegram ..."
python scripts/send_telegram.py --report "reports/daily/$TODAY.md"

Write-Host "Pushing to GitHub ..."
git add reports/
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
  git commit -m "CTO intelligence $TODAY"
  git push origin main
}
Write-Host "Done $TODAY"
