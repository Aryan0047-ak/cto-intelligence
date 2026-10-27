"""Send daily CTO briefing to Telegram. Notification layer only - Markdown files are the database."""
import argparse
import os
import re

from report_utils import build_message, read_report

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def datestr_from_path(report_path: str) -> str:
    match = DATE_RE.search(report_path)
    return match.group(1) if match else "today"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--max-chars", type=int, default=4000)
    ap.add_argument("--dry-run", action="store_true", help="print message without sending")
    args = ap.parse_args()

    if not os.path.exists(args.report):
        print(f"report not found: {args.report}")
        raise SystemExit(1)

    text = build_message(
        read_report(args.report),
        datestr_from_path(args.report),
        args.report,
        args.max_chars,
    )

    # Dry-run is the local preview path, so it must not require secrets.
    if args.dry_run:
        print(text)
        print(f"dry-run {len(text)} chars")
        return

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID first")
        raise SystemExit(1)

    import requests  # lazily imported: dry-run and unit tests need no HTTP client

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=30,
    )
    response.raise_for_status()
    print("sent", len(text), "chars")


if __name__ == "__main__":
    main()
