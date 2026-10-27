"""Tests for the daily report contract validator."""
import json
from pathlib import Path

import pytest

import validate_report as vr

BODY = "Finding with evidence and a technical consequence.\n" + ("context detail " * 8)
REPO = Path(__file__).resolve().parents[1]


def default_sections():
    return [(name, BODY) for name in vr.REQUIRED_SECTIONS]


def render(sections, urls=3):
    parts = [""]
    for index, (name, body) in enumerate(sections):
        parts += [f"### {name}", body, ""]
        if index < urls:
            parts.append(f"Source: https://example{index}.com/item")
    return "\n".join(parts)


def write(tmp_path, name="2026-10-12.md", text=None, sections=None, urls=3):
    path = tmp_path / name
    path.write_text(
        text if text is not None else render(sections or default_sections(), urls),
        encoding="utf-8",
    )
    return path


def codes(result):
    return {finding.code for finding in result.errors}


def test_valid_report_passes(tmp_path):
    result = vr.validate(write(tmp_path))
    assert result.ok, [str(f) for f in result.errors]
    assert result.stats["sections_found"] == len(vr.REQUIRED_SECTIONS)
    assert result.stats["unique_sources"] == 3


def test_bad_filename_is_rejected(tmp_path):
    result = vr.validate(write(tmp_path, name="cto-report.md"))
    assert "E001" in codes(result)


def test_missing_section_is_rejected(tmp_path):
    sections = [s for s in default_sections() if s[0] != "MY ACTION LIST"]
    result = vr.validate(write(tmp_path, sections=sections))
    assert "E002" in codes(result)


def test_out_of_order_sections_are_rejected(tmp_path):
    sections = default_sections()
    sections[1], sections[2] = sections[2], sections[1]
    result = vr.validate(write(tmp_path, sections=sections))
    assert "E003" in codes(result)


def test_stub_section_is_rejected(tmp_path):
    sections = [(name, "stub") if name == "AI ENGINEERING" else (name, BODY) for name, _ in default_sections()]
    result = vr.validate(write(tmp_path, sections=sections))
    assert "E004" in codes(result)


def test_placeholder_is_rejected(tmp_path):
    sections = [(name, BODY + "\nTBD: fill this in") if name == "AI ENGINEERING" else (name, BODY) for name, _ in default_sections()]
    result = vr.validate(write(tmp_path, sections=sections))
    assert "E005" in codes(result)


def test_too_few_sources_is_rejected(tmp_path):
    result = vr.validate(write(tmp_path, urls=1))
    assert "E006" in codes(result)


def test_duplicate_urls_are_a_warning_by_default(tmp_path):
    prior = write(tmp_path, name="2026-10-01.md")
    assert prior.exists()
    current = write(tmp_path, name="2026-10-12.md")
    result = vr.validate(current, reports_dir=tmp_path, window=1)
    assert result.ok
    assert "W001" in {f.code for f in result.warnings}
    assert result.stats["url_overlap"] == 1.0


def test_duplicate_urls_can_be_an_error(tmp_path):
    write(tmp_path, name="2026-10-01.md")
    current = write(tmp_path, name="2026-10-12.md")
    result = vr.validate(current, reports_dir=tmp_path, window=1, fail_on_duplicates=True)
    assert "W001" in codes(result)


def test_no_prior_reports_means_no_overlap_warning(tmp_path):
    result = vr.validate(write(tmp_path), reports_dir=tmp_path, window=3)
    assert result.stats["compared_reports"] == 0
    assert result.stats["url_overlap"] == 0.0


def test_json_output_is_machine_readable(tmp_path, capsys):
    path = write(tmp_path)
    assert vr.main(["--json", str(path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["ok"] is True
    assert payload[0]["stats"]["unique_sources"] == 3


def test_main_returns_one_on_contract_violation(tmp_path, capsys):
    path = write(tmp_path, name="bad-name.md")
    assert vr.main([str(path)]) == 1
    assert "E001" in capsys.readouterr().out


def test_main_handles_multiple_reports(tmp_path, capsys):
    good = write(tmp_path, name="2026-10-12.md")
    bad = write(tmp_path, name="2026-10-13.md", urls=0)
    assert vr.main([str(good), str(bad)]) == 1
    out = capsys.readouterr().out
    assert "PASS" in out and "FAIL" in out


def test_main_returns_two_for_missing_file(tmp_path, capsys):
    assert vr.main([str(tmp_path / "2026-10-12.md")]) == 2


def test_main_expands_glob_patterns(tmp_path, capsys):
    """Windows shells do not expand `*.md` for native binaries; the CLI must."""
    write(tmp_path, name="2026-10-12.md")
    write(tmp_path, name="2026-10-13.md")
    assert vr.main([str(tmp_path / "*.md")]) == 0
    assert capsys.readouterr().out.count("PASS") == 2


@pytest.mark.parametrize("report", sorted((REPO / "reports" / "daily").glob("*.md")))
def test_committed_reports_satisfy_the_contract(report):
    """Guard against regressions in already-published briefings."""
    result = vr.validate(report)
    assert result.ok, [str(f) for f in result.errors]
