"""Command line for adp-audit."""

import argparse
import asyncio
import json
import sys

from rich.console import Console
from rich.table import Table

from adp_audit import registry
from adp_audit.audit import AuditResult, audit_domain

LEVEL_STYLE = {"met": "green", "partial": "yellow", "not met": "red"}


def _mark(value: bool) -> str:
    return "[green]yes[/green]" if value else "[red]no[/red]"


def render(result: AuditResult, console: Console, verbose: bool) -> None:
    style = LEVEL_STYLE[result.level_1]
    console.print(
        f"\n[bold]{result.domain}[/bold]  ADP {result.registry_version}\n"
        f"Level 1 (page copies, required): [bold {style}]{result.level_1}[/bold {style}]"
        f"  {result.pages_conforming} of {len(result.pages)} sampled pages conform\n"
    )
    console.print(
        f"robots.txt: {_mark(result.robots_found)}   "
        f"sitemap: {_mark(result.sitemap_found)}   "
        f"URLs in sitemap: {result.sitemap_urls}   "
        f"markdown copies in sitemap: {result.markdown_urls_in_sitemap}\n"
    )

    table = Table(title="Level 1: sampled pages")
    table.add_column("Page", overflow="fold")
    table.add_column("Copy")
    table.add_column("Body link")
    table.add_column("Crawlable")
    table.add_column("In sitemap (rec.)")
    table.add_column("Note", overflow="fold")
    for page in result.pages:
        table.add_row(
            page.url,
            _mark(page.markdown_copy),
            _mark(page.body_link),
            _mark(page.crawl_allowed),
            "yes" if page.sitemap_listing else "no",
            page.note or "",
        )
    console.print(table)

    names = {entry["level"]: entry["name"] for entry in registry.levels()}
    optional = Table(title="Optional levels")
    optional.add_column("Level")
    optional.add_column("Name")
    optional.add_column("Served", justify="right")
    for level, row in sorted(result.optional_levels().items()):
        optional.add_row(str(level), names[level], f"{row['served']} of {row['total']}")
    console.print(optional)

    if verbose:
        detail = Table(title="Endpoints")
        detail.add_column("Level")
        detail.add_column("Path")
        detail.add_column("Served")
        detail.add_column("Note")
        for endpoint in result.endpoints:
            note = f"from {endpoint.served_from}" if endpoint.served_from else ""
            detail.add_row(
                str(endpoint.level), endpoint.path, _mark(endpoint.found), note
            )
        console.print(detail)

    console.print(
        "\n[dim]Only Level 1 is required. The pages are a sample: pass --page to "
        "audit specific pages. Optional levels are not scored; measured request "
        "counts for each are in the specification's RESULTS.md.[/dim]\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="adp-audit",
        description="Audit a site against the AI Discovery Protocol registry.",
    )
    parser.add_argument("domain", help="domain or URL, for example example.com")
    parser.add_argument(
        "--page",
        action="append",
        default=[],
        help="audit this page instead of sampling the sitemap (repeatable)",
    )
    parser.add_argument(
        "--sample", type=int, default=5, help="pages to sample from the sitemap"
    )
    parser.add_argument(
        "--sitemap",
        action="append",
        default=[],
        help="also read this sitemap, for example a dedicated sitemap of copies",
    )
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 unless every sampled page conforms",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="list every endpoint"
    )
    args = parser.parse_args()

    result = asyncio.run(
        audit_domain(
            args.domain,
            sample=args.sample,
            pages=args.page or None,
            sitemaps=args.sitemap or None,
        )
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        render(result, Console(), args.verbose)

    passing = {"met"} if args.strict else {"met", "partial"}
    sys.exit(0 if result.level_1 in passing else 1)


if __name__ == "__main__":
    main()
