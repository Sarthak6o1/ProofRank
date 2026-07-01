from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.explain import build_reasoning
from src.features import extract_features
from src.load import iter_candidates, load_role_spec
from src.rank_enrich import eligible_for_rank_band, enrich_row
from src.score import final_score, monotonic_submission_scores


def indices_ready(indices_dir: Path) -> bool:
    required = [
        "faiss_career.index",
        "faiss_full.index",
        "bm25.pkl",
        "candidate_ids.npy",
        "features.parquet",
    ]
    return all((indices_dir / name).exists() for name in required)


def _apply_duplicate_penalty(rows: list[dict]) -> None:
    for row in rows:
        if int(row.get("career_hash_count") or 1) >= 8 and float(row.get("career_evidence") or 0) < 0.55:
            row["anti_pattern_penalty"] = min(1.0, float(row.get("anti_pattern_penalty") or 0) + 0.12)


def _eligible_for_top50(row: dict) -> bool:
    if row.get("stuffer_flag") and float(row.get("career_evidence") or 0) < 0.55:
        return False
    if row.get("title_tier") == "trap":
        return False
    return True


def _retrieval_query(spec: dict) -> str:
    return str(spec.get("retrieval_query") or spec.get("jd_query") or "")


def _try_select(row: dict, selected: list[dict], seen: set[str], spec: dict) -> bool:
    cid = str(row.get("candidate_id"))
    if cid in seen:
        return False
    next_rank = len(selected) + 1
    if not eligible_for_rank_band(row, next_rank, spec):
        return False
    selected.append(row)
    seen.add(cid)
    return True


def rank_rows(rows: list[dict], spec: dict, top_n: int, *, allow_partial: bool = False) -> list[dict]:
    if not rows:
        raise RuntimeError("No candidates available after filtering.")

    _apply_duplicate_penalty(rows)
    for row in rows:
        enrich_row(row, spec)
        row["raw_score"] = final_score(row, spec)

    rows = [row for row in rows if not row.get("honeypot_flag")]
    rows.sort(
        key=lambda r: (
            -float(r.get("raw_score") or 0),
            -float(r.get("career_evidence") or 0),
            str(r.get("candidate_id") or ""),
        ),
    )

    non_trap = [r for r in rows if r.get("title_tier") != "trap"]
    if len(non_trap) >= top_n:
        rows = non_trap

    guard = spec.get("top10_guard") or {}
    min_career = float(guard.get("min_career_evidence", 0.50))
    min_title = float(guard.get("min_title_tier_score", 0.65))
    guarded = [
        r
        for r in rows
        if float(r.get("career_evidence") or 0) >= min_career
        and float(r.get("title_tier_score") or 0) >= min_title
        and r.get("title_tier") != "trap"
    ]

    selected: list[dict] = []
    seen: set[str] = set()
    for row in guarded:
        if len(selected) >= 10:
            break
        _try_select(row, selected, seen, spec)

    fill_pool = [r for r in rows if _eligible_for_top50(r)] if len([r for r in rows if _eligible_for_top50(r)]) >= top_n else rows
    for row in fill_pool:
        if len(selected) >= top_n:
            break
        _try_select(row, selected, seen, spec)

    if len(selected) < top_n:
        for row in rows:
            if len(selected) >= top_n:
                break
            _try_select(row, selected, seen, spec)

    if len(selected) < top_n:
        for row in rows:
            cid = str(row.get("candidate_id"))
            if cid not in seen:
                selected.append(row)
                seen.add(cid)
            if len(selected) >= top_n:
                break

    if len(selected) < top_n:
        if not allow_partial:
            raise RuntimeError(f"Only {len(selected)} eligible candidates found; expected {top_n}.")
        top_n = len(selected)

    if top_n == 0:
        raise RuntimeError("No eligible candidates found after filtering.")

    selected = selected[:top_n]
    scores = monotonic_submission_scores([float(row.get("raw_score") or 0) for row in selected])
    for i, (row, score) in enumerate(zip(selected, scores), start=1):
        row["rank"] = i
        row["score"] = score
        row["reasoning"] = build_reasoning(row, i)
    return selected


def structured_rank_candidates(candidates: list[dict], spec: dict, top_n: int) -> list[dict]:
    """Structured-only scoring for an in-memory candidate list (sandbox uploads)."""
    rows: list[dict] = []
    for candidate in candidates:
        row = extract_features(candidate, spec)
        if row.get("honeypot_flag"):
            continue
        row["retrieval_rrf"] = min(
            1.0,
            float(row.get("career_evidence") or 0) + 0.10 * float(row.get("title_tier_score") or 0),
        )
        rows.append(row)
    return rank_rows(rows, spec, top_n, allow_partial=True)


def resolve_indices_dir(root: Path | None = None) -> Path | None:
    """Prefer sandbox sample indexes, then full production indexes."""
    base = root or ROOT
    for name in ("indices_sample", "indices"):
        path = base / name
        if indices_ready(path):
            return path
    return None


