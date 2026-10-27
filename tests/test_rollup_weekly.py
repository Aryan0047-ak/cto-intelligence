"""Tests for the weekly rollup generator."""
import datetime as dt
from pathlib import Path

import pytest

import rollup_weekly as rw


def make_daily(path: Path, headline: str, action: str, urls=("https://example.com/a",)):
    body = "\n".join(
        [
            "### TOP 5 - MUST KNOW",
            f"**[P0] {headline}**",
            "What happened: detail.",
            "### AI ENGINEERING",
            "body long enough to be realistic.",
            "### MY ACTION LIST",
            f"- {action}",
            "",
            *[f"Source: {u}" for u in urls],
            "",
        ]
    )
    path.write_text(body, encoding="utf-8")
    return path


def test_week_bounds_are_monday_to_sunday():
    start, end = rw.week_bounds(dt.date(2026, 10, 27))  # Tuesday
    assert start == dt.date(2026, 10, 26)
    assert end == dt.date(2026, 11, 1)


def test_week_label_is_iso():
    assert rw.week_label(dt.date(2026, 10, 27)) == "2026-W44"


def test_collect_reports_ignores_other_weeks(tmp_path):
    make_daily(tmp_path / "2026-10-26.md", "in week", "DO NOW: x")
    make_daily(tmp_path / "2026-10-27.md", "in week too", "DO NOW: y")
    make_daily(tmp_path / "2026-10-25.md", "previous week", "DO NOW: z")
    start, end = rw.week_bounds(dt.date(2026, 10, 27))
    found = rw.collect_reports(tmp_path, start, end)
    assert sorted(d.isoformat() for d in found) == ["2026-10-26", "2026-10-27"]


def test_extract_bullets_handles_headlines_and_lists():
    section = "### TOP 5 - MUST KNOW\n**[P1] Something big**\n- supporting detail\nprose line\n"
    assert rw.extract_bullets(section) == ["Something big", "supporting detail"]


def test_extract_bullets_returns_empty_for_missing_section():
    assert rw.extract_bullets(None) == []


def test_dedupe_is_case_and_punctuation_insensitive():
    items = ["Temporal v1.32.1 correction", "temporal v1.32.1 CORRECTION!", "Other item"]
    assert rw.dedupe(items) == ["Temporal v1.32.1 correction", "Other item"]


def test_build_rollup_counts_dedupes_and_reports_gaps(tmp_path):
    make_daily(tmp_path / "2026-10-26.md", "Same headline", "DO NOW: pin Temporal")
    make_daily(tmp_path / "2026-10-27.md", "same HEADLINE", "DO NOW: pin Temporal")

    markdown, stats = rw.build_rollup(dt.date(2026, 10, 27), tmp_path)

    assert stats["briefings"] == 2
    assert stats["highlights"] == 1
    assert stats["actions"] == 1
    assert stats["missing"] == ["2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01"]
    assert "## Daily coverage" in markdown
    assert "../daily/2026-10-26.md" in markdown
    assert "**Briefings:** 2 of 7 days" in markdown
    assert markdown.count("Same headline") + markdown.count("same HEADLINE") == 1


def test_build_rollup_unions_sources_across_days(tmp_path):
    make_daily(tmp_path / "2026-10-26.md", "A", "DO NOW: a", urls=("https://example.com/a",))
    make_daily(
        tmp_path / "2026-10-27.md",
        "B",
        "DO NOW: b",
        urls=("https://example.com/a?utm_source=x", "https://other.example/b"),
    )
    _, stats = rw.build_rollup(dt.date(2026, 10, 27), tmp_path)
    assert stats["sources"] == 2


def test_main_stdout_does_not_write(tmp_path, capsys):
    make_daily(tmp_path / "2026-10-26.md", "Headline", "DO NOW: x")
    out_dir = tmp_path / "weekly"
    code = rw.main(
        ["--date", "2026-10-27", "--reports-dir", str(tmp_path), "--out-dir", str(out_dir), "--stdout"]
    )
    assert code == 0
    assert "## Highlights" in capsys.readouterr().out
    assert not out_dir.exists()


def test_main_writes_sheet_and_refuses_overwrite(tmp_path, capsys):
    make_daily(tmp_path / "2026-10-26.md", "Headline", "DO NOW: x")
    out_dir = tmp_path / "weekly"
    args = ["--date", "2026-10-27", "--reports-dir", str(tmp_path), "--out-dir", str(out_dir)]

    assert rw.main(args) == 0
    target = out_dir / "2026-W44.md"
    assert target.exists()
    assert "Headline" in target.read_text(encoding="utf-8")

    assert rw.main(args) == 1
    assert "already exists" in capsys.readouterr().out

    assert rw.main([*args, "--force"]) == 0


def test_main_returns_one_when_week_is_empty(tmp_path, capsys):
    code = rw.main(["--date", "2026-10-27", "--reports-dir", str(tmp_path), "--out-dir", str(tmp_path / "w")])
    assert code == 1
    assert "no briefings found" in capsys.readouterr().out


@pytest.mark.parametrize("day", ["2026-10-04", "2026-10-07", "2026-10-09", "2026-10-12"])
def test_real_briefings_roll_up(day):
    """Every published briefing belongs to a week that can be rendered."""
    markdown, stats = rw.build_rollup(dt.date.fromisoformat(day), rw.ROOT / "reports" / "daily")
    assert stats["briefings"] >= 1
    assert markdown.startswith("# CTO Intelligence - Week ")
