---
description: Run the daily CTO technology intelligence research
agent: cto-research
---

Run today's CTO intelligence research.

Date: use today's date in YYYY-MM-DD format. Run `date /T` on Windows or `date +%F` on Linux to confirm if unsure.

Research the latest relevant developments since the previous report in reports/daily/. Read reports/index.md and the 2-3 most recent daily reports first to avoid duplication.

Use the research priorities and output structure defined by the cto-research agent.

Do not repeat previously reported information unless there is a meaningful update.

Save the final full report as:

reports/daily/YYYY-MM-DD.md

Also update reports/index.md with a 3-line summary link.

Use websearch and webfetch for discovery, then verify important items against primary sources (official docs, GitHub releases, changelogs, engineering blogs).

At the end, provide a concise summary of the 5 most important discoveries and the recommended actions.

$ARGUMENTS