def cached_rank_subset(indices_dir: Path, spec: dict, top_n: int, candidate_ids: set[str]) -> list[dict]:
    """Production hybrid ranker restricted to a candidate ID allowlist (sandbox/demo)."""
    import numpy as np
    import pandas as pd

    from src.indices import load_faiss, load_pickle
    from src.retrieve import hybrid_retrieve_subset

    ids = np.load(indices_dir / "candidate_ids.npy", allow_pickle=True)
    id_to_idx = {str(cid): i for i, cid in enumerate(ids)}
    missing = sorted(candidate_ids - set(id_to_idx))
    if missing:
        raise ValueError(f"Candidate IDs not found in {indices_dir.name}: {missing[:5]}")

    subset_indices = [id_to_idx[cid] for cid in candidate_ids]
    features = pd.read_parquet(indices_dir / "features.parquet")
    career_index = load_faiss(indices_dir / "faiss_career.index")
    full_index = load_faiss(indices_dir / "faiss_full.index")
    bm25 = load_pickle(indices_dir / "bm25.pkl")
    bm25_career = load_pickle(indices_dir / "bm25_career.pkl") if (indices_dir / "bm25_career.pkl").exists() else None

    rrf_k = int((spec.get("retrieval") or {}).get("rrf_k", 60))
    query = _retrieval_query(spec)
    query_vec = _load_query_vec(indices_dir, spec)
    retrieved = hybrid_retrieve_subset(
        career_index,
        full_index,
        bm25,
        query_vec,
        query,
        subset_indices,
        rrf_k=rrf_k,
        bm25_career=bm25_career,
    )

    feat_by_id = features.set_index("candidate_id", drop=False)
    rows: list[dict] = []
    for idx, retrieval_score in retrieved.items():
        cid = str(ids[idx])
        if cid not in candidate_ids:
            continue
        row_obj = feat_by_id.loc[cid]
        if hasattr(row_obj, "iloc") and not isinstance(row_obj, pd.Series):
            row_obj = row_obj.iloc[0]
        row = row_obj.to_dict()
        row["retrieval_rrf"] = float(retrieval_score)
        rows.append(row)

    return rank_rows(rows, spec, top_n, allow_partial=True)


def rank_sandbox(candidates: list[dict], top_n: int, spec: dict | None = None, root: Path | None = None) -> tuple[list[dict], dict]:
    """
    Rank a sandbox candidate list using the same production path when indexes exist.
    Uses indices_sample/ (demo) or indices/ (100K) with ID allowlist filtering.
    """
    import numpy as np

    base = root or ROOT
    spec = spec or load_role_spec(base / "config" / "role_spec.yaml")
    allowlist = {str(c["candidate_id"]) for c in candidates if c.get("candidate_id")}
    if not allowlist:
        raise RuntimeError("No candidate_id values found in sandbox input.")

    top_n = min(top_n, len(allowlist))
    indices_dir = resolve_indices_dir(base)
    if indices_dir is not None:
        ids_in_index = {str(cid) for cid in np.load(indices_dir / "candidate_ids.npy", allow_pickle=True)}
        matched_ids = allowlist & ids_in_index
        if matched_ids == allowlist:
            rows = cached_rank_subset(indices_dir, spec, top_n, allowlist)
            return rows, {
                "mode": "cached_hybrid",
                "indices": indices_dir.name,
                "engine": "same as rank.py (FAISS + dual BM25 + composite score)",
            }
        if matched_ids:
            rows = cached_rank_subset(indices_dir, spec, top_n, matched_ids)
            return rows, {
                "mode": "cached_hybrid_partial",
                "indices": indices_dir.name,
                "engine": (
                    f"hybrid rank on {len(matched_ids)}/{len(allowlist)} IDs in {indices_dir.name}/; "
                    "upload only IDs from the bundled sample for full parity"
                ),
            }

    rows = structured_rank_candidates(candidates, spec, top_n)
    return rows, {
        "mode": "structured_fallback",
        "indices": None,
        "engine": "features only — build indices_sample/ or indices/ for production parity",
    }


def structured_rank(candidates_path: Path, spec: dict, top_n: int) -> list[dict]:
    """Dependency-light fallback: scores all profiles without FAISS/BM25."""
    rows: list[dict] = []
    for candidate in iter_candidates(candidates_path):
        row = extract_features(candidate, spec)
        if row.get("honeypot_flag"):
            continue
        row["retrieval_rrf"] = min(1.0, float(row.get("career_evidence") or 0) + 0.10 * float(row.get("title_tier_score") or 0))
        rows.append(row)
    return rank_rows(rows, spec, top_n)


def _load_query_vec(indices_dir: Path, spec: dict):
    import numpy as np

    jd_path = indices_dir / "jd_query_vec.npy"
    if jd_path.exists():
        return np.load(jd_path)
    from src.embed import Embedder

    print("Warning: jd_query_vec.npy missing; embedding JD at rank time (needs local model cache).")
    return Embedder().encode_one(str(spec.get("jd_query") or ""))


