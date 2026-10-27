"""Shared Markdown parsing for the daily CTO briefing.

Both the notifier (``send_telegram.py``) and the bot (``telegram_bot.py``)
display the "TOP 5" block. Each used to carry its own copy of a regex whose
lookahead stopped only at level-2 headings::

    r"(TOP 5.*?)(?=\\n## |\\n# |\\Z)"

Reports are written with level-3 headings (``### TOP 5 - MUST KNOW``), so the
lookahead never matched and the *whole document* was truncated to 3500
characters instead of just the TOP 5 section. This module owns the parsing
rule once, so the two call sites cannot drift again.
"""
from __future__ import annotations

import re
from pathlib import Path

TOP5_LIMIT = 3500
MESSAGE_LIMIT = 4000
TRUNCATION_MARKER = "\n...(truncated)"

_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.MULTILINE)


def find_section(md: str, title_prefix: str) -> str | None:
    """Return one section (heading line + body) whose title starts with the prefix.

    A section ends at the next heading of *any* level, which is what makes this
    safe for reports that switch between ``##`` and ``###``.
    """
    prefix = title_prefix.strip().lower()
    headings = list(_HEADING.finditer(md))
    for index, match in enumerate(headings):
        if not match.group(2).strip().lower().startswith(prefix):
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(md)
        return md[match.start():end].strip()
    return None


def extract_top5(md: str, limit: int = TOP5_LIMIT) -> str:
    """Return the TOP 5 section, falling back to the document head.

    The fallback keeps notifications useful if a report is malformed; the
    validator (``validate_report.py``) is what rejects malformed reports.
    """
    section = find_section(md, "top 5")
    if section is None:
        section = md.strip()
    return section[:limit].rstrip()


def read_report(path: str | Path) -> str:
    """Read a report as UTF-8, tolerating files written by older Windows shells."""
    return Path(path).read_text(encoding="utf-8", errors="replace")


def build_message(
    md: str,
    datestr: str,
    report_path: str,
    limit: int = MESSAGE_LIMIT,
) -> str:
    """Build the Telegram message body, truncated at a line boundary.

    Telegram rejects messages over 4096 characters, so ``limit`` is clamped to
    :data:`MESSAGE_LIMIT` no matter what the caller asks for.
    """
    limit = max(200, min(limit, MESSAGE_LIMIT))
    text = f"CTO Intelligence - {datestr}\n\n{extract_top5(md)}\n\nFull report in repo: {report_path}"
    if len(text) <= limit:
        return text

    budget = limit - len(TRUNCATION_MARKER)
    cut = text.rfind("\n", 0, budget)
    if cut < budget // 2:  # no useful line break: hard-cut instead of dropping the body
        cut = budget
    return text[:cut] + TRUNCATION_MARKER
