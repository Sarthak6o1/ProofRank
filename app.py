from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import streamlit as st

from rank import audit, rank_sandbox, resolve_indices_dir
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

uploaded = st.file_uploader("Upload candidate JSON (array, ≤100 profiles)", type=["json"])
if uploaded is not None:
    candidates = json.loads(uploaded.read().decode("utf-8"))
else:
    sample_path = ROOT / "India_runs_data_and_ai_challenge" / "sample_candidates.json"
    candidates = json.loads(sample_path.read_text(encoding="utf-8")) if sample_path.exists() else []

if not candidates:
    st.warning("Upload a JSON array or bundle `sample_candidates.json` with the Space.")
    st.stop()

pool = candidates[:100]
limit = st.slider("Rows to rank", 5, min(100, len(pool)), min(20, len(pool)))
spec = load_role_spec(ROOT / "config" / "role_spec.yaml")

with st.spinner("Running production ranking pipeline..."):
    ranked, meta = rank_sandbox(pool, top_n=limit, spec=spec, root=ROOT)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Pool size", len(pool))
c2.metric("Mode", meta.get("mode", "unknown"))
c3.metric("Index bundle", meta.get("indices") or "—")
audit_report = audit(ranked)
c4.metric("Honeypots", audit_report["honeypots"])
c5.metric("Trap titles", audit_report["trap_titles"])

st.caption(meta.get("engine", ""))

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
