"""On-page SEO rules. Each issue has a severity and a fix."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass

from .parser import PageData

PENALTY = {"error": 15, "warning": 6, "notice": 2}

TITLE_MIN, TITLE_MAX = 30, 60
DESC_MIN, DESC_MAX = 70, 160
THIN_CONTENT_WORDS = 250


@dataclass
class Issue:
    url: str
    severity: str  # error | warning | notice
    code: str
    message: str
    fix: str

    def to_dict(self) -> dict:
        return asdict(self)


def page_issues(p: PageData) -> list[Issue]:
    out: list[Issue] = []

    def add(sev, code, msg, fix):
        out.append(Issue(p.url, sev, code, msg, fix))

    if p.error:
        add("error", "unreachable", f"Page could not be loaded: {p.error}", "Check the server and URL.")
        return out
    if p.status >= 400:
        add("error", "http-error", f"Page returns HTTP {p.status}", "Fix or redirect the page, and update links to it.")
        return out
    if not p.title and p.word_count == 0 and not p.h1:
        return out  # non-HTML resource

    if not p.title:
        add("error", "title-missing", "Missing <title>", "Add a unique, descriptive title (30-60 characters).")
    elif len(p.title) > TITLE_MAX:
        add("warning", "title-long", f"Title is {len(p.title)} characters (over {TITLE_MAX})", "Shorten it so Google doesn't truncate it.")
    elif len(p.title) < TITLE_MIN:
        add("notice", "title-short", f"Title is only {len(p.title)} characters", "Add your main keyword and brand.")

    if not p.meta_description:
        add("warning", "description-missing", "Missing meta description", "Write a 70-160 character summary that invites clicks.")
    elif len(p.meta_description) > DESC_MAX:
        add("notice", "description-long", f"Meta description is {len(p.meta_description)} characters", f"Keep it under {DESC_MAX}.")
    elif len(p.meta_description) < DESC_MIN:
        add("notice", "description-short", f"Meta description is only {len(p.meta_description)} characters", f"Aim for {DESC_MIN}-{DESC_MAX}.")

    if not p.h1:
        add("error", "h1-missing", "No <h1> heading", "Add one H1 that states the page topic.")
    elif len(p.h1) > 1:
        add("warning", "h1-multiple", f"{len(p.h1)} <h1> headings", "Use a single H1 and H2-H6 for sections.")

    prev = 0
    for level in p.headings:
        if prev and level > prev + 1:
            add("notice", "heading-skip", f"Heading level skips from H{prev} to H{level}", "Keep heading levels sequential for accessibility.")
            break
        prev = level

    if p.images_missing_alt:
        add("warning", "img-alt-missing", f"{len(p.images_missing_alt)} of {p.image_count} images have no alt text",
            "Describe each meaningful image in its alt attribute.")
    if not p.canonical:
        add("notice", "canonical-missing", "No canonical URL", "Add <link rel=\"canonical\"> to avoid duplicate content.")
    if not p.has_viewport:
        add("error", "viewport-missing", "No mobile viewport meta tag", "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">.")
    if not p.lang:
        add("notice", "lang-missing", "<html> has no lang attribute", "Add lang=\"en\" (or your language).")
    if p.noindex:
        add("warning", "noindex", "Page is set to noindex", "Remove noindex if this page should appear in Google.")
    if p.word_count < THIN_CONTENT_WORDS:
        add("notice", "thin-content", f"Only {p.word_count} words of content", f"Pages with under {THIN_CONTENT_WORDS} words rarely rank. Expand it.")
    if not p.og_title:
        add("notice", "og-missing", "No Open Graph tags", "Add og:title, og:description and og:image for better social sharing.")
    if p.load_ms > 2500:
        add("warning", "slow", f"Server responded in {p.load_ms} ms", "Enable caching, compression and a CDN.")
    return out


def site_issues(pages: list[PageData]) -> list[Issue]:
    """Issues that only show up across pages: duplicate titles and descriptions."""
    out: list[Issue] = []
    for attr, code, label in (("title", "title-duplicate", "title"), ("meta_description", "description-duplicate", "meta description")):
        groups: dict[str, list[str]] = defaultdict(list)
        for p in pages:
            value = getattr(p, attr)
            if value and not p.error and p.status < 400:
                groups[value.lower()].append(p.url)
        for urls in groups.values():
            if len(urls) > 1:
                for u in urls:
                    out.append(Issue(u, "warning", code, f"Duplicate {label} shared with {len(urls) - 1} other page(s)",
                                     f"Write a unique {label} for each page."))
    return out


def broken_link_issues(pages: list[PageData], statuses: dict[str, int]) -> list[Issue]:
    out: list[Issue] = []
    for p in pages:
        for link in p.internal_links + p.external_links:
            code = statuses.get(link)
            if code is not None and (code == 0 or code >= 400):
                label = "unreachable" if code == 0 else f"HTTP {code}"
                out.append(Issue(p.url, "error", "broken-link", f"Broken link ({label}): {link}", "Fix the URL or remove the link."))
    return out


def score(issues: list[Issue], pages: int) -> int:
    if not pages:
        return 0
    penalty = sum(PENALTY[i.severity] for i in issues) / pages
    return max(0, round(100 - penalty))
