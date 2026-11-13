#!/usr/bin/env python3
"""Copy the canonical ADP registry into the package, or check it is current.

    python scripts/sync_registry.py           # overwrite the bundled copy
    python scripts/sync_registry.py --check   # exit 1 if the copy differs
"""

import json
import sys
import urllib.request
from pathlib import Path

CANONICAL = (
    "https://raw.githubusercontent.com/BuddySpuds/AI-Discovery-Protocol/"
    "main/registry/adp-registry.json"
)
BUNDLED = Path(__file__).resolve().parent.parent / "src" / "adp_audit" / "registry.json"


def main() -> int:
    with urllib.request.urlopen(CANONICAL, timeout=30) as response:
        canonical_text = response.read().decode("utf-8")
    if "--check" in sys.argv:
        if json.loads(canonical_text) != json.loads(BUNDLED.read_text()):
            print(f"Bundled registry differs from {CANONICAL}")
            print("Run: python scripts/sync_registry.py")
            return 1
        print("Bundled registry matches the specification.")
        return 0
    BUNDLED.write_text(canonical_text)
    print(f"Wrote {BUNDLED}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
