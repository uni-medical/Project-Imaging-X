#!/usr/bin/env python3
"""Deterministic search and ranking for medical-imaging-fetch."""

import argparse
import json
import re
from pathlib import Path


ACCESS_ORDER = {"open": 0, "registration": 1, "application": 2, "unknown": 3}

SYNONYMS = {
    "modality": {
        "mri": ["mr", "mri"],
        "mr": ["mr", "mri"],
        "ct": ["ct"],
        "xray": ["x-ray", "xray", "radiograph"],
        "x-ray": ["x-ray", "xray", "radiograph"],
        "ultrasound": ["ultrasound", "us"],
        "us": ["ultrasound", "us"],
        "pathology": ["pathology", "histopathology", "wsi"],
        "pet": ["pet"],
        "oct": ["oct"],
        "fundus": ["fundus", "retina"],
        "endoscopy": ["endoscopy", "colonoscopy", "gastroscopy"],
    },
    "task": {
        "segmentation": ["seg"],
        "seg": ["seg"],
        "classification": ["cls"],
        "cls": ["cls"],
        "detection": ["det"],
        "det": ["det"],
        "registration": ["reg"],
        "reg": ["reg"],
        "reconstruction": ["rec"],
        "rec": ["rec"],
        "prediction": ["pred"],
        "pred": ["pred"],
    },
    "dim": {
        "3d": ["3d"],
        "2d": ["2d"],
        "video": ["video"],
    },
}


def load_records(skill_root: Path) -> list[dict]:
    datasets_path = skill_root / "datasets.json"
    with datasets_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def normalize_value(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def expand_terms(field: str, raw: str | None) -> list[str]:
    if not raw:
        return []
    raw = normalize_value(raw)
    mapping = SYNONYMS.get(field, {})
    return mapping.get(raw, [raw])


def parse_bool(raw: str | None) -> bool | None:
    if raw is None:
        return None
    value = normalize_value(raw)
    if value in {"1", "true", "yes", "y"}:
        return True
    if value in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"Unsupported boolean value: {raw}")


def parse_samples(raw: str) -> float:
    text = normalize_value(raw).replace(",", "")
    if not text or text in {"na", "unknown"}:
        return -1
    mult = 1
    if text.endswith("k"):
        mult = 1_000
        text = text[:-1]
    elif text.endswith("m"):
        mult = 1_000_000
        text = text[:-1]
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return -1
    return float(match.group(1)) * mult


def parse_year(raw: str) -> int:
    match = re.search(r"(19|20)\d{2}", raw or "")
    return int(match.group(0)) if match else -1


def normalize_task(raw: str) -> set[str]:
    value = normalize_value(raw)
    if not value or value == "na":
        return set()
    parts = re.split(r"[,/]", value.replace(" ", ""))
    normalized = set()
    for part in parts:
        if not part:
            continue
        if part.startswith("seg"):
            normalized.add("seg")
        elif part.startswith("cls"):
            normalized.add("cls")
        elif part.startswith("det"):
            normalized.add("det")
        elif part.startswith("reg"):
            normalized.add("reg")
        elif part.startswith("rec"):
            normalized.add("rec")
        elif part.startswith("pred"):
            normalized.add("pred")
        elif part.startswith("vqa"):
            normalized.add("vqa")
        else:
            normalized.add(part)
    return normalized


def value_matches(field_value: str, terms: list[str]) -> bool:
    if not terms:
        return True
    haystack = normalize_value(field_value)
    for term in terms:
        if re.search(rf"(^|[^a-z0-9]){re.escape(term)}([^a-z0-9]|$)", haystack):
            return True
        if len(term) >= 6 and term in haystack:
            return True
    return False


def modality_matches(field_value: str, terms: list[str]) -> bool:
    if not terms:
        return True
    haystack = normalize_value(field_value)
    return any(
        re.search(rf"(^|[^a-z0-9]){re.escape(term)}([^a-z0-9]|$)", haystack)
        for term in terms
    )


def task_matches(field_value: str, terms: list[str]) -> bool:
    if not terms:
        return True
    task_tokens = normalize_task(field_value)
    return any(term in task_tokens for term in terms)


def access_matches(field_value: str, requested: str | None) -> bool:
    if not requested:
        return True
    return normalize_value(field_value) == normalize_value(requested)


def label_matches(field_value: bool, requested: bool | None) -> bool:
    if requested is None:
        return True
    return bool(field_value) is requested


def strict_match(record: dict, filters: dict) -> bool:
    return (
        modality_matches(record.get("modality", ""), filters["modality"])
        and value_matches(record.get("structure", ""), filters["structure"])
        and value_matches(record.get("diseases", ""), filters["disease"])
        and task_matches(record.get("task", ""), filters["task"])
        and value_matches(record.get("dim", ""), filters["dim"])
        and access_matches(record.get("access", ""), filters["access"])
        and label_matches(record.get("label", False), filters["label"])
        and value_matches(record.get("url", ""), filters["platform"])
    )


def near_match_candidate(record: dict, filters: dict, has_strict: bool) -> bool:
    if filters["platform"] and not value_matches(record.get("url", ""), filters["platform"]):
        return False
    if not has_strict:
        return True
    # Keep near results close to the same retrieval space once strict matches already exist.
    if filters["modality"] and not modality_matches(record.get("modality", ""), filters["modality"]):
        return False
    if filters["access"] and not access_matches(record.get("access", ""), filters["access"]):
        return False
    if filters["structure"] and not value_matches(record.get("structure", ""), filters["structure"]):
        return False
    if filters["task"] and not task_matches(record.get("task", ""), filters["task"]):
        return False
    return True


