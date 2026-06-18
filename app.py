from __future__ import annotations

import csv
import io
import json
from pathlib import Path

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


def load_candidate_pool(uploaded) -> tuple[list[dict], str]:
    if uploaded is not None:
        try:
            data = json.loads(uploaded.getvalue().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"Invalid JSON upload: {exc}") from exc
        if isinstance(data, dict):
            data = data.get("candidates") or data.get("data") or [data]
        if not isinstance(data, list):
            raise ValueError("Upload must be a JSON array of candidate objects.")
        return data[:100], "uploaded JSON"
    sample_path = ROOT / "India_runs_data_and_ai_challenge" / "sample_candidates.json"
    if sample_path.exists():
        return json.loads(sample_path.read_text(encoding="utf-8"))[:100], "bundled sample_candidates.json"
    return [], "none"


def count_rankable(pool: list[dict], spec: dict) -> tuple[int, int]:
    honeypots = 0
    for candidate in pool:
        if extract_features(candidate, spec).get("honeypot_flag"):
            honeypots += 1
    return len(pool) - honeypots, honeypots


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
    help="Re-upload the bundled sample_candidates.json or any subset whose IDs exist in indices_sample/.",
)

try:
    pool, source_label = load_candidate_pool(uploaded)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

if not pool:
    st.warning("Upload a JSON array or bundle `sample_candidates.json` with the Space.")
    st.stop()

spec = load_role_spec(ROOT / "config" / "role_spec.yaml")
rankable, honeypots = count_rankable(pool, spec)

st.info(
    f"**Pool:** {len(pool)} profiles · **Honeypots excluded:** {honeypots} · "
    f"**Rankable max:** {rankable}"
    + (f" ({len(pool)} − {honeypots} honeypots = {rankable})" if honeypots else "")
)
st.caption(f"Source: {source_label}")

if rankable == 0:
    st.error(f"No rankable candidates after removing {honeypots} honeypot(s).")
    st.stop()

default_rows = min(20, rankable)
limit = st.slider(
    "Rows to rank",
    5,
    rankable,
    default_rows,
    help=f"Maximum {rankable}: {len(pool)} in pool minus {honeypots} honeypot(s).",
)
if limit > rankable:
    st.warning(f"Requested {limit} rows but only **{rankable}** rankable candidates ({honeypots} honeypots removed).")

try:
    with st.spinner("Running production ranking pipeline..."):
        ranked, meta = rank_sandbox(pool, top_n=limit, spec=spec, root=ROOT)
except ValueError as exc:
    st.error(
        f"{exc}\n\nFor hybrid mode, uploaded `candidate_id` values must exist in `{indices_dir.name if indices_dir else 'indices_sample'}/`. "
        "Use the bundled sample file or a subset of those 50 IDs."
    )
    st.stop()
except RuntimeError as exc:
    st.error(str(exc))
    st.stop()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Pool size", len(pool))
c2.metric("Honeypots in pool", honeypots)
c3.metric("Rankable max", rankable)
c4.metric("Mode", meta.get("mode", "unknown"))
c5.metric("Returned", len(ranked))
audit_report = audit(ranked)
c6.metric("Honeypots in results", audit_report["honeypots"])

st.caption(
    f"{meta.get('engine', '')} · Index: `{meta.get('indices') or '—'}` · "
    f"Trap titles in results: {audit_report['trap_titles']}"
)
if len(ranked) < limit:
    st.caption(
        f"Showing **{len(ranked)}** rows (requested {limit}). "
        f"Only **{rankable}** candidates rankable after **{honeypots}** honeypot(s) removed."
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
            "reasoning": r["reasoning"],
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

with st.expander("Top-3 reasoning (recruiter view)"):
    for row in ranked[:3]:
        st.markdown(f"**#{row['rank']} · {row.get('current_title', 'Unknown')}**")
        st.write(row["reasoning"])
