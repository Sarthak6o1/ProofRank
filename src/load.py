from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Iterable


def open_text(path: Path):
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "r", encoding="utf-8")


def iter_candidates(path: Path) -> Iterable[dict]:
    """Yield candidates from jsonl/jsonl.gz or a JSON array sample file."""
    if path.suffix.lower() == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for candidate in data:
            if candidate:
                yield candidate
        return

    with open_text(path) as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_candidates(path: Path, limit: int | None = None) -> list[dict]:
    out: list[dict] = []
    for i, candidate in enumerate(iter_candidates(path)):
        if limit is not None and i >= limit:
            break
        out.append(candidate)
    return out


def default_role_spec() -> dict:
    return {
        "retrieval": {"top_k": 3000, "rrf_k": 60, "safety_pool": 350},
        "scoring_weights": {
            "retrieval_rrf": 0.14,
            "career_evidence": 0.38,
            "title_tier": 0.13,
            "yoe_location_fit": 0.09,
            "skill_trust": 0.07,
            "assessment_score": 0.05,
            "product_company": 0.04,
            "education_score": 0.04,
            "company_scale_score": 0.03,
            "work_mode_fit": 0.02,
            "platform_activity_score": 0.02,
            "anti_pattern_penalty": 0.12,
        },
        "top10_guard": {
            "min_career_evidence": 0.50,
            "min_title_tier_score": 0.65,
            "exclude_trap_titles": True,
        },
        "yoe": {"min": 5.0, "max": 9.0},
        "location_boost": [
            "India",
            "Pune",
            "Noida",
            "Delhi",
            "Gurgaon",
            "Gurugram",
            "Bangalore",
            "Bengaluru",
            "Hyderabad",
            "Mumbai",
        ],
    }


def load_role_spec(path: Path) -> dict:
    if not path.exists():
        return default_role_spec()
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to read config/role_spec.yaml") from exc

    with open(path, "r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}
    spec = default_role_spec()
    spec.update(loaded)
    for section in ("retrieval", "scoring_weights", "top10_guard", "yoe"):
        merged = dict(default_role_spec().get(section, {}))
        merged.update(loaded.get(section, {}) if isinstance(loaded.get(section), dict) else {})
        spec[section] = merged
    return spec
