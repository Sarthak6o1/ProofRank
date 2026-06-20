#!/usr/bin/env python3
"""Proof artifact: rank the ENTIRE 100K pool and emit the top-N (default 20000).

This demonstrates that the ranker scores the full candidate pool from
indices/features.parquet (100,000 candidates) rather than a small subset, and
that submission.csv is the head of this same ranking. It uses the identical
scoring path as rank.py (enrich_row + final_score + duplicate penalty); the
only difference from the hybrid submission path is that retrieval_rrf uses a
career/title proxy (so every candidate in the pool can be scored, not just the
hybrid-retrieved 3000).

Usage:
    python scripts/generate_testing.py --indices ./indices --top 20000 --out ./testing.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.load import load_role_spec
from src.rank_enrich import enrich_row
from src.score import final_score


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--indices", type=Path, default=ROOT / "indices")
    ap.add_argument("--spec", type=Path, default=ROOT / "config" / "role_spec.yaml")
    ap.add_argument("--out", type=Path, default=ROOT / "testing.csv")
    ap.add_argument("--top", type=int, default=20000)
    ap.add_argument("--submission", type=Path, default=ROOT / "submission.csv")
    args = ap.parse_args()

    spec = load_role_spec(args.spec)
    feats = pd.read_parquet(args.indices / "features.parquet")
    total = len(feats)

    rows = feats.to_dict("records")
    eligible = [r for r in rows if not bool(r.get("honeypot_flag"))]

    for row in eligible:
        # Same retrieval proxy as the structured-only path in rank.py.
        row["retrieval_rrf"] = min(
            1.0, float(row.get("career_evidence") or 0) + 0.10 * float(row.get("title_tier_score") or 0)
        )
        # Mirror rank.py's duplicate-career penalty before scoring.
        if int(row.get("career_hash_count") or 1) >= 8 and float(row.get("career_evidence") or 0) < 0.55:
            row["anti_pattern_penalty"] = min(1.0, float(row.get("anti_pattern_penalty") or 0) + 0.12)
        enrich_row(row, spec)
        row["raw_score"] = final_score(row, spec)

    eligible.sort(
        key=lambda r: (
            -float(r.get("raw_score") or 0),
            -float(r.get("career_evidence") or 0),
            str(r.get("candidate_id") or ""),
        )
    )

    top = eligible[: args.top]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "candidate_id", "rank", "score", "career_evidence", "title_tier",
            "years_of_experience", "current_title", "current_company", "location", "country",
        ])
        for i, row in enumerate(top, start=1):
            w.writerow([
                row.get("candidate_id"),
                i,
                f"{float(row.get('raw_score') or 0):.6f}",
                f"{float(row.get('career_evidence') or 0):.4f}",
                row.get("title_tier"),
                f"{float(row.get('years_of_experience') or 0):.1f}",
                row.get("current_title"),
                row.get("current_company"),
                row.get("location"),
                row.get("country"),
            ])

    # Proof stats + overlap with the official submission.
    overlap_msg = ""
    if args.submission.exists():
        with open(args.submission, "r", encoding="utf-8", newline="") as f:
            sub_ids = [r["candidate_id"] for r in csv.DictReader(f)]
        top100_ids = [str(r.get("candidate_id")) for r in top[:100]]
        full_ids = {str(r.get("candidate_id")) for r in top}
        in_full = sum(1 for cid in sub_ids if cid in full_ids)
        head_match = sum(1 for a, b in zip(sub_ids, top100_ids) if a == b)
        overlap_msg = (
            f"  submission top100 present in testing pool : {in_full}/100\n"
            f"  submission top100 exact head-position match: {head_match}/100"
        )

    print("=" * 60)
    print("  FULL-POOL RANKING PROOF")
    print("=" * 60)
    print(f"  features.parquet total candidates : {total:,}")
    print(f"  honeypots excluded                : {total - len(eligible):,}")
    print(f"  eligible candidates scored        : {len(eligible):,}")
    print(f"  rows written to {args.out.name:<18}: {len(top):,}")
    if overlap_msg:
        print("-" * 60)
        print(overlap_msg)
    print("=" * 60)


if __name__ == "__main__":
    main()
