from __future__ import annotations

import numpy as np

from .indices import tokenize


def rrf_fuse(rank_lists: list[list[int]], k: int = 60) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranks in rank_lists:
        for pos, idx in enumerate(ranks):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + pos + 1)
    if not scores:
        return {}
    mx = max(scores.values())
    return {idx: score / mx for idx, score in scores.items()}


def hybrid_retrieve(
    career_index,
    full_index,
    bm25_full,
    query_vec,
    query_text: str,
    top_k: int,
    rrf_k: int,
    exclude_indices: set[int] | None = None,
    bm25_career=None,
) -> dict[int, float]:
    exclude_indices = exclude_indices or set()
    q = np.asarray(query_vec, dtype="float32").reshape(1, -1)

    dense_lists: list[list[int]] = []
    for index, limit in ((career_index, top_k * 2), (full_index, max(top_k, top_k // 2))):
        _, ids = index.search(q, min(limit, index.ntotal))
        dense_lists.append([int(i) for i in ids[0] if int(i) >= 0 and int(i) not in exclude_indices][:top_k])

    bm25_scores = bm25_full.get_scores(tokenize(query_text))
    order = np.argsort(-bm25_scores)
    sparse_full = [int(i) for i in order if int(i) not in exclude_indices][:top_k]

    rank_lists: list[list[int]] = [*dense_lists, sparse_full]
    if bm25_career is not None:
        career_scores = bm25_career.get_scores(tokenize(query_text))
        order_career = np.argsort(-career_scores)
        sparse_career = [int(i) for i in order_career if int(i) not in exclude_indices][:top_k]
        rank_lists.append(sparse_career)

    fused = rrf_fuse(rank_lists, k=rrf_k)
    return dict(sorted(fused.items(), key=lambda x: -x[1])[:top_k])


def hybrid_retrieve_subset(
    career_index,
    full_index,
    bm25_full,
    query_vec,
    query_text: str,
    candidate_indices: list[int],
    rrf_k: int,
    bm25_career=None,
) -> dict[int, float]:
    """Same RRF fusion as hybrid_retrieve, restricted to a candidate index subset."""
    if not candidate_indices:
        return {}

    ci = np.asarray(candidate_indices, dtype=np.int64)
    q = np.asarray(query_vec, dtype="float32").reshape(-1)

    career_vecs = np.vstack([career_index.reconstruct(int(i)) for i in ci]).astype("float32")
    full_vecs = np.vstack([full_index.reconstruct(int(i)) for i in ci]).astype("float32")
    career_dense_order = ci[np.argsort(-(career_vecs @ q))]
    full_dense_order = ci[np.argsort(-(full_vecs @ q))]

    bm25_full_scores = bm25_full.get_scores(tokenize(query_text))
    sparse_full_order = ci[np.argsort(-bm25_full_scores[ci])]

    rank_lists: list[list[int]] = [
        [int(i) for i in career_dense_order],
        [int(i) for i in full_dense_order],
        [int(i) for i in sparse_full_order],
    ]
    if bm25_career is not None:
        bm25_career_scores = bm25_career.get_scores(tokenize(query_text))
        sparse_career_order = ci[np.argsort(-bm25_career_scores[ci])]
        rank_lists.append([int(i) for i in sparse_career_order])

    return rrf_fuse(rank_lists, k=rrf_k)
