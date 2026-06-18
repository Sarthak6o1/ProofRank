"""
Extract a small indices_sample/ bundle from production indices/ + sample_candidates.json.

Avoids re-embedding: reuses FAISS vectors via reconstruct, subsets features.parquet,
rebuilds BM25 token indexes from narratives only. Intended for HuggingFace Spaces.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.embed import DEFAULT_MODEL
from src.indices import build_bm25, load_faiss, save_faiss, save_pickle
from src.load import iter_candidates, load_role_spec
from src.narrative import career_text, full_text


def _progress(msg: str) -> None:
    print(f"[extract_sandbox] {msg}", flush=True)


def _subset_faiss(source_index, source_positions: list[int]):
    import faiss

    dim = source_index.d
    out = faiss.IndexFlatIP(dim)
    vectors = np.vstack([source_index.reconstruct(int(pos)) for pos in source_positions]).astype("float32")
    out.add(vectors)
    return out


def extract_sandbox_indices(
    sample_path: Path,
    source_dir: Path,
    out_dir: Path,
    spec_path: Path,
) -> dict:
    import pandas as pd

    t0 = time.time()
    spec = load_role_spec(spec_path)
    candidates = list(iter_candidates(sample_path))
    if not candidates:
        raise RuntimeError(f"No candidates in {sample_path}")

    sample_ids = [str(c["candidate_id"]) for c in candidates if c.get("candidate_id")]
    if len(sample_ids) != len(candidates):
        raise RuntimeError("Every sample candidate must include candidate_id.")

    source_ids = np.load(source_dir / "candidate_ids.npy", allow_pickle=True)
    id_to_pos = {str(cid): i for i, cid in enumerate(source_ids)}
    missing = [cid for cid in sample_ids if cid not in id_to_pos]
    if missing:
        raise RuntimeError(
            f"{len(missing)} sample IDs missing from production indices (first: {missing[:3]}). "
            "Rebuild production indices from the organizer candidates.jsonl first."
        )

    positions = [id_to_pos[cid] for cid in sample_ids]
    _progress(f"Extracting {len(sample_ids)} profiles from {source_dir.name}/")

    career_index = load_faiss(source_dir / "faiss_career.index")
    full_index = load_faiss(source_dir / "faiss_full.index")
    career_texts = [career_text(c) or " " for c in candidates]
    full_texts = [full_text(c) or " " for c in candidates]

    bm25_full, tokenized_full = build_bm25(full_texts)
    bm25_career, tokenized_career = build_bm25(career_texts)

    features = pd.read_parquet(source_dir / "features.parquet")
    subset_features = features.loc[features["candidate_id"].astype(str).isin(sample_ids)].copy()
    subset_features["candidate_id"] = subset_features["candidate_id"].astype(str)
    subset_features = subset_features.set_index("candidate_id").loc[sample_ids].reset_index()

    out_dir.mkdir(parents=True, exist_ok=True)
    save_faiss(_subset_faiss(career_index, positions), out_dir / "faiss_career.index")
    save_faiss(_subset_faiss(full_index, positions), out_dir / "faiss_full.index")
    save_pickle(bm25_full, out_dir / "bm25.pkl")
    save_pickle(tokenized_full, out_dir / "bm25_tokens.pkl")
    save_pickle(bm25_career, out_dir / "bm25_career.pkl")
    save_pickle(tokenized_career, out_dir / "bm25_career_tokens.pkl")
    np.save(out_dir / "candidate_ids.npy", np.array(sample_ids, dtype=object))
    np.save(out_dir / "jd_query_vec.npy", np.load(source_dir / "jd_query_vec.npy"))
    subset_features.to_parquet(out_dir / "features.parquet", index=False)

    elapsed = round(time.time() - t0, 1)
    meta = {
        "source_indices": str(source_dir),
        "sample_file": str(sample_path),
        "candidates": len(sample_ids),
        "embedding_model": DEFAULT_MODEL,
        "elapsed_seconds": elapsed,
        "method": "faiss_reconstruct_subset",
        "honeypot_flag": int(subset_features["honeypot_flag"].sum()),
        "stuffer_flag": int(subset_features["stuffer_flag"].sum()),
        "trap_titles": int((subset_features["title_tier"] == "trap").sum()),
    }
    with open(out_dir / "build_metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    _progress(f"Done in {elapsed}s -> {out_dir}")
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract indices_sample/ from production indices/.")
    parser.add_argument(
        "--sample",
        type=Path,
        default=ROOT / "India_runs_data_and_ai_challenge" / "sample_candidates.json",
    )
    parser.add_argument("--source", type=Path, default=ROOT / "indices")
    parser.add_argument("--out", type=Path, default=ROOT / "indices_sample")
    parser.add_argument("--spec", type=Path, default=ROOT / "config" / "role_spec.yaml")
    args = parser.parse_args()
    extract_sandbox_indices(args.sample, args.source, args.out, args.spec)


if __name__ == "__main__":
    main()
