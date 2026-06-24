# Submission checklist

## Portal deliverables

| Item | Status / location |
|------|-------------------|
| Ranked CSV | `submission.csv` → rename to `team_<name>.csv` |
| GitHub repo | https://github.com/Sarthak6o1/ProofRank |
| HF sandbox | https://huggingface.co/spaces/Sarthak080907/proofrank |
| Metadata | `submission_metadata.yaml` (fill team name + contact) |
| Approach PDF | Export from `docs/APPROACH.md` |

---

## You — before portal upload

```bash
python rank.py --indices ./indices --out ./submission.csv
python India_runs_data_and_ai_challenge/validate_submission.py submission.csv
python scripts/audit_submission.py submission.csv \
  --candidates ./India_runs_data_and_ai_challenge/candidates.jsonl.gz
```

Indices are pre-built (local or `git lfs pull`). Rebuild only after ranker changes:

```bash
python scripts/build_index.py \
  --candidates ./India_runs_data_and_ai_challenge/candidates.jsonl.gz \
  --out ./indices
```

---

## Judges — Stage 3 reproduce (GitHub)

Full instructions: **[README.md — Reproduce the submission](README.md#reproduce-the-submission-stage-3)**.

**Step 1**

```bash
git lfs install
```

**Step 2**

```bash
git clone https://github.com/Sarthak6o1/ProofRank.git
```

**Step 3**

```bash
cd ProofRank
```

**Step 4** (only if index files are missing)

```bash
git lfs pull
```

**Step 5**

```bash
pip install -r requirements-rank.txt
```

**Step 6 — `reproduce_command` (within compute constraint, ~10–20 s)**

```bash
python rank.py --indices ./indices --out ./submission.csv
```

**Step 7** (optional)

```bash
python India_runs_data_and_ai_challenge/validate_submission.py submission.csv
```

---

## Judges — sandbox (HuggingFace)

Open https://huggingface.co/spaces/Sarthak080907/proofrank

- Default: 50-profile organizer sample, hybrid ranker (`cached_hybrid`).
- UI shows honeypots excluded and rankable max (bundled sample: 50 − 7 honeypots = 43).
- Optional: re-upload `sample_candidates.json` to verify upload path.

Sandbox demonstrates the ranker runs; **scoring uses `submission.csv`** from the 100K pool.

---

## Redeploy sandbox (maintainers)

```powershell
powershell -File scripts/deploy_hf_space.ps1 `
  -SpaceUser Sarthak080907 `
  -SpaceName proofrank `
  -Token YOUR_HF_WRITE_TOKEN
```

See [`docs/SANDBOX_DEPLOY.md`](docs/SANDBOX_DEPLOY.md).
