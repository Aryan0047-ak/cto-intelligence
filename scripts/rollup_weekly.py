"""Roll one ISO week of daily briefings into a single review sheet.

``reports/weekly/`` existed as an empty folder and the README listed weekly
rollups as "automation pending". This is that automation - deterministic, no
LLM call and no network:

* reads the ``reports/daily/YYYY-MM-DD.md`` files inside the target week
* dedupes TOP 5 headlines and action items across those days
* unions the primary sources, normalised so tracking params do not double-count
* reports which weekdays have no briefing, so gaps stay visible

Usage::

    python scripts/rollup_weekly.py                    # current week
    python scripts/rollup_weekly.py --date 2026-10-12  # any day inside the week
    python scripts/rollup_weekly.py --date 2026-10-12 --stdout
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

from report_utils import extract_urls, find_section, normalize_url, read_report

ROOT = Path(__file__).resolve().parents[1]

FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
BULLET_RE = re.compile(r"^\s*(?:[-*]\s+|\*\*\[P\d\]\s*)")
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def week_bounds(day: dt.date) -> tuple[dt.date, dt.date]:
    """Return the Monday and Sunday of the ISO week containing ``day``."""
    monday = day - dt.timedelta(days=day.weekday())
    return monday, monday + dt.timedelta(days=6)


def week_label(day: dt.date) -> str:
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def collect_reports(reports_dir: Path, start: dt.date, end: dt.date) -> dict[dt.date, Path]:
    found: dict[dt.date, Path] = {}
    if not reports_dir.is_dir():
        return found
    for path in sorted(reports_dir.glob("*.md")):
        match = FILENAME_RE.match(path.name)
        if not match:
            continue
        day = dt.date.fromisoformat(match.group(1))
        if start <= day <= end:
            found[day] = path
    return found


def extract_bullets(section: str | None) -> list[str]:
    """Pull list items and ``**[P0]**`` headlines out of a section."""
    if not section:
        return []
    items: list[str] = []
    for line in section.splitlines():
        if not BULLET_RE.match(line):
            continue
        text = BULLET_RE.sub("", line).strip().strip("*").strip()
        if text:
            items.append(re.sub(r"\s+", " ", text))
    return items


def dedupe(items: list[str]) -> list[str]:
    """Case- and punctuation-insensitive dedupe that keeps first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = re.sub(r"[^a-z0-9]+", "", item.lower())
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def build_rollup(day: dt.date, reports_dir: Path) -> tuple[str, dict[str, object]]:
    """Render the weekly sheet for the ISO week containing ``day``."""
    start, end = week_bounds(day)
    reports = collect_reports(reports_dir, start, end)

    highlights: list[str] = []
    actions: list[str] = []
    sources: set[str] = set()
    rows: list[str] = []

    for current, path in sorted(reports.items()):
        md = read_report(path)
        highlights.extend(extract_bullets(find_section(md, "top 5")))
        actions.extend(extract_bullets(find_section(md, "my action list")))
        sources |= {normalize_url(url) for url in extract_urls(md)}
        rows.append(
            f"| {current.isoformat()} ({WEEKDAYS[current.weekday()]}) "
            f"| [{path.stem}](../daily/{path.name}) "
            f"| {len(extract_urls(md))} |"
        )

    covered = set(reports)
    missing = [
        f"{start + dt.timedelta(days=offset)}"
        for offset in range(7)
        if start + dt.timedelta(days=offset) not in covered
    ]

    unique_highlights = dedupe(highlights)
    unique_actions = dedupe(actions)

    lines = [
        f"# CTO Intelligence - Week {week_label(day)[-2:]}",
        "",
        f"**Window:** {start.isoformat()} to {end.isoformat()}  ",
        f"**Briefings:** {len(reports)} of 7 days  ",
        f"**Unique sources:** {len(sources)}",
        "",
        "## Daily coverage",
        "",
        "| Day | Briefing | Sources |",
        "| --- | --- | --- |",
        *(rows or ["| - | no briefings found | 0 |"]),
        "",
        f"**Missing days:** {', '.join(missing) if missing else 'none'}",
        "",
        "## Highlights (deduped across the week)",
        "",
        *(f"- {item}" for item in unique_highlights),
        *([] if unique_highlights else ["- none"]),
        "",
        "## Actions carried forward",
        "",
        *(f"- {item}" for item in unique_actions),
        *([] if unique_actions else ["- none"]),
        "",
        "## Sources",
        "",
        *(f"- https://{url}" for url in sorted(sources)),
        *([] if sources else ["- none"]),
        "",
    ]

    stats = {
        "week": week_label(day),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "briefings": len(reports),
        "missing": missing,
        "highlights": len(unique_highlights),
        "actions": len(unique_actions),
        "sources": len(sources),
    }
    return "\n".join(lines), stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Roll a week of dailies into one sheet.")
    parser.add_argument("--date", help="any date inside the target week (default: today)")
    parser.add_argument("--reports-dir", default="reports/daily", help="folder with daily briefings")
    parser.add_argument("--out-dir", default="reports/weekly", help="folder for the weekly sheet")
    parser.add_argument("--stdout", action="store_true", help="print instead of writing a file")
    parser.add_argument("--force", action="store_true", help="overwrite an existing weekly sheet")
    args = parser.parse_args(argv)

    day = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    reports_dir = Path(args.reports_dir)
    if not reports_dir.is_absolute():
        reports_dir = ROOT / reports_dir

    markdown, stats = build_rollup(day, reports_dir)
    if not stats["briefings"]:
        print(f"no briefings found in {stats['start']}..{stats['end']}")
        return 1

    if args.stdout:
        print(markdown)
        return 0

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{stats['week']}.md"

    if target.exists() and not args.force:
        print(f"{target} already exists (use --force to overwrite)")
        return 1

    target.write_text(markdown, encoding="utf-8")
    print(
        f"wrote {target} "
        f"({stats['briefings']} briefings, {stats['sources']} sources, "
        f"{stats['highlights']} highlights)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
