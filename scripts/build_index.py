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

from src.embed import DEFAULT_MODEL, Embedder
from src.features import attach_hash_counts, extract_features
from src.indices import build_bm25, save_faiss, save_pickle
from src.load import iter_candidates, load_role_spec
from src.narrative import career_text, full_text


def _progress(msg: str) -> None:
    print(f"[build_index] {msg}", flush=True)


def build_index(
    candidates_path: Path,
    out_dir: Path,
    spec_path: Path,
    batch_size: int = 128,
    embed_batch: int = 256,
    limit: int | None = None,
) -> dict:
    import faiss
    import pandas as pd

    t0 = time.time()
    spec = load_role_spec(spec_path)

    ids: list[str] = []
    career_texts: list[str] = []
    full_texts: list[str] = []
    feature_rows: list[dict] = []

    _progress(f"Pass 1/3: parsing {candidates_path}")
    for i, candidate in enumerate(iter_candidates(candidates_path)):
        if limit is not None and i >= limit:
            break
        ids.append(candidate["candidate_id"])
        career_texts.append(career_text(candidate) or " ")
        full_texts.append(full_text(candidate) or " ")
        feature_rows.append(extract_features(candidate, spec))
        if (i + 1) % 10000 == 0:
            _progress(f"  parsed {i + 1:,} candidates")

    n = len(ids)
    if n == 0:
        raise RuntimeError(f"No candidates loaded from {candidates_path}")

    _progress(f"Pass 2/3: embedding {n:,} career + full narratives (batch={embed_batch})")
    embedder = Embedder()
    career_vecs = embedder.encode(career_texts, batch_size=embed_batch)
    full_vecs = embedder.encode(full_texts, batch_size=embed_batch)

    _progress("Pass 3/3: building FAISS + BM25 + features.parquet + JD query vector")
    dim = career_vecs.shape[1]
    career_index = faiss.IndexFlatIP(dim)
    career_index.add(career_vecs)
    full_index = faiss.IndexFlatIP(dim)
    full_index.add(full_vecs)

    bm25_full, tokenized_full = build_bm25(full_texts)
    bm25_career, tokenized_career = build_bm25(career_texts)
    del full_texts

    features = attach_hash_counts(pd.DataFrame(feature_rows))
    jd_query = str(spec.get("jd_query") or "").strip()
    jd_vec = embedder.encode_one(jd_query) if jd_query else np.zeros(dim, dtype="float32")

    out_dir.mkdir(parents=True, exist_ok=True)
    save_faiss(career_index, out_dir / "faiss_career.index")
    save_faiss(full_index, out_dir / "faiss_full.index")
    save_pickle(bm25_full, out_dir / "bm25.pkl")
    save_pickle(tokenized_full, out_dir / "bm25_tokens.pkl")
    save_pickle(bm25_career, out_dir / "bm25_career.pkl")
    save_pickle(tokenized_career, out_dir / "bm25_career_tokens.pkl")
    np.save(out_dir / "candidate_ids.npy", np.array(ids, dtype=object))
    np.save(out_dir / "jd_query_vec.npy", jd_vec)
    features.to_parquet(out_dir / "features.parquet", index=False)
    del career_texts

    elapsed = round(time.time() - t0, 1)
    meta = {
        "candidates": n,
        "embedding_dim": int(dim),
        "embedding_model": DEFAULT_MODEL,
        "elapsed_seconds": elapsed,
        "honeypot_flag": int(features["honeypot_flag"].sum()),
        "stuffer_flag": int(features["stuffer_flag"].sum()),
        "trap_titles": int((features["title_tier"] == "trap").sum()),
        "strong_titles": int((features["title_tier"] == "strong").sum()),
        "career_evidence_ge_0_5": int((features["career_evidence"] >= 0.5).sum()),
        "duplicate_career_hashes_ge_8": int((features["career_hash_count"] >= 8).sum()),
        "artifacts": [
            "faiss_career.index",
            "faiss_full.index",
            "bm25.pkl",
            "bm25_tokens.pkl",
            "bm25_career.pkl",
            "bm25_career_tokens.pkl",
            "candidate_ids.npy",
            "jd_query_vec.npy",
            "features.parquet",
        ],
    }
    with open(out_dir / "build_metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    _progress(f"Done in {elapsed}s — {n:,} candidates -> {out_dir}")
    _progress(f"  honeypots: {meta['honeypot_flag']}")
    _progress(f"  keyword stuffers: {meta['stuffer_flag']}")
    _progress(f"  trap titles: {meta['trap_titles']}")
    _progress(f"  strong ML/AI titles: {meta['strong_titles']}")
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description="Build offline FAISS/BM25/features cache.")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "indices")
    parser.add_argument("--spec", type=Path, default=ROOT / "config" / "role_spec.yaml")
    parser.add_argument("--embed-batch", type=int, default=256)
    parser.add_argument("--limit", type=int, default=None, help="Debug: only index first N candidates")
    args = parser.parse_args()
    build_index(args.candidates, args.out, args.spec, embed_batch=args.embed_batch, limit=args.limit)


if __name__ == "__main__":
    main()
