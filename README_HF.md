---
title: ProofRank Redrob Demo
emoji: 🔍
colorFrom: blue
colorTo: green
sdk: streamlit
sdk_version: "1.28.0"
app_file: app.py
pinned: false
---

# ProofRank Sandbox

Production-parity demo for the Redrob candidate ranking challenge.

**Same engine as `rank.py`:** FAISS + dual BM25 + RRF + composite score + guards.

## Setup (one-time, before deploying Space)

```bash
python scripts/build_index.py \
  --candidates ./India_runs_data_and_ai_challenge/sample_candidates.json \
  --out ./indices_sample
```

Commit `indices_sample/` to the Space repo (small, ~50 profiles).

## Usage

Upload `sample_candidates.json` or use the bundled 50-profile sample. Rankings use `rank_sandbox()` from `rank.py` — not a separate scoring path.
