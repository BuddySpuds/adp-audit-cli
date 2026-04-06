# adp-audit-cli

[![PyPI](https://img.shields.io/pypi/v/adp-audit-cli.svg)](https://pypi.org/project/adp-audit-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Audit any domain for **AI Discovery Protocol (ADP)** compliance from your terminal. Built by [Citability](https://citability.ai) — the AI visibility scoring platform that scans 607M domains.

## What is ADP?

The **AI Discovery Protocol (ADP)** is a collection of well-known endpoints that make a website discoverable, parseable, and citable by AI agents like ChatGPT, Claude, Perplexity, and Gemini. Sites that implement ADP get cited more often by LLMs because the agents can find structured context, content feeds, and capability descriptors at predictable URLs.

This CLI checks the **20 ADP v2.1 endpoints** across five categories:

- **Core** (5) — `.well-known/ai.json`, `.well-known/security.txt`, `robots.txt`, `ai-sitemap.xml`, `opensearch.xml`
- **Feeds** (3) — `feed.json`, `updates.json`, `rss.xml`
- **AI Content** (6) — `llms.txt`, `llms-full.txt`, `llms-lite.txt`, `ai-discovery.json`, `ai-discovery.md`, `knowledge-graph.json`
- **News** (4) — `news/llms.txt`, `news/speakable.json`, `news/changelog.json`, `news/archive.jsonl`
- **API** (2) — `api/v1/webhooks/discovery`, `api/v1/adp/stats`

The endpoint list mirrors the public ADP v2.1 spec used by the [Citability scanner](https://citability.ai/scan).

## Install

```bash
pip install adp-audit-cli
```

## Usage

```bash
adp-audit citability.ai
```

Output:
```
Auditing citability.ai...

╭─ ADP Score: citability.ai ─╮
│ 100/100  •  20/20 endpoints found │
╰─────────────────────────────────────╯

         By Category
┌────────────┬───────┬───────┐
│ Category   │ Found │ Score │
├────────────┼───────┼───────┤
│ Core       │  5/5  │  100% │
│ Feeds      │  3/3  │  100% │
│ Ai Content │  6/6  │  100% │
│ News       │  4/4  │  100% │
│ Api        │  2/2  │  100% │
└────────────┴───────┴───────┘
```

The CLI exits `0` if score >= 50, otherwise `1` — useful in CI pipelines.

## Python API

```python
import asyncio
from adp_audit import audit_domain

result = asyncio.run(audit_domain("citability.ai"))
print(f"Score: {result.score}/100")
print(f"Found: {result.found_count}/{result.total_count}")

for endpoint in result.endpoints:
    if endpoint.found:
        print(f"✓ {endpoint.path}")
```

## Want the full picture?

This CLI checks ADP endpoint *presence*. For deeper analysis — content quality, validation, citation readiness, AI agent commerce capability, performance metrics, and competitive intelligence — try the free scanner at:

**[https://citability.ai/scan](https://citability.ai/scan)**

[Citability](https://citability.ai) scores domains across **5 pillars** (Authority, Performance, Content, Social, Agentic) using **44+ metrics** from Common Crawl, DataForSEO, PageSpeed Insights, and proprietary scanners across **51 protocol endpoints**.

## Related projects

- [llmstxt.org](https://llmstxt.org/) — the llms.txt specification
- [Citability](https://citability.ai) — full AI visibility platform

## License

MIT — see [LICENSE](LICENSE) for details.

---

Built by [Citability.ai](https://citability.ai) — measuring AI visibility across 607M domains. Learn more about the AI Discovery Protocol at [citability.ai](https://citability.ai).
