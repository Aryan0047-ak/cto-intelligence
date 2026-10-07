"""Send daily CTO briefing to Telegram. Notification layer only — Markdown files are the database."""
import argparse
import os
import re
import requests

def extract_top5(md: str) -> str:
    # Keep message short: first ~1500 chars of TOP 5 section if present
    m = re.search(r"(TOP 5.*?)(?=\n## |\n# |\Z)", md, re.S | re.I)
    section = m.group(1).strip() if m else md[:3000]
    return section[:3500]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--max-chars", type=int, default=4000)
    ap.add_argument("--dry-run", action="store_true", help="print message without sending")
    args = ap.parse_args()

    if not os.path.exists(args.report):
        print(f"report not found: {args.report}")
        raise SystemExit(1)

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID first")
        raise SystemExit(1)

    with open(args.report, encoding="utf-8") as f:
        md = f.read()

    date = re.search(r"(\d{4}-\d{2}-\d{2})", args.report)
    datestr = date.group(1) if date else "today"
    briefing = extract_top5(md)

    text = f"CTO Intelligence — {datestr}\n\n{briefing}\n\nFull report in repo: {args.report}"
    # Telegram limit 4096 chars — cut at line boundary when possible
    limit = min(args.max_chars, 4000)
    if len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        text = (text[:cut] if cut > limit // 2 else text[:limit]) + "\n…(truncated)"

    if args.dry_run:
        print(text)
        print(f"dry-run {len(text)} chars")
        return

    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=30,
    )
    r.raise_for_status()
    print("sent", len(text), "chars")

if __name__ == "__main__":
    main()
