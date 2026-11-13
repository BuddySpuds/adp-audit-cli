# adp-audit-cli

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Audit a site against the
[AI Discovery Protocol](https://github.com/BuddySpuds/AI-Discovery-Protocol)
(ADP) from your terminal.

## What it checks

ADP 3.1 has one required level. Every content page has a markdown copy, and
the page body links to it. The tool:

1. reads `robots.txt` and the sitemaps it names;
2. samples pages from the sitemap, across the site's sections;
3. for each page, looks for a link to a markdown copy, fetches the copy, and
   checks that it is markdown, linked from the page body and open to AI
   crawlers;
4. reports, as a recommendation, whether the copy is listed in a sitemap;
5. reports which of the optional endpoints (`llms.txt`, a meta-index, feeds,
   agent manifests) the site serves.

The list of levels, requirements and endpoints is not written in this tool.
It is read from the ADP registry, a copy of which ships in the package
(`src/adp_audit/registry.json`), so the tool and the specification cannot
disagree.

There is no score out of 100. Optional endpoints are reported and not
scored, because on the site where they have been measured they draw very few
crawler requests. See
[RESULTS.md](https://github.com/BuddySpuds/AI-Discovery-Protocol/blob/main/RESULTS.md).

The audit says whether a site is published in the form the protocol
describes. It does not predict whether an AI system will cite the site.

## Install

```bash
pip install git+https://github.com/BuddySpuds/adp-audit-cli
```

## Usage

```bash
adp-audit example.com
```

```
example.com  ADP 3.1
Level 1 (page copies, required): partial  3 of 5 sampled pages conform

robots.txt: yes   sitemap: yes   URLs in sitemap: 325   markdown copies in sitemap: 0
```

followed by a table of the sampled pages and a summary of the optional
levels.

| Option | What it does |
|---|---|
| `--page URL` | Audit this page instead of sampling. Repeatable |
| `--sample N` | Pages to sample from the sitemap (default 5) |
| `--sitemap URL` | Also read this sitemap, for example a dedicated sitemap of copies |
| `--json` | Print the result as JSON |
| `--strict` | Exit 1 unless every sampled page conforms |
| `-v` | List every endpoint |

Exit status is 0 when at least one sampled page conforms (every one, with
`--strict`) and 1 otherwise, so it can gate a CI job.

The sample is a sample. Only you know which of your pages are content pages;
pass them with `--page` for a definite answer.

## Python API

```python
import asyncio
from adp_audit import audit_domain

result = asyncio.run(audit_domain("example.com", sample=10))
print(result.level_1, result.pages_conforming, len(result.pages))
for page in result.pages:
    print(page.url, page.conforms, page.note)
```

## As an agent skill

[skills/adp-audit/SKILL.md](skills/adp-audit/SKILL.md) packages the audit for
coding agents that load skills. Copy the `adp-audit` folder into your agent's
skills directory. It is free.

## Keeping the registry current

```bash
python scripts/sync_registry.py           # copy the registry from the specification repository
python scripts/sync_registry.py --check   # fail if the bundled copy differs
```

A weekly workflow runs the check.

## Development

```bash
pip install -e ".[test]"
pytest
```

The tests use a mock transport and make no network requests.

## License

MIT. See [LICENSE](LICENSE). Maintained by [Pressonify.ai](https://pressonify.ai).
