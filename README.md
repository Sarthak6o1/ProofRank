# ProofRank

[![Live Sandbox](https://img.shields.io/badge/Live_Sandbox-Open_Demo-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black)](https://huggingface.co/spaces/Sarthak080907/proofrank)
[![GitHub](https://img.shields.io/badge/GitHub-ProofRank-181717?style=for-the-badge&logo=github)](https://github.com/Sarthak6o1/ProofRank)
[![Redrob Challenge](https://img.shields.io/badge/Redrob-Senior_AI_Engineer_JD-6C63FF?style=for-the-badge)](job_description.md)

CPU-only hybrid ranker for the Redrob Senior AI Engineer JD: dual FAISS + dual BM25 retrieval, career-proof scoring, honeypot defenses, rule-based reasoning. No LLM at rank time.

> **Try it live →** [**ProofRank Sandbox**](https://huggingface.co/spaces/Sarthak080907/proofrank)  
> Rank the organizer's 50-profile sample (or upload your own JSON). Same `rank_sandbox()` engine as production `rank.py`.

| | |
|---|---|
| **Live sandbox** | https://huggingface.co/spaces/Sarthak080907/proofrank |
| **GitHub** | https://github.com/Sarthak6o1/ProofRank |
| **Reproduce** | `python rank.py --indices ./indices --out ./submission.csv` |

---

## Judges — reproduce ranking

Pre-built `indices/` are in this repo (Git LFS). **No `candidates.jsonl`. No `build_index.py`.**

```bash
git clone https://github.com/Sarthak6o1/ProofRank.git && cd ProofRank
git lfs install
git lfs pull
pip install -r requirements.txt
python rank.py --indices ./indices --out ./submission.csv
```

Run `git lfs install` and `git lfs pull` before `rank.py` so LFS index files are present locally. That setup step is separate from the timed `reproduce_command`.

Optional: `python India_runs_data_and_ai_challenge/validate_submission.py submission.csv`

---

## Live sandbox (Hugging Face)

**URL:** https://huggingface.co/spaces/Sarthak080907/proofrank

- Opens with the bundled 50-profile `sample_candidates.json`
- Optional JSON upload (≤100 profiles) to test the ranker
- Hybrid mode when IDs match `indices_sample/`; same pipeline as `rank.py`

Maintainers: [`docs/SANDBOX_DEPLOY.md`](docs/SANDBOX_DEPLOY.md)

---

## What's in the repo

| Artifact | Purpose |
|----------|---------|
| `indices/` (Git LFS) | Production FAISS + BM25 + features for 100K |
| `indices_sample/` | 50-profile bundle for HF sandbox |
| `rank.py` | Production entrypoint |
| `app.py` | Streamlit sandbox UI |
| `config/role_spec.yaml` | JD query, weights, guards |
| `submission_metadata.yaml` | Portal metadata template |

Pre-built indices are bundled so judges only run `rank.py` for reproduction.

---

## Portal checklist

1. Fill team name + contact in `submission_metadata.yaml`
2. `python India_runs_data_and_ai_challenge/validate_submission.py submission.csv`
3. Export PDF from `docs/APPROACH.md`
4. Upload `team_<name>.csv` + metadata to portal

Full checklist: [`SUBMISSION.md`](SUBMISSION.md)
