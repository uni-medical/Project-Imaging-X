#!/usr/bin/env python3
"""Lookup one dataset by name and return download-oriented metadata."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def normalize(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def load_records(skill_root: Path) -> list[dict]:
    path = skill_root / "datasets.json"
    return json.loads(path.read_text(encoding="utf-8"))


def dedupe(records: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for record in records:
        key = (record.get("name", ""), record.get("url", ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
    return result


def score_match(name_query: str, record_name: str) -> tuple[int, int, str]:
    query = normalize(name_query)
    name = normalize(record_name)
    if name == query:
        return (0, len(name), name)
    if len(query) >= 4 and re.search(rf"(^|[^a-z0-9]){re.escape(query)}([^a-z0-9]|$)", name):
        return (1, len(name), name)
    if len(query) >= 6 and query in name:
        return (2, len(name), name)
    return (99, len(name), name)


def match_type(name_query: str, record_name: str) -> str | None:
    query = normalize(name_query)
    name = normalize(record_name)
    if name == query:
        return "exact"
    if len(query) < 4:
        return None
    if re.search(rf"(^|[^a-z0-9]){re.escape(query)}([^a-z0-9]|$)", name):
        return "boundary"
    if len(query) >= 6 and query in name:
        return "substring"
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", help="Dataset name query")
    parser.add_argument("--name", dest="query_flag", default=None, help="Dataset name query")
    parser.add_argument("--skill-root", default=None, help="Override skill root directory")
    parser.add_argument("--top-k", type=int, default=5, help="Maximum matches to return")
    args = parser.parse_args()

    query = args.query_flag or args.query
    if not query:
        parser.error("Provide a dataset query either positionally or with --name")

    skill_root = Path(args.skill_root) if args.skill_root else Path(__file__).resolve().parent.parent
    records = dedupe(load_records(skill_root))
    matches = []
    for record in records:
        match_kind = match_type(query, record.get("name", ""))
        if not match_kind:
            continue
        item = dict(record)
        item["_match_type"] = match_kind
        matches.append(item)

    exact_matches = [item for item in matches if item.get("_match_type") == "exact"]
    if exact_matches:
        matches = exact_matches

    matches = sorted(matches, key=lambda item: score_match(query, item.get("name", "")))

    match_types = {item.get("_match_type") for item in matches}
    if not matches:
        resolution_mode = "unresolved"
    elif match_types == {"exact"}:
        resolution_mode = "exact"
    elif "boundary" in match_types or "substring" in match_types:
        resolution_mode = "family"
    else:
        resolution_mode = "ambiguous"

    result = {
        "query": query,
        "query_length": len(normalize(query)),
        "resolution_mode": resolution_mode,
        "match_count": len(matches),
        "matches": [
            {
                "name": item.get("name"),
                "url": item.get("url"),
                "year": item.get("year"),
                "modality": item.get("modality"),
                "structure": item.get("structure"),
                "task": item.get("task"),
                "access": item.get("access"),
                "download_method": item.get("download_method"),
                "auth_instructions": item.get("auth_instructions"),
                "match_type": item.get("_match_type"),
            }
            for item in matches[: args.top_k]
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
