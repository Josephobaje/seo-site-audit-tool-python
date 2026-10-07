"""Extract SEO-relevant data from an HTML page."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup


@dataclass
class PageData:
    url: str
    status: int = 0
    title: str = ""
    meta_description: str = ""
    canonical: str = ""
    lang: str = ""
    has_viewport: bool = False
    noindex: bool = False
    h1: list[str] = field(default_factory=list)
    headings: list[int] = field(default_factory=list)  # heading levels in document order
    images_missing_alt: list[str] = field(default_factory=list)
    image_count: int = 0
    internal_links: list[str] = field(default_factory=list)
    external_links: list[str] = field(default_factory=list)
    word_count: int = 0
    og_title: bool = False
    load_ms: int = 0
    error: str = ""


def normalize_url(url: str) -> str:
    url, _ = urldefrag(url)
    p = urlparse(url)
    path = p.path or "/"
    return p._replace(scheme=p.scheme.lower(), netloc=p.netloc.lower(), path=path).geturl()


def parse_page(html: str, url: str) -> PageData:
    soup = BeautifulSoup(html, "lxml")
    data = PageData(url=url)
    if soup.title and soup.title.string:
        data.title = " ".join(soup.title.string.split())
    desc = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    data.meta_description = " ".join((desc.get("content") or "").split()) if desc else ""
    canon = soup.find("link", rel=lambda v: v and "canonical" in (v if isinstance(v, list) else [v]))
    data.canonical = urljoin(url, canon["href"]) if canon and canon.get("href") else ""
    html_tag = soup.find("html")
    data.lang = (html_tag.get("lang") or "") if html_tag else ""
    data.has_viewport = soup.find("meta", attrs={"name": "viewport"}) is not None
    robots = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    data.noindex = bool(robots and "noindex" in (robots.get("content") or "").lower())
    data.og_title = soup.find("meta", attrs={"property": "og:title"}) is not None

    for tag in soup.find_all(re.compile(r"^h[1-6]$")):
        level = int(tag.name[1])
        data.headings.append(level)
        if level == 1:
            data.h1.append(tag.get_text(" ", strip=True))

    imgs = soup.find_all("img")
    data.image_count = len(imgs)
    data.images_missing_alt = [urljoin(url, i.get("src", "")) for i in imgs if not (i.get("alt") or "").strip()]

    host = urlparse(url).netloc.lower()
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")) or not href:
            continue
        absolute = normalize_url(urljoin(url, href))
        if absolute in seen or urlparse(absolute).scheme not in {"http", "https"}:
            continue
        seen.add(absolute)
        (data.internal_links if urlparse(absolute).netloc == host else data.external_links).append(absolute)

    for t in soup(["script", "style", "noscript", "template"]):
        t.decompose()
    body = soup.body or soup
    data.word_count = len(re.findall(r"\b\w+\b", body.get_text(" ")))
    return data
