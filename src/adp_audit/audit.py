"""ADP endpoint audit logic.

Checks the 20 endpoints defined by the AI Discovery Protocol (ADP v2.1).
Endpoint list mirrors the public Citability scanner specification.
"""
import asyncio
from dataclasses import dataclass, field
from typing import Optional

import httpx


@dataclass
class Endpoint:
    """ADP endpoint definition."""
    path: str
    category: str
    weight: int
    description: str


# Core 20 ADP v2.1 endpoints (matches Citability scanner specification)
ENDPOINTS: list[Endpoint] = [
    # Core (5)
    Endpoint("/.well-known/ai.json", "core", 20, "AI discovery descriptor (required)"),
    Endpoint("/.well-known/security.txt", "core", 3, "Security contact info"),
    Endpoint("/robots.txt", "core", 10, "Robots exclusion (with AI crawler rules)"),
    Endpoint("/ai-sitemap.xml", "core", 5, "AI-optimized sitemap"),
    Endpoint("/opensearch.xml", "core", 2, "OpenSearch description"),

    # Feeds (3)
    Endpoint("/feed.json", "feeds", 5, "JSON Feed"),
    Endpoint("/updates.json", "feeds", 5, "Updates feed"),
    Endpoint("/rss.xml", "feeds", 3, "RSS feed"),

    # AI Content (6)
    Endpoint("/llms.txt", "ai_content", 15, "LLM context file (llmstxt.org spec)"),
    Endpoint("/llms-full.txt", "ai_content", 5, "Full LLM context"),
    Endpoint("/llms-lite.txt", "ai_content", 3, "Condensed LLM context"),
    Endpoint("/ai-discovery.json", "ai_content", 10, "AI discovery JSON"),
    Endpoint("/ai-discovery.md", "ai_content", 3, "AI discovery markdown"),
    Endpoint("/knowledge-graph.json", "ai_content", 10, "Knowledge graph JSON"),

    # News (4)
    Endpoint("/news/llms.txt", "news", 5, "News-specific LLM context"),
    Endpoint("/news/speakable.json", "news", 5, "Speakable content for voice"),
    Endpoint("/news/changelog.json", "news", 3, "Structured changelog"),
    Endpoint("/news/archive.jsonl", "news", 3, "Historical news archive"),

    # API (2)
    Endpoint("/api/v1/webhooks/discovery", "api", 3, "Webhook discovery"),
    Endpoint("/api/v1/adp/stats", "api", 5, "ADP stats endpoint"),
]


@dataclass
class EndpointResult:
    """Result of checking a single endpoint."""
    path: str
    category: str
    weight: int
    found: bool
    status_code: Optional[int] = None
    content_length: Optional[int] = None
    error: Optional[str] = None


@dataclass
class AuditResult:
    """Complete audit result for a domain."""
    domain: str
    score: int  # 0-100
    found_count: int
    total_count: int
    by_category: dict[str, dict] = field(default_factory=dict)
    endpoints: list[EndpointResult] = field(default_factory=list)


async def _check_endpoint(
    client: httpx.AsyncClient, base_url: str, endpoint: Endpoint
) -> EndpointResult:
    """Check a single endpoint."""
    url = f"{base_url}{endpoint.path}"
    try:
        response = await client.get(url, follow_redirects=True, timeout=10.0)
        return EndpointResult(
            path=endpoint.path,
            category=endpoint.category,
            weight=endpoint.weight,
            found=response.status_code == 200,
            status_code=response.status_code,
            content_length=len(response.content) if response.status_code == 200 else None,
        )
    except Exception as e:
        return EndpointResult(
            path=endpoint.path,
            category=endpoint.category,
            weight=endpoint.weight,
            found=False,
            error=str(e)[:100],
        )


async def audit_domain(domain: str) -> AuditResult:
    """Audit a domain for ADP compliance.

    Args:
        domain: Domain name (e.g. "example.com") or full URL

    Returns:
        AuditResult with score, endpoint details, and category breakdown
    """
    if not domain.startswith("http"):
        domain = f"https://{domain}"
    base_url = domain.rstrip("/")

    headers = {"User-Agent": "adp-audit-cli/0.1.0 (+https://citability.ai)"}
    async with httpx.AsyncClient(headers=headers) as client:
        tasks = [_check_endpoint(client, base_url, ep) for ep in ENDPOINTS]
        results = await asyncio.gather(*tasks)

    # Calculate weighted score
    max_weight = sum(ep.weight for ep in ENDPOINTS)
    earned_weight = sum(r.weight for r in results if r.found)
    score = int((earned_weight / max_weight) * 100) if max_weight else 0

    # Group by category
    by_category: dict[str, dict] = {}
    for r in results:
        cat = by_category.setdefault(
            r.category,
            {"found": 0, "total": 0, "weight_earned": 0, "weight_total": 0},
        )
        cat["total"] += 1
        cat["weight_total"] += r.weight
        if r.found:
            cat["found"] += 1
            cat["weight_earned"] += r.weight

    return AuditResult(
        domain=domain.replace("https://", "").replace("http://", ""),
        score=score,
        found_count=sum(1 for r in results if r.found),
        total_count=len(results),
        by_category=by_category,
        endpoints=results,
    )
