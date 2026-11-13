"""Tests for adp-audit. No network: every site is a mock transport."""

import json
from pathlib import Path

import httpx
import pytest

from adp_audit import audit_domain, choose_pages, find_copy, parse_sitemap, registry

ROBOTS = "User-agent: *\nDisallow: /admin/\nAllow: /\n\nSitemap: https://example.com/sitemap.xml\n"
PAGE = """<!doctype html><html><head>
<link rel="alternate" type="text/markdown" href="/news/launch.md">
</head><body><h1>Launch</h1>
<p><a href="/news/launch.md">this page as markdown</a></p></body></html>"""
COPY = "---\ntitle: Launch\n---\n\n# Launch\n"
SITEMAP = """<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://example.com/news/launch</loc></url>
<url><loc>https://example.com/news/launch.md</loc></url>
</urlset>"""


def site(overrides=None):
    routes = {
        "/robots.txt": (200, "text/plain", ROBOTS),
        "/sitemap.xml": (200, "application/xml", SITEMAP),
        "/news/launch": (200, "text/html", PAGE),
        "/news/launch.md": (200, "text/markdown; charset=utf-8", COPY),
        "/llms.txt": (200, "text/plain", "# Example"),
        "/.well-known/mcp.json": (200, "application/json", "{}"),
    }
    routes.update(overrides or {})

    def handler(request: httpx.Request) -> httpx.Response:
        route = routes.get(request.url.path)
        if route is None:
            return httpx.Response(404)
        status, kind, body = route
        return httpx.Response(status, headers={"content-type": kind}, text=body)

    return httpx.MockTransport(handler)


async def run(overrides=None, **kwargs):
    return await audit_domain("example.com", transport=site(overrides), **kwargs)


def test_registry_is_well_formed():
    data = registry.load()
    ids = [e["id"] for e in data["endpoints"]]
    paths = [p for e in data["endpoints"] for p in [e["path"], *e.get("aliases", [])]]
    assert len(ids) == len(set(ids))
    assert len(paths) == len(set(paths))
    assert {e["level"] for e in data["endpoints"]} <= {lv["level"] for lv in data["levels"]}
    assert [lv["status"] for lv in data["levels"]] == ["required", "optional", "optional", "optional"]
    assert {r["id"] for r in registry.page_requirements(required_only=True)} == {
        "markdown_copy",
        "body_link",
        "crawl_allowed",
    }


def test_bundled_registry_matches_the_specification_repo():
    """Runs when the specification repo is checked out next to this one."""
    canonical = (
        Path(__file__).resolve().parents[2]
        / "AI-Discovery-Protocol"
        / "registry"
        / "adp-registry.json"
    )
    if not canonical.exists():
        pytest.skip("AI-Discovery-Protocol is not checked out alongside")
    assert json.loads(canonical.read_text()) == registry.load()


async def test_conforming_site_meets_level_1():
    result = await run()
    assert result.level_1 == "met"
    page = result.pages[0]
    assert page.url == "https://example.com/news/launch"
    assert page.copy_url == "https://example.com/news/launch.md"
    assert page.conforms and page.alternate_link
    assert result.markdown_urls_in_sitemap == 1


async def test_head_link_alone_is_not_enough():
    page = PAGE.replace('<p><a href="/news/launch.md">this page as markdown</a></p>', "")
    result = await run({"/news/launch": (200, "text/html", page)})
    assert result.pages[0].markdown_copy is True
    assert result.pages[0].body_link is False
    assert result.level_1 == "not met"
    assert "head only" in result.pages[0].note


COPY_ENTRY = "<url><loc>https://example.com/news/launch.md</loc></url>"


async def test_sitemap_listing_is_recommended_not_required():
    sitemap = SITEMAP.replace(COPY_ENTRY, "")
    result = await run({"/sitemap.xml": (200, "application/xml", sitemap)})
    assert result.pages[0].sitemap_listing is False
    assert result.pages[0].conforms is True
    assert result.level_1 == "met"
    assert "recommended" in result.pages[0].note


