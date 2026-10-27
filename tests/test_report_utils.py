"""Tests for the shared briefing parser.

The regression these cover: the old regex stopped only at level-2 headings, so a
level-3 report leaked the whole document into the Telegram message.
"""
import report_utils as ru

REPORT = """### TOP 5 - MUST KNOW
- [P0] Temporal v1.32.1 ships
- [P1] Postgres 18 beta

### AI ENGINEERING
- coding agents, evals

### MY ACTION LIST
- DO NOW: upgrade Temporal
"""


def test_top5_stops_at_next_heading_of_any_level():
    section = ru.extract_top5(REPORT)
    assert "Temporal v1.32.1 ships" in section
    # The bug: level-3 sections used to be swallowed into the TOP 5 block.
    assert "AI ENGINEERING" not in section
    assert "DO NOW: upgrade Temporal" not in section


def test_top5_keeps_the_heading_line():
    assert ru.extract_top5(REPORT).startswith("### TOP 5 - MUST KNOW")


def test_top5_accepts_level_two_heading():
    md = "## TOP 5 - MUST KNOW\n- item\n## NEXT SECTION\n- other\n"
    section = ru.extract_top5(md)
    assert "- item" in section
    assert "- other" not in section


def test_top5_falls_back_to_document_head_when_section_missing():
    md = "no top five heading here\n" + ("filler " * 50)
    assert ru.extract_top5(md).startswith("no top five heading here")


def test_top5_respects_limit():
    md = "### TOP 5 - MUST KNOW\n" + ("x" * 5000)
    assert len(ru.extract_top5(md, limit=120)) == 120


def test_find_section_returns_none_when_absent():
    assert ru.find_section("### OTHER\nbody", "top 5") is None


def test_build_message_contains_date_briefing_and_path():
    msg = ru.build_message(REPORT, "2026-10-12", "reports/daily/2026-10-12.md")
    assert msg.startswith("CTO Intelligence - 2026-10-12")
    assert "Temporal v1.32.1 ships" in msg
    assert "reports/daily/2026-10-12.md" in msg
    assert "AI ENGINEERING" not in msg


def test_build_message_truncates_at_line_boundary():
    md = "### TOP 5 - MUST KNOW\n" + "\n".join(f"- line {i} " + "y" * 40 for i in range(200))
    msg = ru.build_message(md, "2026-10-12", "r.md", limit=600)
    assert len(msg) <= 600
    assert msg.endswith(ru.TRUNCATION_MARKER)


def test_build_message_clamps_oversized_limit():
    md = "### TOP 5 - MUST KNOW\n" + ("z" * 9000)
    msg = ru.build_message(md, "2026-10-12", "r.md", limit=99999)
    assert len(msg) <= ru.MESSAGE_LIMIT
