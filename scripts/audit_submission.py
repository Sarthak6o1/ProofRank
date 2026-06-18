#!/usr/bin/env python3
"""Audit a ranked submission CSV for honeypots, traps, and format issues."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.features import extract_features
from src.load import iter_candidates, load_role_spec


def load_submission(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def build_lookup(candidates_path: Path) -> dict[str, dict]:
    return {c["candidate_id"]: c for c in iter_candidates(candidates_path)}


def audit(csv_path: Path, candidates_path: Path, spec_path: Path) -> dict:
    rows = load_submission(csv_path)
    lookup = build_lookup(candidates_path)
    spec = load_role_spec(spec_path)

    missing = []
    honeypots = []
    traps = []
    stuffers = []

    for row in rows:
        cid = row["candidate_id"]
        if cid not in lookup:
            missing.append(cid)
            continue
        feat = extract_features(lookup[cid], spec)
        rank = int(row["rank"])
        if feat.get("honeypot_flag"):
            honeypots.append((rank, cid, feat.get("honeypot_reasons")))
        if feat.get("title_tier") == "trap":
            traps.append((rank, cid, feat.get("current_title")))
        if feat.get("stuffer_flag"):
            stuffers.append((rank, cid))

    return {
        "rows": len(rows),
        "missing_ids": missing,
        "honeypots_in_top100": honeypots,
        "trap_titles_in_top100": traps,
        "stuffers_in_top100": stuffers,
        "honeypot_rate_pct": round(100 * len(honeypots) / max(len(rows), 1), 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument(
        "--candidates",
        type=Path,
        default=ROOT / "India_runs_data_and_ai_challenge" / "candidates.jsonl",
    )
    parser.add_argument("--spec", type=Path, default=ROOT / "config" / "role_spec.yaml")
    args = parser.parse_args()

    report = audit(args.csv, args.candidates, args.spec)
    print(json.dumps(report, indent=2))
    if report["honeypot_rate_pct"] > 10:
        print("\nWARNING: honeypot rate > 10% — Stage 3 disqualification risk.")
    if report["missing_ids"]:
        print(f"\nERROR: {len(report['missing_ids'])} candidate_ids not in pool.")


if __name__ == "__main__":
    main()
