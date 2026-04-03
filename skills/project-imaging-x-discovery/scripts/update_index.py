#!/usr/bin/env python3
"""Parse Project-Imaging-X README.md tables into a structured datasets.json.

Usage:
    # From a local clone:
    python update_index.py /path/to/Project-Imaging-X/README.md

    # Or fetch from GitHub directly:
    python update_index.py --github
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

SECTION_RE = re.compile(r"^###\s+(.+)$")
TABLE_ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def build_github_raw_url(repo: str, ref: str, readme_path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{ref}/{readme_path.lstrip('/')}"


def fetch_readme_url(url: str) -> str:
    print(f"Fetching README from {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


def read_readme_local(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def parse_section_name(raw: str) -> str:
    """Strip emoji prefixes and whitespace from section headers."""
    cleaned = re.sub(r"[\U0001f000-\U0001ffff\u2600-\u27ff\ufe0f️]", "", raw)
    return cleaned.strip()


def parse_table_row(line: str, section: str) -> dict | None:
    """Parse one markdown table row into a record dict."""
    cells = [c.strip() for c in line.split("|")]
    # Remove empty strings from leading/trailing pipes
    cells = [c for c in cells if c != ""]
    if len(cells) < 9:
        return None

    idx_str, dataset_cell, year, dim, modality, structure = cells[:6]
    if not idx_str.isdigit():
        return None

    link_match = LINK_RE.search(dataset_cell)
    if link_match:
        name = link_match.group(1).strip()
        url = link_match.group(2).strip()
    else:
        name = dataset_cell.strip()
        url = ""

    # columns 6..end vary slightly but typically: images/volumes, label, task, diseases
    samples = cells[6] if len(cells) > 6 else ""
    label_str = cells[7] if len(cells) > 7 else ""
    task = cells[8] if len(cells) > 8 else ""
    diseases = cells[9] if len(cells) > 9 else ""

    return {
        "section": section,
        "name": name,
        "url": url,
        "year": year,
        "dim": dim,
        "modality": modality,
        "structure": structure,
        "samples": samples,
        "label": label_str.lower().startswith("yes"),
        "task": task,
        "diseases": diseases,
    }


def load_access_rules() -> tuple[list[dict], dict]:
    """Load access_rules.json from the skill root directory."""
    rules_path = Path(__file__).resolve().parent.parent / "access_rules.json"
    if not rules_path.exists():
        return [], {"access": "unknown", "method": "", "auth": None}
    data = json.loads(rules_path.read_text(encoding="utf-8"))
    return data["rules"], data["default"]


def classify_access(url: str, rules: list[dict], default: dict) -> dict:
    """Classify a URL's access type based on pattern matching rules."""
    url_lower = url.lower()
    for rule in rules:
        if rule["pattern"] in url_lower:
            return {
                "access": rule["access"],
                "download_method": rule["method"],
                "auth_instructions": rule.get("auth"),
            }
    return {
        "access": default["access"],
        "download_method": default["method"],
        "auth_instructions": default.get("auth"),
    }


def parse_readme(text: str) -> list[dict]:
    rules, default_rule = load_access_rules()
    records = []
    current_section = ""

    for line in text.splitlines():
        sec_match = SECTION_RE.match(line)
        if sec_match:
            current_section = parse_section_name(sec_match.group(1))
            continue

        if TABLE_ROW_RE.match(line) and current_section:
            rec = parse_table_row(line, current_section)
            if rec:
                access_info = classify_access(rec["url"], rules, default_rule)
                rec.update(access_info)
                records.append(rec)

    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "readme_path",
        nargs="?",
        default=None,
        help="Path to local README.md",
    )
    parser.add_argument(
        "--github",
        action="store_true",
        help="Fetch README.md from GitHub instead of a local file",
    )
    parser.add_argument(
        "--github-repo",
        default="uni-medical/Project-Imaging-X",
        help="GitHub repo in owner/repo form used with --github",
    )
    parser.add_argument(
        "--github-ref",
        default="main",
        help="Git ref used with --github",
    )
    parser.add_argument(
        "--github-readme-path",
        default="README.md",
        help="Repository-relative README path used with --github",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output JSON path (default: ../datasets.json relative to this script)",
    )
    args = parser.parse_args()

    if args.github:
        url = build_github_raw_url(args.github_repo, args.github_ref, args.github_readme_path)
        text = fetch_readme_url(url)
    elif args.readme_path:
        text = read_readme_local(args.readme_path)
    else:
        parser.error("Provide a local README path or use --github")

    records = parse_readme(text)

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = Path(__file__).resolve().parent.parent / "datasets.json"

    out_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Print summary
    sections = {}
    access_counts = {}
    for r in records:
        sections[r["section"]] = sections.get(r["section"], 0) + 1
        a = r.get("access", "unknown")
        access_counts[a] = access_counts.get(a, 0) + 1
    print(f"Parsed {len(records)} datasets across {len(sections)} sections:", file=sys.stderr)
    for sec, cnt in sorted(sections.items(), key=lambda x: -x[1]):
        print(f"  {cnt:4d}  {sec}", file=sys.stderr)
    print(f"\nAccess classification:", file=sys.stderr)
    for a, cnt in sorted(access_counts.items(), key=lambda x: -x[1]):
        print(f"  {cnt:4d}  {a}", file=sys.stderr)
    print(f"\nWritten to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
