from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import numpy as np
import streamlit as st

from rank import audit, rank_sandbox, resolve_indices_dir
from src.features import extract_features
from src.load import load_role_spec

ROOT = Path(__file__).resolve().parent

PIPELINE = """
**Offline (once)** — `build_index.py` or `extract_sandbox_indices.py`
```
candidates → narratives → MiniLM embeddings → FAISS (career + full)
          → BM25 (career + full) → features.parquet → jd_query_vec
```

**Online (sandbox + production)** — `rank_sandbox()` / `rank.py`
```
JD query → hybrid retrieve (2× FAISS + 2× BM25, RRF fusion)
        → composite score (career evidence, title tier, skills, behavior)
        → honeypot drop → rank-band guards → top-N + reasoning
```
"""


def rows_to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["candidate_id", "rank", "score", "reasoning"])
    for row in rows:
        writer.writerow([row["candidate_id"], row["rank"], f"{row['score']:.4f}", row["reasoning"]])
    return buf.getvalue()


def load_candidate_pool(uploaded) -> tuple[list[dict], str, str | None]:
    """Return pool, source label, and uploaded filename (if any)."""
    if uploaded is not None:
        try:
            raw = uploaded.getvalue()
            if not raw:
                uploaded.seek(0)
                raw = uploaded.read()
            data = json.loads(raw.decode("utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"Invalid JSON upload: {exc}") from exc
        except AttributeError:
            # Older Streamlit UploadedFile without seek
            data = json.loads(uploaded.read().decode("utf-8-sig"))
        if isinstance(data, dict):
            data = data.get("candidates") or data.get("data") or [data]
        if not isinstance(data, list):
            raise ValueError("Upload must be a JSON array of candidate objects.")
        if not data:
            raise ValueError("Uploaded JSON array is empty.")
        missing_id = [i for i, c in enumerate(data[:5]) if not c.get("candidate_id")]
        if missing_id:
            raise ValueError("Each candidate object must include candidate_id.")
        name = getattr(uploaded, "name", None)
        return data[:100], "uploaded JSON", name
    sample_path = ROOT / "India_runs_data_and_ai_challenge" / "sample_candidates.json"
    if sample_path.exists():
        return (
            json.loads(sample_path.read_text(encoding="utf-8"))[:100],
            "bundled sample_candidates.json",
            None,
        )
    return [], "none", None


def count_rankable(pool: list[dict], spec: dict) -> tuple[int, int]:
    honeypots = sum(1 for c in pool if extract_features(c, spec).get("honeypot_flag"))
    return len(pool) - honeypots, honeypots


def ids_in_index(indices_dir: Path | None, pool: list[dict]) -> tuple[int, int]:
    if indices_dir is None:
        return 0, len(pool)
    ids = {str(x) for x in np.load(indices_dir / "candidate_ids.npy", allow_pickle=True)}
    pool_ids = {str(c.get("candidate_id")) for c in pool if c.get("candidate_id")}
    matched = len(pool_ids & ids)
    return matched, len(pool_ids)


st.set_page_config(page_title="ProofRank — Redrob Sandbox", page_icon="🔍", layout="wide")

with st.sidebar:
    st.header("ProofRank")
    st.caption("Redrob Intelligent Candidate Discovery & Ranking")
    st.markdown(PIPELINE)
    st.divider()
    st.markdown(
        "**Production parity:** this Space calls `rank_sandbox()` from `rank.py` — "
        "not a separate demo scorer."
    )
    st.info(
        "Bundled demo = organizer's first **50** profiles (only 1 strong ML fit). "
        "Full 100K ranking is on GitHub via `rank.py` + `indices/`."
    )

st.title("ProofRank Sandbox")
st.caption("Senior AI Engineer JD · hybrid retrieval + career-proof scoring · CPU-only")

indices_dir = resolve_indices_dir(ROOT)
if indices_dir is not None:
    st.success(f"Indexes loaded: `{indices_dir.name}/` — full hybrid ranker active")
else:
    st.error(
        "No indexes found. Build `indices_sample/` before deploying:\n\n"
        "`powershell -File scripts/build_sandbox_index.ps1`"
    )

uploaded = st.file_uploader(
    "Upload candidate JSON (array, ≤100 profiles)",
    type=["json"],
    help="Upload sample_candidates.json (or a subset). Must be a JSON array; each item needs candidate_id.",
)

use_bundled = st.checkbox(
    "Use bundled sample_candidates.json (ignore upload)",
    value=False,
    help="Check this to rank the default 50-profile sample instead of an uploaded file.",
)
if use_bundled:
    uploaded = None

try:
    pool, source_label, upload_name = load_candidate_pool(uploaded)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

if not pool:
    st.warning("Upload a JSON array or bundle `sample_candidates.json` with the Space.")
    st.stop()

spec = load_role_spec(ROOT / "config" / "role_spec.yaml")
rankable, honeypots = count_rankable(pool, spec)
matched, total_ids = ids_in_index(indices_dir, pool)

if upload_name:
    st.success(f"Loaded **{len(pool)}** profiles from upload: `{upload_name}`")
else:
    st.caption(f"Using bundled **{len(pool)}** profiles from `sample_candidates.json`")

# Prominent pool breakdown — same logic for default load and upload
highlight = st.container()
with highlight:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Pool size", len(pool))
    m2.metric("Honeypots excluded", honeypots, help="Trap profiles removed before ranking")
    m3.metric("Rankable max", rankable, help=f"{len(pool)} − {honeypots} honeypots")
    m4.metric("IDs in index", f"{matched}/{total_ids}", help="Hybrid mode needs IDs in indices_sample/")

if honeypots:
    st.warning(
        f"**{honeypots} honeypot(s) removed** from this pool. "
        f"Slider maximum is **{rankable}** ({len(pool)} − {honeypots} = {rankable}), not {len(pool)}."
    )
elif rankable < len(pool):
    st.warning(f"Only **{rankable}** of **{len(pool)}** profiles are rankable after filtering.")

if indices_dir and matched < total_ids:
    st.warning(
        f"**{total_ids - matched} uploaded ID(s)** are not in `{indices_dir.name}/`. "
        "Those profiles use structured fallback scoring (no FAISS/BM25). "
        "For full hybrid parity, upload only IDs from the bundled 50-sample set."
    )

if rankable == 0:
    st.error(f"No rankable candidates after removing {honeypots} honeypot(s).")
    st.stop()

default_rows = min(20, rankable)
# Reset slider when pool source/size changes (fixes upload after bundled session)
slider_key = f"rank_rows_{upload_name or 'bundled'}_{len(pool)}_{rankable}"
limit = st.slider(
    "Rows to rank",
    min_value=5,
    max_value=rankable,
    value=min(default_rows, rankable),
    help=f"Max {rankable}: {len(pool)} pool − {honeypots} honeypots.",
    key=slider_key,
)

try:
    with st.spinner("Running production ranking pipeline..."):
        ranked, meta = rank_sandbox(pool, top_n=limit, spec=spec, root=ROOT)
except ValueError as exc:
    st.error(
        f"{exc}\n\nFor hybrid mode, uploaded `candidate_id` values must exist in "
        f"`{indices_dir.name if indices_dir else 'indices_sample'}/`."
    )
    st.stop()
except RuntimeError as exc:
    st.error(str(exc))
    st.stop()

audit_report = audit(ranked)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Returned rows", len(ranked))
c2.metric("Mode", meta.get("mode", "unknown"))
c3.metric("Honeypots in results", audit_report["honeypots"])
c4.metric("Trap titles in results", audit_report["trap_titles"])

st.caption(
    f"{meta.get('engine', '')} · Index: `{meta.get('indices') or '—'}` · Source: {source_label}"
)
if len(ranked) < limit:
    st.info(
        f"Returned **{len(ranked)}** rows (requested {limit}). "
        f"Cap is **{rankable}** rankable = **{len(pool)}** pool − **{honeypots}** honeypots."
    )

st.dataframe(
    [
        {
            "rank": r["rank"],
            "candidate_id": r["candidate_id"],
            "title": r.get("current_title"),
            "score": round(float(r["score"]), 4),
            "career_evidence": round(float(r.get("career_evidence") or 0), 3),
            "retrieval_rrf": round(float(r.get("retrieval_rrf") or 0), 3),
            "behavioral_mult": round(float(r.get("behavioral_mult") or 0), 3),
        }
        for r in ranked
    ],
    use_container_width=True,
    hide_index=True,
)

st.download_button(
    "Download ranked CSV",
    rows_to_csv(ranked),
    file_name="sample_ranked.csv",
    mime="text/csv",
)

st.subheader("Full reasoning")
st.caption("Recruiter-style justification for each ranked candidate (complete text, not table-truncated).")

for row in ranked:
    title = row.get("current_title") or "Unknown"
    company = row.get("current_company") or ""
    label = f"#{row['rank']} · {title}"
    if company:
        label += f" @ {company}"
    with st.expander(label, expanded=row["rank"] <= 3):
        st.markdown(row["reasoning"])
