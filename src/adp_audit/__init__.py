"""
ADP Audit CLI — audit domains for AI Discovery Protocol compliance.

Built by Citability.ai (https://citability.ai) — AI visibility scoring platform.
"""
from adp_audit.audit import (
    AuditResult,
    Endpoint,
    EndpointResult,
    ENDPOINTS,
    audit_domain,
)

__version__ = "0.1.0"
__all__ = ["AuditResult", "Endpoint", "EndpointResult", "ENDPOINTS", "audit_domain"]
