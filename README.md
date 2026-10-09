# 🧠 CTO Intelligence Agent

> An LLM-powered daily research system that turns tech noise into 7 exceptional decisions.

[![Reports](https://img.shields.io/badge/Reports-daily-brightgreen?style=flat-square)](#-reports)
[![Agent](https://img.shields.io/badge/Agent-cto--research-blue?style=flat-square)](#-how-it-works)
[![Bot](https://img.shields.io/badge/Telegram-two--way-229ED9?style=flat-square&logo=telegram)](#-telegram-bot-phase-2)
[![Automation](https://img.shields.io/badge/Automation-PowerShell-5391FE?style=flat-square&logo=powershell)](#-daily-operation)
[![Model](https://img.shields.io/badge/Model-Muse_Spark-7C3AED?style=flat-square)](#-configuration)

**Problem:** 50-tab tech news diet, zero decisions.
**Solution:** One agent (`cto-research`) + one command (`/research`) + one daily report with TOP 5, actions, and primary sources — versioned in Git, pushed to Telegram, queryable via bot.

- 📅 Daily briefings in `reports/daily/YYYY-MM-DD.md`, indexed latest-first
- 🤖 Brutally selective: P0–P3 ranking, dedup vs prior reports, primary sources only
- 💬 Two-way Telegram bot: `/brief`, `/latest`, `/search`, `/ask`
- 🔁 Unattended daily run via `scripts/daily.ps1` + Windows Task Scheduler
- 🧾 Markdown files are the database. No server, no cost, fully offline-readable.

---

## 📋 Table of Contents

1. [How It Works](#-how-it-works)
2. [Quickstart](#-quickstart)
3. [Daily Operation](#-daily-operation)
4. [Telegram Bot (Phase 2)](#-telegram-bot-phase-2)
5. [Report Format](#-report-format)
6. [Project Structure](#-project-structure)
7. [Configuration](#-configuration)
8. [Engineering Capabilities Demonstrated](#-engineering-capabilities-demonstrated)
9. [Limitations & Roadmap](#-limitations--roadmap)

---

## 🔄 How It Works

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ 1. RESEARCH  │──▶│ 2. REPORT    │──▶│ 3. COMMIT    │──▶│ 4. NOTIFY +  │
│ cto-research │   │ daily/*.md + │   │ git push     │   │ QUERY        │
│ agent +      │   │ index.md     │   │ origin/main  │   │ Telegram     │
│ /research    │   │ deduped      │   │              │   │ bot          │
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
```

1. **Research** — `/research` (agent `cto-research`, model `opencode/muse-spark-1.3-contributor-free`) reads `reports/index.md` + 2–3 latest `reports/daily/*.md`, discovers via websearch, verifies against primary sources (GitHub releases, official changelogs, engineering blogs).
2. **Report** — Saves `reports/daily/YYYY-MM-DD.md`, updates `reports/index.md` latest-first. See [Report Format](#-report-format).
3. **Commit** — Conventional message (`docs(reports): add YYYY-MM-DD …`), `git pull --rebase` first, push only on change.
4. **Notify + Query** — `send_telegram.py` pushes TOP 5 to Telegram; `telegram_bot.py` answers `/brief`, `/search`, `/ask` from local Markdown.

**Key design rule:** components never invent data. Reports cite primary-source URLs. Bot fast paths (`/brief`, `/search`) read local files only; only `/ask` spends an LLM call.

---

## 🚀 Quickstart

### Prerequisites

- [OpenCode CLI](https://opencode.ai) logged in (`opencode auth list`)
- Python 3.10+ with `requests` (`pip install requests`)
- A Telegram bot token (via [@BotFather](https://t.me/BotFather))
- Git + GitHub access to this repo
- Windows (Task Scheduler) for unattended runs — manual runs work anywhere

### Run one briefing now

```bash
# 1. Configure secrets (never commit real tokens — see .env.example)
# PowerShell:
$env:TELEGRAM_BOT_TOKEN="123456:ABC..."
$env:TELEGRAM_CHAT_ID="123456789"

# 2. Interactive research (inside opencode)
/research

# ...or one-shot daily pipeline:
powershell -File scripts/daily.ps1 -Date 2026-10-09

# Dry-run the Telegram message without sending:
python scripts/send_telegram.py --report reports/daily/2026-10-09.md --dry-run
```

### Start the two-way bot

```bash
# Polling only. No server, no cost.
python scripts/telegram_bot.py
```

Then in Telegram: `/brief` for latest TOP 5, `/search nats` for local hits, `/ask <question>` for an AI answer (30–120s).

---

## 🗓️ Daily Operation

| Path | Purpose |
| ---- | ------- |
| `powershell -File scripts/daily.ps1` | Full pipeline: research → index sync → Telegram → commit → push |
| `scripts/daily.ps1 -SkipResearch` | Resend/commit existing `reports/daily/<Date>.md` without LLM call |
| Windows Task Scheduler | Unattended daily trigger (service-account keys rejected in CI, so local scheduling is primary) |
| `.github/workflows/daily-research.yml` | Manual `workflow_dispatch` fallback; scheduled cron is **disabled** (see file header) with `OPENCODE_API_KEY` secret documented |

`daily.ps1` guarantees green-graph hygiene:

- Enforces account-linked git identity (`Aryan Kalal <aryankalal0047@gmail.com>`), warns on mismatch
- Idempotent `reports/index.md` sync
- `git pull --rebase` before commit, push only when `git diff --cached` is non-empty

---

## 💬 Telegram Bot (Phase 2)

Polling bot in `scripts/telegram_bot.py` — uses local OpenCode login, no service key.

| Command | Behavior | Cost |
| ------- | -------- | ---- |
| `/brief` | TOP 5 from latest `reports/daily/*.md` | Free (local read) |
| `/latest` | Last 5 report filenames | Free |
| `/search <text>` | Grep `reports/` + `knowledge/` (max 8 hits) | Free |
| `/ask <question>` | `opencode run --agent cto-research`, ≤25 lines, local files first | 1 LLM call |
| any other text | Fast local search + hint to `/ask` | Free |

Chat lock: set `TELEGRAM_CHAT_ID` to restrict to your chat; empty = allow any (not recommended).

---

## 📝 Report Format

Every `reports/daily/YYYY-MM-DD.md` follows `.opencode/agents/cto-research.md`:

- **TOP 5 — MUST KNOW** — `[P0/P1] Title`, what happened, why it matters, technical impact, Build/Buy/Watch, action, relevance/novelty, primary source
- **AI Engineering** — coding agents, LLMs, MCP, inference, RAG, eval
- **Software Engineering & Architecture** — DBs, queues, workflows, APIs, search, graphs
- **DevOps / Cloud / Security** — AWS, K8s, CI/CD, observability, supply-chain
- **Regulated Enterprise Software** — QMS/LIMS/MES/eBMR, audit trails, e-signatures
- **Open Source to Watch** — repo, license, maturity, action (never stars-only)
- **Competitor / Market Intelligence** — capability, pricing, partnerships
- **What I Should Learn** — max 3, each with project + value
- **My Action List** — max 5: DO NOW / TEST THIS WEEK / READ / WATCH / IGNORE

Rules: P0 > P1 > P2 > P3. Ignore hype, clickbait, gossip, repeats. Secondary sources for discovery only; **primary sources for claims**. Honest gaps allowed ("No verified P0 from QMS vendors — honest gap preserved").

Latest: [2026-10-09](./reports/daily/2026-10-09.md) — NATS 2.15.1 final, Step 5 Preview, AWS $50M science credits.

---

## 📁 Project Structure

```
.
├── .opencode/
│   ├── agents/cto-research.md   # Agent role, priorities, report schema
│   └── commands/research.md     # /research workflow (dedup + save + index)
├── knowledge/                   # Long-term notes, promoted weekly (P0/P1 only)
│   ├── ai-agents.md  architecture.md  databases.md
│   ├── devops.md  pharma-software.md  competitors.md
├── reports/
│   ├── index.md                 # Latest-first briefing index
│   ├── daily/YYYY-MM-DD.md      # Ephemeral daily briefings
│   ├── weekly/.gitkeep  monthly/.gitkeep
├── scripts/
│   ├── daily.ps1                # Unattended pipeline + green-identity guard
│   ├── send_telegram.py         # TOP-5 push (--dry-run, --max-chars)
│   └── telegram_bot.py          # Polling two-way bot
├── sources/                     # Where to look: github.md, changelogs.md, rss.md
├── .github/workflows/daily-research.yml  # Manual fallback (schedule disabled)
├── opencode.jsonc               # model: muse-spark-1.3-contributor-free
└── .env.example                 # TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

---

## 🔧 Configuration

| Secret | Where | Purpose |
| ------ | ----- | ------- |
| `TELEGRAM_BOT_TOKEN` | env / Task Scheduler / repo secrets | Bot send + polling |
| `TELEGRAM_CHAT_ID` | env / Task Scheduler / repo secrets | Destination chat + bot allow-list |
| `OPENCODE_API_KEY` | repo secret, CI only | Zen free models in GitHub Actions (get from opencode.ai/console → API Keys) |
| `GIT_USER_NAME` / `GIT_USER_EMAIL` | repo secrets, CI only (optional) | Defaults: `Aryan Kalal` / `aryankalal0047@gmail.com` so CI commits count green |

Never commit real tokens. `.gitignore` covers `.env`; `scripts/` reads env at runtime.

---

## 🛠️ Engineering Capabilities Demonstrated

Honest mapping — only what exists in this repo:

| Discipline | Evidence in repo |
| ---------- | ---------------- |
| AI engineering | `cto-research.md` — LLM research workflow with ranked, sourced output |
| Agent engineering | Agent instructions + `/research` repeatable task, dedup discipline |
| Automation engineering | `daily.ps1` + Task Scheduler + idempotent index sync |
| Integration engineering | Telegram Bot API (push + polling commands), GitHub push |
| DevOps fundamentals | Git versioning, `daily-research.yml` fallback, secrets via env/repo secrets |
| Systems engineering | Agent → Markdown DB → bot → scheduler wired into one loop |
| Reliability fundamentals | Service-account CI failure diagnosed → local execution; `--dry-run`, missing-report guards |
| Knowledge engineering | `reports/` ephemeral + `knowledge/` promoted, `sources/` allow-list |

---

## 🧭 Limitations & Roadmap

What this project does **not** yet demonstrate (no claims made):

- Distributed systems at scale, Kubernetes operators, production cloud architecture
- MLOps pipelines, custom model training/eval harnesses
- Server-side auth, multi-user SaaS, real backend (Markdown files are the DB by design)
- `reports/weekly/` and `reports/monthly/` rollups (folders exist, automation pending)

Sensible next steps: weekly rollup job, link-checker for sources, eval harness comparing models on one SWE task, real backend swap behind `scripts/` interfaces.

---

*Built with OpenCode + Muse Spark. Markdown is the database. Selectivity is the feature.*