def has_modality_coverage(records: list[dict], filters: dict) -> bool:
    return any(modality_matches(record.get("modality", ""), filters["modality"]) for record in records)


def min_near_score(filters: dict, has_strict: bool) -> int:
    active_count = sum(
        1
        for value in filters.values()
        if value not in (None, [], "")
    )
    if active_count == 0:
        return 1
    if has_strict:
        return max(1, active_count - 1)
    return max(1, active_count - 2)


def partial_score(record: dict, filters: dict) -> int:
    checks = []
    if filters["modality"]:
        checks.append(modality_matches(record.get("modality", ""), filters["modality"]))
    if filters["structure"]:
        checks.append(value_matches(record.get("structure", ""), filters["structure"]))
    if filters["disease"]:
        checks.append(value_matches(record.get("diseases", ""), filters["disease"]))
    if filters["task"]:
        checks.append(task_matches(record.get("task", ""), filters["task"]))
    if filters["dim"]:
        checks.append(value_matches(record.get("dim", ""), filters["dim"]))
    if filters["access"]:
        checks.append(access_matches(record.get("access", ""), filters["access"]))
    if filters["label"] is not None:
        checks.append(label_matches(record.get("label", False), filters["label"]))
    if filters["platform"]:
        checks.append(value_matches(record.get("url", ""), filters["platform"]))
    return sum(int(matched) for matched in checks)


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


def sort_records(records: list[dict], prefer_open: bool) -> list[dict]:
    def key(record: dict):
        access_rank = ACCESS_ORDER.get(record.get("access", "unknown"), 99)
        return (
            access_rank if prefer_open else 0,
            0 if record.get("label") else 1,
            -parse_samples(record.get("samples", "")),
            -parse_year(record.get("year", "")),
            0 if record.get("url") else 1,
            record.get("name", "").lower(),
        )

    return sorted(records, key=key)


def annotate(records: list[dict], filters: dict) -> list[dict]:
    annotated = []
    active_constraints = [k for k, v in filters.items() if v not in (None, [], "")]
    for record in records:
        score = partial_score(record, filters)
        reasons = []
        if filters["access"] and not access_matches(record.get("access", ""), filters["access"]):
            reasons.append(f"access={record.get('access', 'unknown')}")
        if filters["label"] is not None and not label_matches(record.get("label", False), filters["label"]):
            reasons.append(f"label={record.get('label')}")
        if filters["dim"] and not value_matches(record.get("dim", ""), filters["dim"]):
            reasons.append(f"dim={record.get('dim', '')}")
        if filters["task"] and not task_matches(record.get("task", ""), filters["task"]):
            reasons.append(f"task={record.get('task', '')}")
        if filters["disease"] and not value_matches(record.get("diseases", ""), filters["disease"]):
            reasons.append(f"diseases={record.get('diseases', '')}")
        if filters["structure"] and not value_matches(record.get("structure", ""), filters["structure"]):
            reasons.append(f"structure={record.get('structure', '')}")
        if filters["modality"] and not modality_matches(record.get("modality", ""), filters["modality"]):
            reasons.append(f"modality={record.get('modality', '')}")
        item = dict(record)
        item["_match_score"] = score
        item["_constraint_count"] = len(active_constraints)
        item["_near_match_reasons"] = reasons
        annotated.append(item)
    return annotated


def build_filters(args: argparse.Namespace) -> dict:
    return {
        "modality": expand_terms("modality", args.modality),
        "structure": [normalize_value(args.structure)] if args.structure else [],
        "disease": [normalize_value(args.disease)] if args.disease else [],
        "task": expand_terms("task", args.task),
        "dim": expand_terms("dim", args.dim),
        "label": parse_bool(args.label),
        "access": normalize_value(args.access) if args.access else None,
        "platform": [normalize_value(args.platform)] if args.platform else [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", default=None, help="Override skill root directory")
    parser.add_argument("--modality")
    parser.add_argument("--structure")
    parser.add_argument("--disease")
    parser.add_argument("--task")
    parser.add_argument("--dim")
    parser.add_argument("--label")
    parser.add_argument("--access")
    parser.add_argument("--platform")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--prefer-open",
        action="store_true",
        help="Sort open datasets first within result groups",
    )
    args = parser.parse_args()

    skill_root = Path(args.skill_root) if args.skill_root else Path(__file__).resolve().parent.parent
    filters = build_filters(args)
    records = dedupe(load_records(skill_root))

    strict = [record for record in records if strict_match(record, filters)]
    strict = annotate(sort_records(strict, prefer_open=args.prefer_open), filters)

    near = []
    if strict:
        candidates = [record for record in records if record not in strict]
    else:
        candidates = records
    modality_covered = True
    if filters["modality"]:
        modality_covered = has_modality_coverage(records, filters)
    near_score_floor = min_near_score(filters, has_strict=bool(strict))
    for record in annotate(candidates, filters):
        if not near_match_candidate(record, filters, has_strict=bool(strict)):
            continue
        if filters["modality"] and not modality_covered:
            continue
        if record["_match_score"] <= 0:
            continue
        if record["_match_score"] < near_score_floor:
            continue
        near.append(record)
    near = sort_records(dedupe(near), prefer_open=args.prefer_open)
    near = [record for record in near if not strict_match(record, filters)]

    result = {
        "interpreted_query": {
            "modality": args.modality,
            "structure": args.structure,
            "disease": args.disease,
            "task": args.task,
            "dim": args.dim,
            "label": parse_bool(args.label),
            "access": args.access,
            "platform": args.platform,
            "prefer_open": args.prefer_open,
        },
        "strict_match_count": len(strict),
        "near_match_count": len(near),
        "strict_matches": strict[: args.top_k],
        "near_matches": near[: args.top_k],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
