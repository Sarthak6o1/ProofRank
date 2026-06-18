# Submission quick reference

See **[README.md](README.md)** for the full guide.

```bash
# Place organizer candidates.jsonl.gz in India_runs_data_and_ai_challenge/
python scripts/build_index.py --candidates ./India_runs_data_and_ai_challenge/candidates.jsonl.gz --out ./indices
python rank.py --indices ./indices --out ./submission.csv
python India_runs_data_and_ai_challenge/validate_submission.py submission.csv
python scripts/audit_submission.py submission.csv --candidates ./India_runs_data_and_ai_challenge/candidates.jsonl.gz
```

Portal: `submission_metadata.yaml` · PDF from `docs/APPROACH.md` · HF sandbox · rename to `team_<name>.csv`.
