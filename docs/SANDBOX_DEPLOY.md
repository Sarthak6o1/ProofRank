# Deploy ProofRank to Hugging Face Spaces

The sandbox is a **Streamlit Space** that runs the same `rank_sandbox()` path as production `rank.py`, on the organizer's 50-profile `sample_candidates.json` bundle with pre-built `indices_sample/`.

## One-time local prep

```powershell
# Extract indices_sample/ from production indices/ (~1 second, no re-embed)
powershell -File scripts/build_sandbox_index.ps1

# Verify sandbox ranking
.tools\python-embed\python.exe -c "import json; from pathlib import Path; from rank import rank_sandbox; from src.load import load_role_spec; r=Path('.'); s=json.loads((r/'India_runs_data_and_ai_challenge/sample_candidates.json').read_text()); print(rank_sandbox(s, 10, load_role_spec(r/'config/role_spec.yaml'), r)[1])"
```

## Deploy (git push to HF Space)

1. Create a **Streamlit** Space at https://huggingface.co/new-space  
   - Owner: your HF username (e.g. `Sarthak6o1`)  
   - Name: `proofrank`  
   - Visibility: **Public**

2. Package and push:

```powershell
powershell -File scripts/deploy_hf_space.ps1 -SpaceUser Sarthak6o1 -SpaceName proofrank
```

The script stages only Space-needed files (~1 MB with `indices_sample/`), initializes a git repo, and pushes to:

`https://huggingface.co/spaces/Sarthak6o1/proofrank`

3. Update `submission_metadata.yaml`:

```yaml
sandbox_link: "https://huggingface.co/spaces/Sarthak6o1/proofrank"
```

## What gets deployed

| Path | Purpose |
|------|---------|
| `app.py` | Streamlit UI |
| `rank.py` | Production ranker (shared code path) |
| `src/`, `config/` | Feature extraction, retrieval, scoring |
| `indices_sample/` | 50-profile FAISS + BM25 + features |
| `India_runs_data_and_ai_challenge/sample_candidates.json` | Default demo pool |
| `requirements.txt` | Python deps |
| `README.md` | HF Space card (YAML frontmatter) |

**Not deployed:** `indices/` (1 GB LFS), `candidates.jsonl`, `.tools/`, build scripts.

## Engineering notes

- `scripts/extract_sandbox_indices.py` subsets production `indices/` via FAISS `reconstruct` — no second embedding run, no model download on deploy.
- Uploads in the Space are ranked with the same hybrid pipeline when all IDs exist in the loaded index bundle; otherwise structured fallback applies.
- HF build may take 3–5 minutes on first boot (pip install). Ranking itself is seconds on CPU.
