"""Command-line interface: ``python -m seoaudit https://example.com -o report.html``."""

from __future__ import annotations

import argparse
import sys

from .audit import run_audit
from .report import save


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="seoaudit", description="Crawl a website and audit its on-page SEO.")
    ap.add_argument("url", help="Start URL, e.g. https://example.com")
    ap.add_argument("--max-pages", type=int, default=50)
    ap.add_argument("--delay", type=float, default=0.2, help="Seconds between page requests")
    ap.add_argument("--check-external", action="store_true", help="Also check outbound links for 4xx/5xx")
    ap.add_argument("-o", "--output", action="append", default=[], help="Report file (.html, .json, .csv); repeatable")
    ap.add_argument("--min-score", type=int, help="Exit 1 if the site score is below this (for CI)")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.url.startswith(("http://", "https://")):
        print("error: URL must start with http:// or https://", file=sys.stderr)
        return 2
    result = run_audit(args.url, args.max_pages, args.check_external, args.delay)
    c = result.counts()
    print(f"Crawled {len(result.pages)} pages. Score: {result.score}/100")
    print(f"{c['error']} errors, {c['warning']} warnings, {c['notice']} notices")
    for issue in result.issues[:15]:
        print(f"  [{issue.severity:7}] {issue.url}  {issue.message}")
    if len(result.issues) > 15:
        print(f"  ... and {len(result.issues) - 15} more (see the report)")
    for out in args.output:
        print(f"Report saved to {save(result, out)}")
    if args.min_score is not None and result.score < args.min_score:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
