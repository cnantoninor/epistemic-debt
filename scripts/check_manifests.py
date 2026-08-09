#!/usr/bin/env python3
"""Validate .claude-plugin/plugin.json and marketplace.json: both must be
valid JSON, and plugin.json's version must match both version fields in
marketplace.json (metadata.version and the matching plugins[] entry) — a
version bump in one is easy to forget in the other otherwise."""
from __future__ import annotations

import json
import sys


def main() -> int:
    with open(".claude-plugin/plugin.json") as f:
        plugin = json.load(f)
    with open(".claude-plugin/marketplace.json") as f:
        marketplace = json.load(f)

    plugin_version = plugin["version"]
    marketplace_version = marketplace["metadata"]["version"]
    entry = next(p for p in marketplace["plugins"] if p["name"] == plugin["name"])
    entry_version = entry["version"]

    versions = {
        "plugin.json:version": plugin_version,
        "marketplace.json:metadata.version": marketplace_version,
        "marketplace.json:plugins[].version": entry_version,
    }

    mismatched = {k: v for k, v in versions.items() if v != plugin_version}
    if mismatched:
        print(f"Version mismatch across manifests: {versions}", file=sys.stderr)
        return 1

    print(f"Manifests OK: {versions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
