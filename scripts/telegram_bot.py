"""Phase 2: two-way Telegram CTO bot (Windows local, uses your OpenCode login).
Polling only. No server, no cost. Fast local answers, optional AI via `opencode run`.

Commands:
  /start /help -> help
  /brief -> TOP 5 from latest reports/daily/*.md
  /latest -> list last 5 reports
  /search <text> -> grep reports + knowledge
  /ask <question> -> opencode cto-research (slow, 30-120s)
  any other text -> fast search
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "daily"
KNOW = ROOT / "knowledge"
OFFSET_FILE = ROOT / ".telegram_offset"

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ALLOW = os.environ.get("TELEGRAM_CHAT_ID", "")  # lock to your chat; empty = allow any
API = f"https://api.telegram.org/bot{TOKEN}/" if TOKEN else ""

def api(method, **kwargs):
    r = requests.post(API + method, json=kwargs, timeout=35)
    r.raise_for_status()
    return r.json()

def send(chat_id, text):
    if len(text) > 4000:
        text = text[:4000] + "\n...(truncated)"
    api("sendMessage", chat_id=chat_id, text=text, disable_web_page_preview=True)

def latest_reports(n=5):
    files = sorted(REPORTS.glob("2*.md"), reverse=True)
    return files[:n]

def read_top5(md_path: Path) -> str:
    md = md_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"(TOP 5.*?)(?=\n## |\n# |\Z)", md, re.S | re.I)
    sec = m.group(1).strip() if m else md[:3000]
    return sec[:3500]

def fast_search(query: str, limit=5):
    q = query.lower()
    hits = []
    for base in (REPORTS, KNOW):
        if not base.exists():
            continue
        for p in sorted(base.glob("*.md"), reverse=True)[:30]:
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for line in txt.splitlines():
                if q in line.lower() and len(line.strip()) > 20:
                    hits.append(f"{p.name}: {line.strip()[:200]}")
                    if len(hits) >= limit:
                        return hits
    return hits

def ai_ask(question: str, timeout=150) -> str:
    # Uses local OpenCode login (no service key needed). Slow.
    cmd = [
        "opencode", "run", "--agent", "cto-research",
        f"Answer concisely (max 25 lines) using reports/daily/*.md and knowledge/*.md first, then general knowledge. Question: {question}",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(ROOT))
        txt = (out.stdout or "") + ("\n" + out.stderr if out.stderr else "")
        txt = txt.strip()
        return txt[-3500:] if len(txt) > 3500 else (txt or "(empty AI reply)")
    except subprocess.TimeoutExpired:
        return "AI timed out after ~2.5 min. Try a narrower /ask."
    except Exception as e:
        return f"AI error: {e}"

HELP = (
    "CTO bot commands:\n"
    "/brief - TOP 5 from latest report\n"
    "/latest - list recent reports\n"
    "/search <text> - fast search reports+knowledge\n"
    "/ask <question> - AI answer via cto-research (slow)\n"
    "Just send text to fast-search."
)

def handle(chat_id, text):
    t = (text or "").strip()
    if t in ("/start", "/help", "hi", "hello"):
        send(chat_id, "CTO bot online.\n" + HELP)
    elif t == "/brief":
        reps = latest_reports(1)
        if not reps:
            send(chat_id, "No reports yet. Run /research in OpenCode.")
        else:
            send(chat_id, f"{reps[0].stem}\n\n{read_top5(reps[0])}")
    elif t == "/latest":
        reps = latest_reports(5)
        send(chat_id, "Recent:\n" + ("\n".join("- " + r.name for r in reps) if reps else "(none)"))
    elif t.startswith("/search "):
        q = t[8:].strip()
        hits = fast_search(q, 8)
        send(chat_id, f"Search '{q}':\n" + ("\n".join("- " + h for h in hits) if hits else "(no hits)"))
    elif t.startswith("/ask "):
        q = t[5:].strip()
        send(chat_id, "Researching (30-120s)...")
        send(chat_id, ai_ask(q))
    else:
        hits = fast_search(t, 5)
        if hits:
            send(chat_id, "From your base:\n" + "\n".join("- " + h for h in hits) + "\n\nUse /ask for AI answer.")
        else:
            send(chat_id, "No local hit. Use /ask <question> for AI, or /brief for latest.\n" + HELP)

def main():
    if not TOKEN:
        print("Set TELEGRAM_BOT_TOKEN first")
        sys.exit(1)
    offset = int(OFFSET_FILE.read_text().strip()) if OFFSET_FILE.exists() else 0
    print(f"bot polling as {API[:40]}... allow_chat={CHAT_ALLOW or 'any'}")
    while True:
        try:
            r = requests.get(API + "getUpdates", params={"offset": offset, "timeout": 30}, timeout=35).json()
            for u in r.get("result", []):
                offset = max(offset, u["update_id"] + 1)
                OFFSET_FILE.write_text(str(offset))
                msg = u.get("message") or {}
                chat_id = str((msg.get("chat") or {}).get("id", ""))
                text = msg.get("text", "")
                if not chat_id or not text:
                    continue
                if CHAT_ALLOW and chat_id != CHAT_ALLOW:
                    continue
                print(f"<- {chat_id}: {text[:80]}")
                try:
                    handle(chat_id, text)
                except Exception as e:
                    print("handle error", e)
                    try:
                        send(chat_id, f"error: {e}")
                    except Exception:
                        pass
        except Exception as e:
            print("poll error", e)
            time.sleep(5)

if __name__ == "__main__":
    main()
