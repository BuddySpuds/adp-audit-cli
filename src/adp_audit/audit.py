"""Audit a site against the AI Discovery Protocol registry.

Level 1 (required) is checked page by page: a sample of pages from the
sitemap, each tested for a markdown copy that is linked from the page body
and open to AI crawlers. Whether the copy is listed in a sitemap is reported
as a recommendation. Levels 2 to 4 are optional
endpoints; the audit reports which are served and gives them no score.
"""

import asyncio
import re
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

import httpx

from adp_audit import registry

USER_AGENT = "adp-audit-cli/0.2.0 (+https://github.com/BuddySpuds/adp-audit-cli)"
AI_CRAWLERS = ("GPTBot", "OAI-SearchBot", "ClaudeBot", "PerplexityBot")
MARKDOWN_SUFFIXES = (".md", ".markdown")
MARKDOWN_TYPES = ("text/markdown", "text/plain", "text/x-markdown")
MAX_SITEMAPS = 8
TIMEOUT = 15.0


@dataclass
class PageResult:
    """Level 1 checks for one page."""

    url: str
    copy_url: Optional[str] = None
    markdown_copy: bool = False
    body_link: bool = False
    sitemap_listing: bool = False
    crawl_allowed: bool = False
    alternate_link: bool = False
    note: Optional[str] = None

    @property
    def conforms(self) -> bool:
        """Every required Level 1 row holds. Sitemap listing is recommended."""
        return self.markdown_copy and self.body_link and self.crawl_allowed


@dataclass
class EndpointResult:
    """Whether one registry endpoint is served."""

    id: str
    path: str
    level: int
    category: str
    status: str
    found: bool
    status_code: Optional[int] = None
    served_from: Optional[str] = None
    error: Optional[str] = None


@dataclass
class AuditResult:
    domain: str
    registry_version: str
    robots_found: bool = False
    sitemap_found: bool = False
    sitemap_urls: int = 0
    markdown_urls_in_sitemap: int = 0
    pages: list[PageResult] = field(default_factory=list)
    endpoints: list[EndpointResult] = field(default_factory=list)

    @property
    def pages_conforming(self) -> int:
        return sum(1 for page in self.pages if page.conforms)

    @property
    def level_1(self) -> str:
        """"met", "partial" or "not met" for the pages sampled."""
        if not (self.robots_found and self.sitemap_found and self.pages):
            return "not met"
        if self.pages_conforming == len(self.pages):
            return "met"
        return "partial" if self.pages_conforming else "not met"

    def optional_levels(self) -> dict[int, dict]:
        summary: dict[int, dict] = {}
        for result in self.endpoints:
            if result.level == 1:
                continue
            row = summary.setdefault(result.level, {"served": 0, "total": 0})
            row["total"] += 1
            row["served"] += int(result.found)
        return summary

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "registry_version": self.registry_version,
            "level_1": self.level_1,
            "robots_found": self.robots_found,
            "sitemap_found": self.sitemap_found,
            "sitemap_urls": self.sitemap_urls,
            "markdown_urls_in_sitemap": self.markdown_urls_in_sitemap,
            "pages_sampled": len(self.pages),
            "pages_conforming": self.pages_conforming,
            "pages": [dict(asdict(p), conforms=p.conforms) for p in self.pages],
            "optional_levels": self.optional_levels(),
            "endpoints": [asdict(e) for e in self.endpoints],
        }


