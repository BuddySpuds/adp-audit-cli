---
name: adp-audit
description: Audit a website against the AI Discovery Protocol (ADP) and fix what it finds. Use when someone asks whether AI crawlers can read their site, wants markdown copies of their pages, asks about llms.txt or AI discovery files, or wants to measure which AI crawlers fetch what. Checks that each content page has a markdown copy linked from the page body, then helps add the copies and set up crawler logging.
---

# ADP audit

The AI Discovery Protocol has one required level: every content page has a
markdown copy, and the page body links to it. Everything else (llms.txt, a
meta-index, a knowledge graph, feeds, agent manifests) is optional.

Specification, registry and measured results:
https://github.com/BuddySpuds/AI-Discovery-Protocol

## 1. Run the audit

```bash
pip install git+https://github.com/BuddySpuds/adp-audit-cli
adp-audit <domain> --json
```

If the person has named the pages that matter, pass each with `--page`.
Otherwise the tool samples the sitemap, and the sample may include pages they
do not consider content (pricing, landing pages). Ask which page types count
before reporting a sampled page as a failure.

If the site keeps its copies in a separate sitemap, add `--sitemap <url>`.

## 2. Report

Lead with Level 1: how many of the audited pages conform, and for each
failing page the single reason from its `note`. Then one line on the optional
levels. Do not turn the result into a score.

## 3. Fix, in this order

1. **Pages with no copy.** Generate the copy from the same source as the
   page (the CMS record, the markdown file, the template context), never by
   scraping the rendered page or rewriting it. The copy must say nothing the
   page does not say. Serve it as `text/markdown` with
   `X-Robots-Tag: noindex, follow` and a canonical `Link` header to the page.
2. **Copy announced in the head only.** Add a visible link in the body
   template. Clients that work from extracted text never see the head.
3. **robots.txt blocks an AI crawler.** Show the rule and ask before changing
   it: blocking may be deliberate.
4. **Recommended:** list the copies in a dedicated sitemap, and add the
   `<link rel="alternate" type="text/markdown">` head link.
5. **Optional levels.** Build these only if asked. Say plainly that on the
   one site where they have been measured they drew under 2% of crawler
   requests.

Work in the project's own framework and conventions. Add a test that every
content page type renders a body link to a copy that returns 200.

## 4. Set up measurement

Without logs nobody can tell whether the copies are read. Log, for each
request from a known AI or search crawler: crawler name, path, status, the
`Accept` header and the time. Group paths into pages, copies, robots.txt and
sitemaps, and optional files. Where an operator publishes its address ranges
(OpenAI and Perplexity do), check the request address against them.

## Rules

- **Never promise citations, rankings or traffic.** The audit shows whether a
  site is published in a form crawlers are observed to fetch. It does not
  show that any AI system will cite it. If asked what the benefit is, quote
  the measured results and their limits (one site, requests not citations).
- **Never invent content for a copy.** No summaries, no added claims, no
  example facts.
- **Do not present the sample as the whole site.** Say how many pages were
  audited.
- **Do not send the person's site details to third-party services** beyond
  fetching the site's own public pages.
