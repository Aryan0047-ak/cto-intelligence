"""Validate daily CTO briefings against the report contract.

The agent (``cto-research``) is asked to produce a fixed nine-section report
with primary sources and no repeats. Nothing enforced that until now: a bad
run could commit a truncated report, and the Telegram message would happily
send the fragment.

This validator is the contract gate. It runs in two places:

* ``.github/workflows/ci.yml`` - every committed report, so regressions are
  caught after the fact.
* ``.github/workflows/daily-research.yml`` - the report that is about to be
  committed, so it fails before it reaches ``main``.

Rules
-----
===== =========================================================================
E001  file name is not ``YYYY-MM-DD.md``
E002  a required section is missing
E003  required sections are out of order
E004  a section body is empty or stub-short (default: under 80 characters)
E005  an unresolved placeholder is present (``TBD``, ``TKTK``, ``{{...}}``,
      ``PLACEHOLDER``, ``Lorem ipsum``)
E006  fewer unique source URLs than ``--min-sources`` (default: 3)
W001  more than ``--max-overlap`` of this report's URLs also appear in the
      previous ``--window`` reports (dedup smell). A warning by default;
      ``--fail-on-duplicates`` turns it into an error.
===== =========================================================================

Exit codes: ``0`` pass (warnings allowed), ``1`` contract violation, ``2`` the
file could not be read.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

REQUIRED_SECTIONS: tuple[str, ...] = (
    "TOP 5 - MUST KNOW",
    "AI ENGINEERING",
    "SOFTWARE ENGINEERING & ARCHITECTURE",
    "DEVOPS / CLOUD / SECURITY",
    "REGULATED ENTERPRISE SOFTWARE",
    "OPEN SOURCE TO WATCH",
    "COMPETITOR / MARKET INTELLIGENCE",
    "WHAT I SHOULD LEARN",
    "MY ACTION LIST",
)

FILENAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
URL_RE = re.compile(r"https?://[^\s<>()\[\]\"']+", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(
    r"\b(?:TBD|TKTK|PLACEHOLDER)\b|lorem\s+ipsum|\{\{[^}]*\}\}", re.IGNORECASE
)
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.MULTILINE)

MIN_SECTION_CHARS = 80
_WORD_RE = re.compile(r"\b\w+\b")


@dataclass(frozen=True)
class Finding:
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return f"{self.code} {self.message}"


@dataclass
class Result:
    path: Path
    errors: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)
    stats: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "ok": self.ok,
            "errors": [f.as_dict() for f in self.errors],
            "warnings": [f.as_dict() for f in self.warnings],
            "stats": self.stats,
        }


def normalize_title(title: str) -> str:
    """Compare headings ignoring case, punctuation and dash style (em/en/ASCII)."""
    cleaned = re.sub(r"[^A-Z0-9 ]+", " ", title.upper())
    return re.sub(r"\s+", " ", cleaned).strip()


def split_sections(md: str) -> list[tuple[str, str]]:
    """Return ``(normalized_title, body)`` for every heading in the document."""
    headings = list(HEADING_RE.finditer(md))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(md)
        sections.append((normalize_title(match.group(2)), md[match.end():end].strip()))
    return sections


def extract_urls(text: str) -> set[str]:
    return {m.group(0).rstrip(".,);:!?*_`") for m in URL_RE.finditer(text)}


def normalize_url(url: str) -> str:
    """Drop scheme, ``www.``, query string, fragment and trailing slash."""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/")
    return f"{host}{path}".lower()


def _check_sections(sections: list[tuple[str, str]], min_chars: int) -> list[Finding]:
    findings: list[Finding] = []
    titles = [title for title, _ in sections]
    bodies = dict(sections)
    required = [normalize_title(name) for name in REQUIRED_SECTIONS]

    missing = [name for name in required if name not in bodies]
    for name in missing:
        findings.append(Finding("E002", f"missing required section: {name}"))

    found_order = [titles.index(name) for name in required if name in titles]
    if found_order != sorted(found_order):
        findings.append(
            Finding("E003", "required sections are out of order (expected the canonical sequence)")
        )

    for name in required:
        if name in missing:
            continue
        if len(bodies[name]) < min_chars:
            findings.append(
                Finding(
                    "E004",
                    f"section '{name}' is a stub ({len(bodies[name])} chars, need >= {min_chars})",
                )
            )
    return findings


def _prior_reports(reports_dir: Path, current: Path, window: int) -> list[Path]:
    if not reports_dir.is_dir() or window <= 0:
        return []
    candidates = sorted(
        p
        for p in reports_dir.glob("*.md")
        if FILENAME_RE.match(p.name) and p.name < current.name
    )
    return candidates[-window:]


def _overlap(current: set[str], previous: set[str]) -> float:
    if not current:
        return 0.0
    return len(current & previous) / len(current)


def validate(
    path: str | Path,
    *,
    reports_dir: str | Path | None = None,
    window: int = 3,
    max_overlap: float = 0.5,
    min_sources: int = 3,
    min_section_chars: int = MIN_SECTION_CHARS,
    fail_on_duplicates: bool = False,
) -> Result:
    path = Path(path)
    result = Result(path=path)

    try:
        md = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        result.errors.append(Finding("E000", f"cannot read file: {exc}"))
        return result

    if not FILENAME_RE.match(path.name):
        result.errors.append(
            Finding("E001", f"file name '{path.name}' is not YYYY-MM-DD.md")
        )

    sections = split_sections(md)
    result.errors.extend(_check_sections(sections, min_section_chars))

    placeholders = sorted({m.group(0) for m in PLACEHOLDER_RE.finditer(md)})
    if placeholders:
        result.errors.append(
            Finding("E005", "unresolved placeholder(s): " + ", ".join(placeholders))
        )

    urls = extract_urls(md)

    prior_paths = _prior_reports(
        Path(reports_dir) if reports_dir else path.parent, path, window
    )
    prior_urls: set[str] = set()
    for prior in prior_paths:
        try:
            prior_urls |= {normalize_url(u) for u in extract_urls(prior.read_text(encoding="utf-8", errors="replace"))}
        except OSError:
            continue

    overlap = _overlap({normalize_url(u) for u in urls}, prior_urls)
    if prior_paths and overlap > max_overlap:
        finding = Finding(
            "W001",
            f"{overlap:.0%} of source URLs already appeared in the previous "
            f"{len(prior_paths)} report(s); limit is {max_overlap:.0%}",
        )
        (result.errors if fail_on_duplicates else result.warnings).append(finding)

    result.stats = {
        "sections_found": len(sections),
        "sections_required": len(REQUIRED_SECTIONS),
        "unique_sources": len(urls),
        "words": len(_WORD_RE.findall(md)),
        "url_overlap": round(overlap, 3),
        "compared_reports": len(prior_paths),
    }

    if len(urls) < min_sources:
        result.errors.append(
            Finding("E006", f"only {len(urls)} unique source URL(s); need >= {min_sources}")
        )
    return result


def format_result(result: Result) -> str:
    status = "PASS" if result.ok else "FAIL"
    stats = result.stats
    line = (
        f"{status} {result.path}  "
        f"[{stats.get('sections_found', 0)}/{stats.get('sections_required', 0)} sections, "
        f"{stats.get('unique_sources', 0)} sources, "
        f"overlap {float(stats.get('url_overlap', 0.0)):.0%}]"
    )
    details = [f"  {finding}" for finding in (*result.errors, *result.warnings)]
    return "\n".join([line, *details])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate daily CTO briefings.")
    parser.add_argument("paths", nargs="+", help="report file(s) to validate")
    parser.add_argument("--reports-dir", help="folder used for the dedup comparison")
    parser.add_argument("--window", type=int, default=3, help="prior reports to compare (default 3)")
    parser.add_argument("--max-overlap", type=float, default=0.5, help="allowed URL overlap (default 0.5)")
    parser.add_argument("--min-sources", type=int, default=3, help="minimum unique URLs (default 3)")
    parser.add_argument(
        "--min-section-chars", type=int, default=MIN_SECTION_CHARS,
        help=f"minimum section body length (default {MIN_SECTION_CHARS})",
    )
    parser.add_argument("--fail-on-duplicates", action="store_true", help="treat W001 as an error")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--quiet", action="store_true", help="only print failures")
    args = parser.parse_args(argv)

    results: list[Result] = []
    # Expand globs ourselves: PowerShell/cmd do not expand wildcards for native
    # binaries, so the documented `reports/daily/*.md` form must work on Windows.
    targets: list[str] = []
    for raw in args.paths:
        targets.extend(sorted(glob.glob(raw)) or [raw])

    for raw in targets:
        try:
            results.append(
                validate(
                    raw,
                    reports_dir=args.reports_dir,
                    window=args.window,
                    max_overlap=args.max_overlap,
                    min_sources=args.min_sources,
                    min_section_chars=args.min_section_chars,
                    fail_on_duplicates=args.fail_on_duplicates,
                )
            )
        except OSError as exc:  # pragma: no cover - defensive
            print(f"FAIL {raw}: {exc}", file=sys.stderr)
            return 2

    if args.json:
        print(json.dumps([r.as_dict() for r in results], indent=2))
    else:
        for result in results:
            if args.quiet and result.ok:
                continue
            print(format_result(result))

    unreadable = any(any(f.code == "E000" for f in r.errors) for r in results)
    if unreadable:
        return 2
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
