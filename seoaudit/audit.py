"""Run a full audit: crawl, check every page, check links and score."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .checks import Issue, broken_link_issues, page_issues, score, site_issues
from .crawler import Crawler
from .parser import PageData


@dataclass
class AuditResult:
    start_url: str
    created_at: str
    pages: list[PageData] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    score: int = 0

    def counts(self) -> dict[str, int]:
        c = {"error": 0, "warning": 0, "notice": 0}
        for i in self.issues:
            c[i.severity] += 1
        return c

    def issues_for(self, url: str) -> list[Issue]:
        return [i for i in self.issues if i.url == url]

    def to_dict(self) -> dict:
        return {
            "start_url": self.start_url,
            "created_at": self.created_at,
            "score": self.score,
            "pages_crawled": len(self.pages),
            "counts": self.counts(),
            "pages": [
                {"url": p.url, "status": p.status, "title": p.title, "meta_description": p.meta_description,
                 "h1": p.h1, "word_count": p.word_count, "load_ms": p.load_ms,
                 "score": score(self.issues_for(p.url), 1)}
                for p in self.pages
            ],
            "issues": [i.to_dict() for i in self.issues],
        }


def run_audit(start_url: str, max_pages: int = 50, check_external: bool = False, delay: float = 0.2,
              crawler: Crawler | None = None) -> AuditResult:
    crawler = crawler or Crawler(start_url, max_pages=max_pages, delay=delay)
    pages = crawler.crawl()
    links = {link for p in pages for link in p.internal_links}
    if check_external:
        links |= {link for p in pages for link in p.external_links}
    statuses = crawler.check_links(links)
    issues = [i for p in pages for i in page_issues(p)] + site_issues(pages) + broken_link_issues(pages, statuses)
    order = {"error": 0, "warning": 1, "notice": 2}
    issues.sort(key=lambda i: (order[i.severity], i.url))
    return AuditResult(
        start_url=crawler.start_url,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        pages=pages,
        issues=issues,
        score=score(issues, len(pages)),
    )
