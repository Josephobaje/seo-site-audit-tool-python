"""Breadth-first, same-domain crawler with link checking."""

from __future__ import annotations

import time
import urllib.robotparser
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import requests

from .parser import PageData, normalize_url, parse_page

USER_AGENT = "SEO-Audit-Bot/1.0 (+https://github.com/Josephobaje/seo-site-audit-tool-python)"
SKIP_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".zip", ".mp4", ".mp3", ".css", ".js")


class Crawler:
    def __init__(self, start_url: str, max_pages: int = 50, delay: float = 0.2, timeout: float = 15.0,
                 respect_robots: bool = True, session: requests.Session | None = None) -> None:
        self.start_url = normalize_url(start_url)
        self.host = urlparse(self.start_url).netloc
        self.max_pages = max_pages
        self.delay = delay
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.robots = urllib.robotparser.RobotFileParser()
        if respect_robots:
            try:
                r = self.session.get(urljoin(self.start_url, "/robots.txt"), timeout=timeout)
                self.robots.parse(r.text.splitlines() if r.status_code == 200 else [])
            except requests.RequestException:
                self.robots.parse([])
        else:
            self.robots.parse([])
        self.link_status: dict[str, int] = {}

    def fetch(self, url: str) -> PageData:
        start = time.perf_counter()
        try:
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
        except requests.RequestException as exc:
            return PageData(url=url, error=str(exc))
        elapsed = int((time.perf_counter() - start) * 1000)
        self.link_status[url] = resp.status_code
        ctype = resp.headers.get("Content-Type", "")
        if resp.status_code >= 400 or "html" not in ctype:
            return PageData(url=url, status=resp.status_code, load_ms=elapsed)
        if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding or "utf-8"
        page = parse_page(resp.text, url)
        page.status, page.load_ms = resp.status_code, elapsed
        return page

    def crawl(self) -> list[PageData]:
        queue: deque[str] = deque([self.start_url])
        queued = {self.start_url}
        pages: list[PageData] = []
        while queue and len(pages) < self.max_pages:
            url = queue.popleft()
            if not self.robots.can_fetch(USER_AGENT, url):
                continue
            page = self.fetch(url)
            pages.append(page)
            for link in page.internal_links:
                if link not in queued and not urlparse(link).path.lower().endswith(SKIP_EXTENSIONS):
                    queued.add(link)
                    queue.append(link)
            if self.delay:
                time.sleep(self.delay)
        return pages

    def check_links(self, urls: set[str], workers: int = 8) -> dict[str, int]:
        """Return HTTP status for each URL (0 = connection error). Uses HEAD, falling back to GET."""
        todo = [u for u in urls if u not in self.link_status]

        def status(u: str) -> tuple[str, int]:
            try:
                r = self.session.head(u, timeout=self.timeout, allow_redirects=True)
                if r.status_code in (405, 501) or r.status_code == 403:
                    r = self.session.get(u, timeout=self.timeout, allow_redirects=True, stream=True)
                    r.close()
                return u, r.status_code
            except requests.RequestException:
                return u, 0

        with ThreadPoolExecutor(max_workers=workers) as pool:
            for u, code in pool.map(status, todo):
                self.link_status[u] = code
        return {u: self.link_status[u] for u in urls}
