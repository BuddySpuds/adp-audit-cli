"""Tests for adp-audit."""
import pytest

from adp_audit import ENDPOINTS, AuditResult, audit_domain


def test_endpoints_defined():
    """All 20 ADP endpoints should be defined."""
    assert len(ENDPOINTS) == 20


def test_categories_present():
    """All five ADP v2.1 categories should be present."""
    categories = {ep.category for ep in ENDPOINTS}
    assert categories == {"core", "feeds", "ai_content", "news", "api"}


def test_weights_positive():
    """All endpoints have positive weight."""
    assert all(ep.weight > 0 for ep in ENDPOINTS)


def test_paths_unique():
    """No duplicate endpoint paths."""
    paths = [ep.path for ep in ENDPOINTS]
    assert len(paths) == len(set(paths))


@pytest.mark.asyncio
async def test_audit_returns_result():
    """Audit should return an AuditResult with all 20 endpoints checked."""
    result = await audit_domain("example.com")
    assert isinstance(result, AuditResult)
    assert result.total_count == 20
    assert 0 <= result.score <= 100
    assert len(result.endpoints) == 20
