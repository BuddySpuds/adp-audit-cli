"""Audit a site against the AI Discovery Protocol (ADP) registry."""

from adp_audit.audit import (
    AuditResult,
    EndpointResult,
    PageResult,
    audit_domain,
    choose_pages,
    find_copy,
    parse_sitemap,
)

__version__ = "0.2.0"
__all__ = [
    "AuditResult",
    "EndpointResult",
    "PageResult",
    "audit_domain",
    "choose_pages",
    "find_copy",
    "parse_sitemap",
]
