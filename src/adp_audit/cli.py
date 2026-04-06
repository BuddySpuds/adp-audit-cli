"""CLI for adp-audit."""
import asyncio
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from adp_audit import audit_domain


def main():
    """CLI entry point."""
    console = Console()

    if len(sys.argv) < 2:
        console.print("[bold]ADP Audit CLI[/bold] — audit domains for AI Discovery Protocol compliance\n")
        console.print("[dim]Usage:[/dim] adp-audit <domain>")
        console.print("[dim]Example:[/dim] adp-audit citability.ai\n")
        console.print("Powered by Citability.ai — https://citability.ai")
        sys.exit(1)

    domain = sys.argv[1]
    console.print(f"\n[cyan]Auditing[/cyan] [bold]{domain}[/bold]...\n")

    result = asyncio.run(audit_domain(domain))

    # Score header
    score_color = "green" if result.score >= 80 else "yellow" if result.score >= 50 else "red"
    console.print(
        Panel(
            f"[bold {score_color}]{result.score}/100[/bold {score_color}]  •  "
            f"{result.found_count}/{result.total_count} endpoints found",
            title=f"ADP Score: {result.domain}",
            expand=False,
        )
    )

    # Category breakdown
    cat_table = Table(title="By Category", show_header=True)
    cat_table.add_column("Category")
    cat_table.add_column("Found", justify="right")
    cat_table.add_column("Score", justify="right")
    for cat, data in result.by_category.items():
        pct = int((data["weight_earned"] / data["weight_total"]) * 100) if data["weight_total"] else 0
        cat_table.add_row(
            cat.replace("_", " ").title(),
            f"{data['found']}/{data['total']}",
            f"{pct}%",
        )
    console.print(cat_table)

    # Endpoint details
    ep_table = Table(title="Endpoint Details", show_header=True)
    ep_table.add_column("Endpoint")
    ep_table.add_column("Status", justify="center")
    ep_table.add_column("Category")
    for r in result.endpoints:
        status = "[green]✓[/green]" if r.found else "[red]✗[/red]"
        ep_table.add_row(r.path, status, r.category.replace("_", " "))
    console.print(ep_table)

    console.print()
    console.print("[dim]For full AI visibility scoring across 5 pillars, try:[/dim]")
    console.print("[cyan]https://citability.ai/scan[/cyan]")
    sys.exit(0 if result.score >= 50 else 1)


if __name__ == "__main__":
    main()