async def test_dedicated_copies_sitemap_can_be_supplied():
    main = SITEMAP.replace(COPY_ENTRY, "")
    copies = SITEMAP.replace("<url><loc>https://example.com/news/launch</loc></url>", "")
    result = await run(
        {
            "/sitemap.xml": (200, "application/xml", main),
            "/sitemap-md.xml": (200, "application/xml", copies),
        },
        sitemaps=["/sitemap-md.xml"],
    )
    assert result.pages[0].sitemap_listing is True
    assert result.pages[0].note is None
    assert [p.url for p in result.pages] == ["https://example.com/news/launch"]


async def test_html_served_at_the_copy_url_fails():
    result = await run({"/news/launch.md": (200, "text/html", PAGE)})
    assert result.pages[0].markdown_copy is False
    result = await run({"/news/launch.md": (200, "text/plain", PAGE)})
    assert result.pages[0].markdown_copy is False


async def test_robots_blocking_an_ai_crawler_fails():
    robots = "User-agent: GPTBot\nDisallow: /\n\n" + ROBOTS
    result = await run({"/robots.txt": (200, "text/plain", robots)})
    assert result.pages[0].crawl_allowed is False
    assert result.level_1 == "not met"


async def test_page_without_any_copy():
    result = await run({"/news/launch": (200, "text/html", "<html><body>Hi</body></html>")})
    assert result.pages[0].copy_url is None
    assert result.level_1 == "not met"


async def test_partial_when_only_some_pages_conform():
    sitemap = SITEMAP.replace(
        "</urlset>", "<url><loc>https://example.com/news/other</loc></url></urlset>"
    )
    result = await run(
        {
            "/sitemap.xml": (200, "application/xml", sitemap),
            "/news/other": (200, "text/html", "<html><body>Hi</body></html>"),
        }
    )
    assert len(result.pages) == 2
    assert result.level_1 == "partial"


async def test_explicit_pages_override_sampling():
    result = await run(pages=["/news/launch"])
    assert [p.url for p in result.pages] == ["https://example.com/news/launch"]


async def test_optional_endpoints_are_reported_not_scored():
    result = await run()
    found = {e.id: e for e in result.endpoints}
    assert found["llms_txt"].found is True
    assert found["knowledge_graph"].found is False
    # served from an alias
    assert found["mcp_manifest"].found is True
    assert found["mcp_manifest"].served_from == "/.well-known/mcp.json"
    assert result.optional_levels()[2]["served"] == 1
    assert not hasattr(result, "score")
    assert result.to_dict()["level_1"] == "met"


async def test_missing_robots_and_sitemap():
    result = await run({"/robots.txt": (404, "text/plain", ""), "/sitemap.xml": (404, "text/plain", "")})
    assert result.robots_found is False and result.sitemap_found is False
    assert result.level_1 == "not met"


def test_sitemap_index_is_followed():
    index = """<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap><loc>https://example.com/a.xml</loc></sitemap></sitemapindex>"""
    assert parse_sitemap(index) == ([], ["https://example.com/a.xml"])
    assert parse_sitemap("not xml") == ([], [])


def test_find_copy_prefers_the_link_for_this_page():
    html = """<html><head></head><body>
    <a href="/md/index.md">all copies</a><a href="/md/blog/my-post.md">this page</a>
    <a href="https://other.example/x.md">elsewhere</a></body></html>"""
    copy, in_body, in_head = find_copy("https://example.com/blog/my-post", html)
    assert copy == "https://example.com/md/blog/my-post.md"
    assert in_body is True and in_head is False


def test_choose_pages_spreads_across_sections():
    urls = [f"https://example.com/blog/p{i}" for i in range(5)]
    urls += [f"https://example.com/news/n{i}" for i in range(3)]
    urls += ["https://example.com/", "https://example.com/pricing", "https://example.com/blog/p0.md"]
    chosen = choose_pages(urls, 4)
    assert len(chosen) == 4
    assert sum("/blog/" in u for u in chosen) == 2 and sum("/news/" in u for u in chosen) == 2
    assert not any(u.endswith(".md") for u in chosen)


async def test_html_catch_all_does_not_count_as_an_endpoint():
    result = await run({"/knowledge-graph.json": (200, "text/html; charset=utf-8", PAGE)})
    found = {e.id: e for e in result.endpoints}
    assert found["knowledge_graph"].found is False
    assert found["knowledge_graph"].error == "answered with an HTML page"
