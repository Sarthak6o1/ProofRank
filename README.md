# ProofRank

**Repository:** [github.com/Sarthak6o1/ProofRank](https://github.com/Sarthak6o1/ProofRank)  
**Sandbox:** [huggingface.co/spaces/Sarthak080907/proofrank](https://huggingface.co/spaces/Sarthak080907/proofrank)

CPU-only hybrid ranker for the Redrob Senior AI Engineer JD: dual FAISS + dual BM25 retrieval, career-proof scoring, honeypot defenses, rule-based reasoning. No LLM at rank time.

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

## HuggingFace sandbox

Live demo on organizer `sample_candidates.json` (50 profiles). Same `rank_sandbox()` engine as production.

Deploy / update: [`docs/SANDBOX_DEPLOY.md`](docs/SANDBOX_DEPLOY.md)

```powershell
powershell -File scripts/build_sandbox_index.ps1
powershell -File scripts/deploy_hf_space.ps1 -SpaceUser Sarthak080907 -SpaceName proofrank -Token YOUR_HF_TOKEN
```

---

## Portal checklist

1. Fill team name + contact in `submission_metadata.yaml`
2. `python India_runs_data_and_ai_challenge/validate_submission.py submission.csv`
3. Export PDF from `docs/APPROACH.md`
4. Upload `team_<name>.csv` + metadata to portal

Full checklist: [`SUBMISSION.md`](SUBMISSION.md)