class _LinkParser(HTMLParser):
    """Collect markdown links from the head and from the body of a page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_body = False
        self.head_alternates: list[str] = []
        self.body_links: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = {name: (value or "") for name, value in attrs}
        if tag == "body":
            self.in_body = True
        elif tag == "link" and not self.in_body:
            rel = attributes.get("rel", "").lower().split()
            kind = attributes.get("type", "").lower()
            if "alternate" in rel and kind.startswith("text/markdown"):
                if attributes.get("href"):
                    self.head_alternates.append(attributes["href"])
        elif tag == "a" and self.in_body and attributes.get("href"):
            self.body_links.append(attributes["href"])


def _is_markdown_url(url: str) -> bool:
    return urlsplit(url).path.lower().endswith(MARKDOWN_SUFFIXES)


def _normalise(url: str) -> str:
    parts = urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.")
    return f"{host}{parts.path}"


def find_copy(page_url: str, html: str) -> tuple[Optional[str], bool, bool]:
    """Return (copy URL, linked from body, announced in head) for a page."""
    parser = _LinkParser()
    try:
        parser.feed(html)
    except Exception:
        pass
    host = _normalise(page_url).split("/")[0]

    def same_site(url: str) -> bool:
        return _normalise(url).split("/")[0] == host

    head = [urljoin(page_url, href) for href in parser.head_alternates]
    head = [url for url in head if same_site(url)]
    head_keys = {_normalise(url) for url in head}
    body = [urljoin(page_url, href).split("#")[0] for href in parser.body_links]
    body = [
        url
        for url in body
        if same_site(url) and (_is_markdown_url(url) or _normalise(url) in head_keys)
    ]

    slug = urlsplit(page_url).path.rstrip("/").rsplit("/", 1)[-1].lower()

    def best(candidates: list[str]) -> Optional[str]:
        if not candidates:
            return None
        if slug:
            for url in candidates:
                if slug in urlsplit(url).path.lower():
                    return url
        return candidates[0]

    copy = best(body)
    if copy:
        return copy, True, _normalise(copy) in head_keys
    copy = best(head)
    return copy, False, bool(copy)


def parse_sitemap(xml_text: str) -> tuple[list[str], list[str]]:
    """Return (page URLs, child sitemap URLs) from a sitemap document."""
    try:
        root = ElementTree.fromstring(xml_text.encode("utf-8"))
    except ElementTree.ParseError:
        return [], []
    locations = [
        (element.text or "").strip()
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1] == "loc"
    ]
    locations = [loc for loc in locations if loc]
    if root.tag.rsplit("}", 1)[-1] == "sitemapindex":
        return [], locations
    return locations, []


def choose_pages(urls: list[str], sample: int) -> list[str]:
    """Pick pages to audit: deep pages first, spread across site sections."""
    pages = sorted({url for url in urls if not _is_markdown_url(url)})
    by_section: dict[str, list[str]] = {}
    for url in pages:
        segments = [s for s in urlsplit(url).path.split("/") if s]
        if len(segments) >= 2:
            by_section.setdefault(segments[0], []).append(url)
    # Largest sections first: they are the most likely to be content.
    sections = sorted(by_section, key=lambda name: (-len(by_section[name]), name))
    chosen: list[str] = []
    index = 0
    while len(chosen) < sample and any(by_section[s][index:] for s in sections):
        for section in sections:
            if index < len(by_section[section]) and len(chosen) < sample:
                chosen.append(by_section[section][index])
        index += 1
    if not chosen:
        chosen = pages[:sample]
    return chosen


async def _get(client: httpx.AsyncClient, url: str) -> Optional[httpx.Response]:
    try:
        return await client.get(url, follow_redirects=True, timeout=TIMEOUT)
    except Exception:
        return None


def _looks_like_html(text: str) -> bool:
    return bool(re.match(r"\s*(<!doctype html|<html)", text[:500], re.IGNORECASE))


async def _check_page(
    client: httpx.AsyncClient,
    page_url: str,
    listed: set[str],
    robots: Optional[RobotFileParser],
) -> PageResult:
    result = PageResult(url=page_url)
    response = await _get(client, page_url)
    if response is None or response.status_code != 200:
        result.note = "page did not load"
        return result

    copy_url, in_body, in_head = find_copy(str(response.url), response.text)
    result.copy_url = copy_url
    result.body_link = in_body
    result.alternate_link = in_head
    if not copy_url:
        result.note = "no link to a markdown copy"
        return result

    copy = await _get(client, copy_url)
    if copy is None or copy.status_code != 200:
        result.note = "markdown copy did not load"
    else:
        kind = copy.headers.get("content-type", "").lower()
        if not kind.startswith(MARKDOWN_TYPES):
            result.note = f"copy is served as {kind or 'an unknown type'}"
        elif _looks_like_html(copy.text):
            result.note = "copy is HTML, not markdown"
        else:
            result.markdown_copy = True

    result.sitemap_listing = _normalise(copy_url) in listed
    if robots is None:
        result.crawl_allowed = True
    else:
        result.crawl_allowed = all(
            robots.can_fetch(agent, page_url) and robots.can_fetch(agent, copy_url)
            for agent in AI_CRAWLERS
        )
    if result.markdown_copy and not result.note:
        if not result.body_link:
            result.note = "copy is announced in the head only"
        elif not result.crawl_allowed:
            result.note = "robots.txt blocks an AI crawler"
        elif not result.sitemap_listing:
            result.note = "recommended: list the copy in a sitemap"
    return result


async def _check_endpoint(
    client: httpx.AsyncClient, base_url: str, endpoint: dict
) -> EndpointResult:
    result = EndpointResult(
        id=endpoint["id"],
        path=endpoint["path"],
        level=endpoint["level"],
        category=endpoint["category"],
        status=endpoint["status"],
        found=False,
    )
    for path in [endpoint["path"], *endpoint.get("aliases", [])]:
        response = await _get(client, f"{base_url}{path}")
        if response is None:
            result.error = "request failed"
            continue
        result.status_code = response.status_code
        kind = response.headers.get("content-type", "").lower()
        if response.status_code == 200 and kind.startswith("text/html"):
            # No registry endpoint is an HTML page: this is a catch-all route.
            result.error = "answered with an HTML page"
            continue
        if response.status_code == 200:
            result.found = True
            result.error = None
            final = urlsplit(str(response.url)).path
            if final != path or path != endpoint["path"]:
                result.served_from = final
            break
    return result


async def audit_domain(
    domain: str,
    sample: int = 5,
    pages: Optional[list[str]] = None,
    sitemaps: Optional[list[str]] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> AuditResult:
    """Audit a domain against the ADP registry.

    Args:
        domain: Domain name ("example.com") or full URL.
        sample: How many pages to take from the sitemap for the Level 1 check.
        pages: Audit these page URLs instead of sampling.
        sitemaps: Extra sitemaps to read, for example a dedicated sitemap of
            markdown copies that robots.txt does not name.
        transport: Optional httpx transport (used by the tests).
    """
    if not domain.startswith("http"):
        domain = f"https://{domain}"
    base_url = domain.rstrip("/")
    result = AuditResult(
        domain=urlsplit(base_url).netloc, registry_version=registry.version()
    )

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, transport=transport
    ) as client:
        # robots.txt: the rules, and where the sitemaps are.
        robots: Optional[RobotFileParser] = None
        sitemap_queue: list[str] = []
        response = await _get(client, f"{base_url}/robots.txt")
        if response is not None and response.status_code == 200:
            result.robots_found = True
            robots = RobotFileParser()
            robots.parse(response.text.splitlines())
            sitemap_queue = list(robots.site_maps() or [])
        if not sitemap_queue:
            sitemap_queue = [f"{base_url}/sitemap.xml"]
        sitemap_queue += [urljoin(base_url + "/", extra) for extra in sitemaps or []]

        # Sitemaps, following one sitemap index.
        listed_urls: list[str] = []
        fetched = 0
        while sitemap_queue and fetched < MAX_SITEMAPS:
            sitemap_url = sitemap_queue.pop(0)
            fetched += 1
            response = await _get(client, sitemap_url)
            if response is None or response.status_code != 200:
                continue
            urls, children = parse_sitemap(response.text)
            if urls or children:
                result.sitemap_found = True
            listed_urls.extend(urls)
            sitemap_queue.extend(children)
        listed = {_normalise(url) for url in listed_urls}
        result.sitemap_urls = len(listed)
        result.markdown_urls_in_sitemap = sum(
            1 for url in set(listed_urls) if _is_markdown_url(url)
        )

        # Level 1, page by page.
        targets = (
            [urljoin(base_url + "/", page) for page in pages]
            if pages
            else choose_pages(listed_urls, sample)
        )
        result.pages = list(
            await asyncio.gather(
                *(_check_page(client, url, listed, robots) for url in targets)
            )
        )

        # Every registry endpoint.
        result.endpoints = list(
            await asyncio.gather(
                *(
                    _check_endpoint(client, base_url, endpoint)
                    for endpoint in registry.endpoints()
                )
            )
        )
        # A sitemap named in robots.txt satisfies the sitemap requirement.
        for endpoint in result.endpoints:
            if endpoint.id == "sitemap" and result.sitemap_found:
                endpoint.found = True
    return result
