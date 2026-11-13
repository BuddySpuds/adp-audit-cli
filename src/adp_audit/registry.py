"""The ADP registry: the one list of levels, page requirements and endpoints.

``registry.json`` is a copy of ``registry/adp-registry.json`` in the
AI-Discovery-Protocol repository. Do not edit it here: change it there and
copy it across (``scripts/sync_registry.py``).
"""

import json
from functools import lru_cache
from importlib import resources

CANONICAL_URL = (
    "https://raw.githubusercontent.com/BuddySpuds/AI-Discovery-Protocol/"
    "main/registry/adp-registry.json"
)


@lru_cache(maxsize=1)
def load() -> dict:
    text = resources.files("adp_audit").joinpath("registry.json").read_text("utf-8")
    return json.loads(text)


def endpoints(level: int | None = None) -> list[dict]:
    items = load()["endpoints"]
    return [e for e in items if level is None or e["level"] == level]


def levels() -> list[dict]:
    return load()["levels"]


def page_requirements(required_only: bool = False) -> list[dict]:
    items = load()["page_requirements"]
    return [r for r in items if not required_only or r["status"] == "required"]


def version() -> str:
    return load()["version"]
