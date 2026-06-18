# ProofRank

**Repository:** [github.com/Sarthak6o1/ProofRank](https://github.com/Sarthak6o1/ProofRank)

---

## Judges — run ranking (no 85-min build)

Pre-built `indices/` are in this repo (Git LFS). **No `candidates.jsonl`. No `build_index.py`.**

### Setup once

```bash
git clone https://github.com/Sarthak6o1/ProofRank.git && cd ProofRank
git lfs install && git lfs pull
pip install -r requirements.txt
```

`git lfs pull` downloads indexes (~1 GB). Not part of the 5-minute reproduce timer.

### Reproduce command (timed, < 5 min, CPU, no network)

```bash
python rank.py --indices ./indices --out ./submission.csv
```

### Optional

```bash
python India_runs_data_and_ai_challenge/validate_submission.py submission.csv
```

---

## What is in the repo

| Included (Git LFS) | Not needed for reproduce |
|---|---|
| `faiss_career.index`, `faiss_full.index` | `candidates.jsonl.gz` |
| `bm25.pkl`, `bm25_career.pkl` + token files | `build_index.py` |
| `features.parquet`, `jd_query_vec.npy` | |

Offline build was ~85 min once; results are bundled so judges only run `rank.py`.

---

## HuggingFace sandbox

See [`docs/SANDBOX_DEPLOY.md`](docs/SANDBOX_DEPLOY.md) for deploy steps.

```bash
powershell -File scripts/build_sandbox_index.ps1
powershell -File scripts/deploy_hf_space.ps1 -SpaceUser YOUR_HF_USER -SpaceName proofrank
```

Sandbox URL for portal: `https://huggingface.co/spaces/YOUR_HF_USER/proofrank`

---

## Portal checklist

1. `validate_submission.py submission.csv`
2. Fill `submission_metadata.yaml`
3. PDF from `docs/APPROACH.md`
4. Upload `team_<name>.csv`
