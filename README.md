# ProofRank

[![Live Sandbox](https://img.shields.io/badge/Live_Sandbox-Open_Demo-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black)](https://huggingface.co/spaces/Sarthak080907/proofrank)
[![GitHub](https://img.shields.io/badge/GitHub-ProofRank-181717?style=for-the-badge&logo=github)](https://github.com/Sarthak6o1/ProofRank)
[![Redrob Challenge](https://img.shields.io/badge/Redrob-Senior_AI_Engineer_JD-6C63FF?style=for-the-badge)](job_description.md)

CPU-only hybrid ranker for the Redrob Senior AI Engineer JD: dual FAISS + dual BM25 retrieval, career-proof scoring, honeypot defenses, rule-based reasoning. **No LLM, no network at rank time.**

| | |
|---|---|
| **Live sandbox** | https://huggingface.co/spaces/Sarthak080907/proofrank |
| **GitHub** | https://github.com/Sarthak6o1/ProofRank |
| **Reproduce command** | `python rank.py --indices ./indices --out ./submission.csv` |

---

## Reproduce the submission (Stage 3)

Pre-built `indices/` ship with the repo (Git LFS). **No `candidates.jsonl`, no `build_index.py`, no GPU, no network during Step 6.**

**Prerequisites:** Git, [Git LFS](https://git-lfs.com/), Python **3.11+** on your PATH, ~2 GB free disk.  
Install Python from [python.org](https://www.python.org/downloads/) (Windows: check **Add Python to PATH**) before Step 5 if `python` is not recognized.

Clone and package install (Steps 1–5) take standard setup time depending on your network download speed.

**Step 6 — the `reproduce_command` — runs within the hackathon compute constraint:** ~10–20 s on CPU, no network, using pre-built `indices/` loaded locally.

### Step 1 — Enable Git LFS (once per machine)

```bash
git lfs install
```

### Step 2 — Clone the repo

```bash
git clone https://github.com/Sarthak6o1/ProofRank.git
```

If Git LFS was already enabled, index files usually download during clone.

### Step 3 — Enter the repo

```bash
cd ProofRank
```

### Step 4 — Fetch index files (only if Step 6 errors on missing indices)

```bash
git lfs pull
```

Skip this if `indices/faiss_full.index` is a large file (~100+ MB), not a tiny LFS pointer stub.  
LFS files: `*.index`, `*.pkl`. Normal Git files: `features.parquet`, `candidate_ids.npy`, `jd_query_vec.npy`.

### Step 5 — Install minimal Python packages

```bash
pip install -r requirements-rank.txt
```

Six packages only (`numpy`, `pandas`, `pyarrow`, `pyyaml`, `faiss-cpu`, `rank-bm25`).  
Do **not** use full `requirements.txt` (torch, streamlit); that is for rebuilding indices or the sandbox only.

On Windows, if `python` / `pip` fail, use `py -3` and `py -3 -m pip`, or run `scripts/setup_env.ps1` then:

```powershell
.\.tools\python-embed\python.exe -m pip install -r requirements-rank.txt
```

If setup stops at `No module named venv`, that is expected — use the embed command above, then run Step 6 with `.\.tools\python-embed\python.exe` instead of `python`.

### Step 6 — Generate submission CSV

This is the `reproduce_command` in `submission_metadata.yaml`. Runs offline using pre-built `indices/`.

```bash
python rank.py --indices ./indices --out ./submission.csv
```

Expected output:

```text
Ranking with cached FAISS + BM25 + structured scorer.
Wrote 100 rows to .../submission.csv
```

**~10–20 s** on an 8-core CPU laptop — within the hackathon compute constraint (CPU-only, no network).

### Step 7 — Validate CSV format (optional)

Quick local format check (stdlib only):

```bash
python India_runs_data_and_ai_challenge/validate_submission.py submission.csv
```

Checks header, 100 rows, ranks 1–100, monotonic scores, and `CAND_#######` IDs.

---

## Reproduction scope

What Step 6 produces and what it depends on:

| Item | Detail |
|------|--------|
| Output | `submission.csv`: header + exactly 100 ranked rows, monotonic scores |
| Runtime | ~10–20 s on CPU with pre-built `indices/`, no network |
| Artifacts | `indices/` via Git LFS; offline index build (~85 min) is already done |

**Used by reproduce:** `rank.py`, `requirements-rank.txt`, `config/role_spec.yaml`, `src/*.py`, `indices/`.

**Not required for Step 6:** `app.py`, `indices_sample/`, full `requirements.txt`, `scripts/build_index.py`, `docs/`. The Hugging Face sandbox is a separate demo path — see below.

Portal deliverables and upload checklist: [`SUBMISSION.md`](SUBMISSION.md). Team metadata: [`submission_metadata.yaml`](submission_metadata.yaml).

---

## Live sandbox (Hugging Face)

[https://huggingface.co/spaces/Sarthak080907/proofrank](https://huggingface.co/spaces/Sarthak080907/proofrank) — ranks the 50-profile sample (or your uploaded JSON ≤100) with the same engine as `rank.py`. Deploy notes: [`docs/SANDBOX_DEPLOY.md`](docs/SANDBOX_DEPLOY.md).