def cached_rank(indices_dir: Path, spec: dict, top_n: int) -> list[dict]:
    import numpy as np
    import pandas as pd

    from src.indices import load_faiss, load_pickle
    from src.retrieve import hybrid_retrieve

    ids = np.load(indices_dir / "candidate_ids.npy", allow_pickle=True)
    features = pd.read_parquet(indices_dir / "features.parquet")
    career_index = load_faiss(indices_dir / "faiss_career.index")
    full_index = load_faiss(indices_dir / "faiss_full.index")
    bm25 = load_pickle(indices_dir / "bm25.pkl")
    bm25_career = load_pickle(indices_dir / "bm25_career.pkl") if (indices_dir / "bm25_career.pkl").exists() else None

    top_k = int((spec.get("retrieval") or {}).get("top_k", 3000))
    rrf_k = int((spec.get("retrieval") or {}).get("rrf_k", 60))
    honeypot_ids = set(features.loc[features["honeypot_flag"], "candidate_id"].astype(str))
    exclude_indices = {i for i, cid in enumerate(ids) if str(cid) in honeypot_ids}

    query = _retrieval_query(spec)
    query_vec = _load_query_vec(indices_dir, spec)
    retrieved = hybrid_retrieve(
        career_index,
        full_index,
        bm25,
        query_vec,
        query,
        top_k=top_k,
        rrf_k=rrf_k,
        exclude_indices=exclude_indices,
        bm25_career=bm25_career,
    )

    feat_by_id = features.set_index("candidate_id", drop=False)
    rows: list[dict] = []
    for idx, retrieval_score in retrieved.items():
        cid = str(ids[idx])
        if cid in honeypot_ids or cid not in feat_by_id.index:
            continue
        row_obj = feat_by_id.loc[cid]
        if hasattr(row_obj, "iloc") and not isinstance(row_obj, pd.Series):
            row_obj = row_obj.iloc[0]
        row = row_obj.to_dict()
        row["retrieval_rrf"] = float(retrieval_score)
        rows.append(row)

    safety_n = int((spec.get("retrieval") or {}).get("safety_pool", 350))
    safety_guard = spec.get("safety_pool_guard") or {}
    min_career = float(safety_guard.get("min_career_evidence", 0.45))
    min_title = float(safety_guard.get("min_title_tier_score", 0.65))
    safety = features[
        (~features["honeypot_flag"])
        & (features["career_evidence"] >= min_career)
        & (features["title_tier_score"] >= min_title)
        & (features["title_tier"] != "trap")
    ].nlargest(safety_n, ["career_evidence", "title_tier_score", "assessment_score"])
    seen = {str(row.get("candidate_id")) for row in rows}
    for _, srow in safety.iterrows():
        cid = str(srow["candidate_id"])
        if cid not in seen:
            row = srow.to_dict()
            row["retrieval_rrf"] = 0.25
            rows.append(row)
            seen.add(cid)

    return rank_rows(rows, spec, top_n)


def _write_submission_rows(writer: csv.writer, rows: list[dict]) -> None:
    writer.writerow(["candidate_id", "rank", "score", "reasoning"])
    for row in rows:
        writer.writerow(
            [
                row["candidate_id"],
                int(row["rank"]),
                f"{float(row['score']):.4f}",
                row["reasoning"],
            ]
        )


def write_submission(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        _write_submission_rows(csv.writer(f), rows)


def print_submission(rows: list[dict]) -> None:
    """Print submission CSV to stdout (same columns as submission.csv)."""
    _write_submission_rows(csv.writer(sys.stdout), rows)


def audit(rows: list[dict]) -> dict:
    return {
        "rows": len(rows),
        "honeypots": sum(1 for row in rows if row.get("honeypot_flag")),
        "trap_titles": sum(1 for row in rows if row.get("title_tier") == "trap"),
        "keyword_stuffers": sum(1 for row in rows if row.get("stuffer_flag")),
        "consulting_only": sum(1 for row in rows if row.get("consulting_only")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank Redrob candidates for Senior AI Engineer JD.")
    parser.add_argument("--candidates", type=Path, default=ROOT / "India_runs_data_and_ai_challenge" / "candidates.jsonl")
    parser.add_argument("--indices", type=Path, default=ROOT / "indices")
    parser.add_argument("--spec", type=Path, default=ROOT / "config" / "role_spec.yaml")
    parser.add_argument("--out", type=Path, default=ROOT / "submission.csv")
    parser.add_argument("--top", type=int, default=100)
    parser.add_argument("--structured-only", action="store_true", help="Ignore cached indexes and score from structured features only.")
    args = parser.parse_args()

    spec = load_role_spec(args.spec)
    if not args.candidates.exists() and not indices_ready(args.indices):
        raise FileNotFoundError(f"Candidate file not found: {args.candidates}")

    if not args.structured_only and indices_ready(args.indices):
        print("Ranking with cached FAISS + BM25 + structured scorer.")
        rows = cached_rank(args.indices, spec, args.top)
    else:
        print("Ranking with structured-only fallback. Build indices for best quality.")
        rows = structured_rank(args.candidates, spec, args.top)

    write_submission(rows, args.out)
    print(f"Wrote {len(rows)} rows to {args.out}")
    print("Audit:", audit(rows))
    print()
    print_submission(rows)


if __name__ == "__main__":
    main()
