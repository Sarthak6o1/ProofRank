from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import streamlit as st

from rank import audit, rank_sandbox, resolve_indices_dir
from src.load import load_role_spec

ROOT = Path(__file__).resolve().parent


def rows_to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["candidate_id", "rank", "score", "reasoning"])
    for row in rows:
        writer.writerow([row["candidate_id"], row["rank"], f"{row['score']:.4f}", row["reasoning"]])
    return buf.getvalue()


st.set_page_config(page_title="ProofRank Redrob Demo", layout="wide")
st.title("ProofRank Redrob Demo")
st.caption(
    "Sandbox uses the same hybrid ranker as production (`rank.py`): "
    "FAISS + dual BM25 + composite score + guards. "
    "Requires `indices_sample/` or `indices/`."
)

indices_dir = resolve_indices_dir(ROOT)
if indices_dir is not None:
    st.success(f"Production indexes loaded: `{indices_dir.name}/`")
else:
    st.warning(
        "No indexes found. Build sandbox indexes first:\n\n"
        "`powershell -File scripts/build_sandbox_index.ps1`\n\n"
        "Falling back to structured-only scoring until indexes exist."
    )

uploaded = st.file_uploader("Upload sample_candidates.json (<=100 candidates)", type=["json"])
if uploaded is not None:
    candidates = json.loads(uploaded.read().decode("utf-8"))
else:
    sample_path = ROOT / "India_runs_data_and_ai_challenge" / "sample_candidates.json"
    candidates = json.loads(sample_path.read_text(encoding="utf-8")) if sample_path.exists() else []

if candidates:
    pool = candidates[:100]
    limit = st.slider("Rows to rank", 5, min(100, len(pool)), min(20, len(pool)))
    spec = load_role_spec(ROOT / "config" / "role_spec.yaml")

    with st.spinner("Ranking with production pipeline..."):
        ranked, meta = rank_sandbox(pool, top_n=limit, spec=spec, root=ROOT)

    st.metric("Candidates loaded", len(pool))
    st.metric("Ranking mode", meta.get("mode", "unknown"))
    st.caption(meta.get("engine", ""))

    audit_report = audit(ranked)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Honeypots in results", audit_report["honeypots"])
    c2.metric("Trap titles", audit_report["trap_titles"])
    c3.metric("Keyword stuffers", audit_report["keyword_stuffers"])
    c4.metric("Consulting-only", audit_report["consulting_only"])

    st.dataframe(
        [
            {
                "rank": r["rank"],
                "candidate_id": r["candidate_id"],
                "title": r.get("current_title"),
                "score": r["score"],
                "career_evidence": round(float(r.get("career_evidence") or 0), 3),
                "retrieval_rrf": round(float(r.get("retrieval_rrf") or 0), 3),
                "reasoning": r["reasoning"],
            }
            for r in ranked
        ],
        use_container_width=True,
    )
    st.download_button("Download ranked CSV", rows_to_csv(ranked), file_name="sample_ranked.csv", mime="text/csv")
else:
    st.warning("No sample candidates found. Upload a JSON array to run the demo.")
