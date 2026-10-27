"""Tests for the Telegram notifier.

The important one is the dry-run test: the preview path used to require bot
secrets, so you could not check a message locally without exporting tokens.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import send_telegram

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "send_telegram.py"
REPORT = REPO / "reports" / "daily" / "2026-10-12.md"


def run_script(*args, drop_secrets=True):
    env = dict(os.environ)
    if drop_secrets:
        for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
            env.pop(key, None)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120,
    )


def test_datestr_from_path():
    assert send_telegram.datestr_from_path("reports/daily/2026-10-12.md") == "2026-10-12"
    assert send_telegram.datestr_from_path("report.md") == "today"


def test_dry_run_works_without_secrets():
    proc = run_script("--report", str(REPORT), "--dry-run")
    assert proc.returncode == 0, proc.stderr
    assert "CTO Intelligence - 2026-10-12" in proc.stdout
    assert "TOP 5" in proc.stdout
    # Only the TOP 5 block is sent; the next heading must not leak in.
    assert "### AI ENGINEERING" not in proc.stdout


def test_dry_run_respects_max_chars():
    proc = run_script("--report", str(REPORT), "--dry-run", "--max-chars", "800")
    assert proc.returncode == 0, proc.stderr
    match = re.search(r"dry-run (\d+) chars", proc.stdout)
    assert match, proc.stdout[-200:]
    assert int(match.group(1)) <= 800


def test_missing_report_exits_nonzero(tmp_path):
    proc = run_script("--report", str(tmp_path / "2026-10-12.md"), "--dry-run")
    assert proc.returncode == 1
    assert "report not found" in proc.stdout
