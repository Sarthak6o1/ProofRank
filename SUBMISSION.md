# Submission checklist

## You — before portal upload

```bash
python rank.py --indices ./indices --out ./submission.csv
python India_runs_data_and_ai_challenge/validate_submission.py submission.csv
python scripts/audit_submission.py submission.csv \
  --candidates ./India_runs_data_and_ai_challenge/candidates.jsonl.gz
```

Indices are already built locally (or pulled via Git LFS). Rebuild only if you changed the ranker:

```bash
python scripts/build_index.py \
  --candidates ./India_runs_data_and_ai_challenge/candidates.jsonl.gz \
  --out ./indices
```

## Judges — Stage 3 reproduce

```bash
git clone https://github.com/Sarthak6o1/ProofRank.git && cd ProofRank
git lfs install && git lfs pull
pip install -r requirements.txt
python rank.py --indices ./indices --out ./submission.csv
```

Timed command (in metadata): `python rank.py --indices ./indices --out ./submission.csv`

`git lfs pull` (~1 GB) is one-time setup, not part of the 5-minute reproduce timer.

## Portal

- `team_<name>.csv`
- `submission_metadata.yaml` fields (team, GitHub, sandbox, AI declaration)
- Approach PDF
- HuggingFace sandbox URL
