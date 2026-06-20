#!/usr/bin/env python3
"""Offline ranking evaluation for the Senior AI Engineer JD.

The challenge ships no ground-truth relevance labels, so this harness builds a
transparent JD-rubric **silver-label** set via weak supervision and scores a
submission against it with NDCG@K / MRR / MAP. These numbers are NOT a truth
oracle (absolute values are inflated because labels and ranker both read the
same JD); their value is **relative** — comparing pipeline variant A vs B on the
identical label set tells you which configuration is better, which is exactly
what an offline benchmark is for (JD: "offline benchmarks ... offline-to-online
correlation").

Relevance is graded 0-3 from independent JD pillars, with hard disqualifiers
forced to 0, rather than from the ranker's weighted composite score.

Usage:
    python scripts/eval_ranking.py --indices ./indices --submission ./submission.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.load import load_role_spec

REL_THRESHOLD = 2  # label >= 2 counts as "relevant" for MRR / MAP


def _days_since(value: object) -> float | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except (TypeError, ValueError):
        return None


def _families(spec: dict) -> dict[str, list[str]]:
    fams = spec.get("career_evidence_terms") or {}
    return {k: [str(t).lower() for t in v] for k, v in fams.items()}


def _eval_terms(spec: dict) -> list[str]:
    return [str(t).lower() for t in (spec.get("rank_time") or {}).get("eval_evidence_terms", [])]


def _blob(row: pd.Series) -> str:
    parts = [
        str(row.get("career_terms") or "").replace("|", " "),
        str(row.get("current_role_excerpt") or ""),
        str(row.get("current_title") or ""),
        str(row.get("best_career_title") or ""),
    ]
    return " ".join(parts).lower()


def _has_any(text: str, terms: list[str]) -> bool:
    return any(t and t in text for t in terms)


def relevance_label(row: pd.Series, spec: dict, fams: dict, eval_terms: list[str]) -> int:
    """Graded 0-3 relevance from JD pillars; hard disqualifiers force 0."""
    if (
        bool(row.get("honeypot_flag"))
        or str(row.get("title_tier")) == "trap"
        or bool(row.get("consulting_only"))
        or bool(row.get("research_only"))
        or bool(row.get("cv_speech_without_ir"))
        or bool(row.get("stuffer_flag"))
    ):
        return 0

    text = _blob(row)
    career = float(row.get("career_evidence") or 0)
    yoe = float(row.get("years_of_experience") or 0)
    country = str(row.get("country") or "").lower()

    retrieval = _has_any(text, fams.get("retrieval", []))
    ranking = _has_any(text, fams.get("ranking", []))
    production = _has_any(text, fams.get("production", []))
    eval_ev = _has_any(text, eval_terms)
    product = float(row.get("product_company_score") or 0) >= 0.40
    location_ok = country == "india" or bool(row.get("willing_to_relocate"))
    band = 5.0 <= yoe <= 9.0
    days = _days_since(row.get("last_active_date"))
    active = (days is not None and days <= 180) and float(row.get("recruiter_response_rate") or 0) >= 0.30
    strong_title = float(row.get("title_tier_score") or 0) >= 0.65

    pillars = sum([retrieval, ranking, production, product, location_ok, band, active])
    core = retrieval and (ranking or production)

    if core and career >= 0.60 and pillars >= 6:
        return 3
    if core and career >= 0.45 and pillars >= 4:
        return 2
    if (eval_ev and core) or career >= 0.30 or strong_title:
        return 1
    return 0


def _dcg(gains: list[float]) -> float:
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg_at_k(ranked_labels: list[int], all_labels: list[int], k: int) -> float:
    gains = [2 ** rel - 1 for rel in ranked_labels[:k]]
    ideal = sorted(all_labels, reverse=True)[:k]
    idcg = _dcg([2 ** rel - 1 for rel in ideal])
    return _dcg(gains) / idcg if idcg > 0 else 0.0


def mrr(ranked_labels: list[int]) -> float:
    for i, rel in enumerate(ranked_labels, start=1):
        if rel >= REL_THRESHOLD:
            return 1.0 / i
    return 0.0


def map_at_k(ranked_labels: list[int], k: int) -> float:
    hits = 0
    precisions = []
    for i, rel in enumerate(ranked_labels[:k], start=1):
        if rel >= REL_THRESHOLD:
            hits += 1
            precisions.append(hits / i)
    return sum(precisions) / hits if hits else 0.0


def load_ranked_ids(submission: Path) -> list[str]:
    with open(submission, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: int(r["rank"]))
    return [r["candidate_id"] for r in rows]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--indices", type=Path, default=ROOT / "indices")
    ap.add_argument("--submission", type=Path, default=ROOT / "submission.csv")
    ap.add_argument("--spec", type=Path, default=ROOT / "config" / "role_spec.yaml")
    args = ap.parse_args()

    spec = load_role_spec(args.spec)
    fams = _families(spec)
    eval_terms = _eval_terms(spec)

    feats = pd.read_parquet(args.indices / "features.parquet")
    feats["__label"] = feats.apply(lambda r: relevance_label(r, spec, fams, eval_terms), axis=1)
    label_by_id = dict(zip(feats["candidate_id"].astype(str), feats["__label"]))

    # Eligible pool excludes hard-dropped honeypots (mirrors the ranker).
    eligible = feats[~feats["honeypot_flag"].astype(bool)]
    all_labels = eligible["__label"].tolist()

    ranked_ids = load_ranked_ids(args.submission)
    ranked_labels = [int(label_by_id.get(cid, 0)) for cid in ranked_ids]

    pool_hist = {g: int((eligible["__label"] == g).sum()) for g in (3, 2, 1, 0)}
    top10_hist = {g: ranked_labels[:10].count(g) for g in (3, 2, 1, 0)}
    top100_hist = {g: ranked_labels.count(g) for g in (3, 2, 1, 0)}

    # Coverage stats on the submitted top 100 (for the ablation table).
    sub = feats[feats["candidate_id"].astype(str).isin(ranked_ids)]
    n = max(len(sub), 1)
    in_india = (sub["country"].astype(str).str.lower() == "india").sum()
    pref_hub = sub["location"].astype(str).str.lower().str.contains("pune|noida").sum()
    product = (sub["product_company_score"].astype(float) >= 0.40).sum()
    band = sub["years_of_experience"].astype(float).between(5.0, 9.0).sum()

    print("=" * 64)
    print("  OFFLINE RANKING EVAL — Senior AI Engineer JD (silver labels)")
    print("=" * 64)
    print(f"  submission         : {args.submission.name}  ({len(ranked_ids)} rows)")
    print(f"  eligible pool      : {len(eligible):,} (honeypots excluded)")
    print(f"  pool label 3/2/1/0 : {pool_hist[3]} / {pool_hist[2]} / {pool_hist[1]} / {pool_hist[0]}")
    print("-" * 64)
    print(f"  NDCG@10            : {ndcg_at_k(ranked_labels, all_labels, 10):.4f}")
    print(f"  NDCG@100           : {ndcg_at_k(ranked_labels, all_labels, 100):.4f}")
    print(f"  MRR (rel>={REL_THRESHOLD})         : {mrr(ranked_labels):.4f}")
    print(f"  MAP@100 (rel>={REL_THRESHOLD})     : {map_at_k(ranked_labels, 100):.4f}")
    print(f"  mean rel @10       : {sum(ranked_labels[:10]) / 10:.3f}")
    print(f"  mean rel @100      : {sum(ranked_labels) / n:.3f}")
    print("-" * 64)
    print(f"  top10  label 3/2/1/0: {top10_hist[3]} / {top10_hist[2]} / {top10_hist[1]} / {top10_hist[0]}")
    print(f"  top100 label 3/2/1/0: {top100_hist[3]} / {top100_hist[2]} / {top100_hist[1]} / {top100_hist[0]}")
    print("-" * 64)
    print(f"  top100 in India     : {in_india}/{n}  ({100*in_india/n:.0f}%)")
    print(f"  top100 Pune/Noida   : {pref_hub}/{n}  ({100*pref_hub/n:.0f}%)")
    print(f"  top100 product co.  : {product}/{n}  ({100*product/n:.0f}%)")
    print(f"  top100 in 5-9 band  : {band}/{n}  ({100*band/n:.0f}%)")
    print("=" * 64)


if __name__ == "__main__":
    main()
