# Deploy ProofRank to Hugging Face Spaces

Live sandbox: **https://huggingface.co/spaces/Sarthak080907/proofrank**

The Space runs `rank_sandbox()` — the same code path as production `rank.py` — on the organizer's 50-profile `sample_candidates.json` with pre-built `indices_sample/`.

## One-time local prep

```powershell
# Extract indices_sample/ from production indices/ (~1 second, no re-embed)
powershell -File scripts/build_sandbox_index.ps1
```

## Deploy (git push to HF Space)

1. Create a **Docker → Blank** Space at https://huggingface.co/new-space  
   - Owner: `Sarthak080907`  
   - Name: `proofrank`  
   - Visibility: **Public**  
   - Storage bucket: **OFF** (indexes ship with the repo)

2. Push:

```powershell
powershell -File scripts/deploy_hf_space.ps1 `
  -SpaceUser Sarthak080907 `
  -SpaceName proofrank `
  -Token YOUR_HF_WRITE_TOKEN
```

The script stages Space files (~1 MB), tracks binaries via Git LFS, and pushes to the Space repo.

## What gets deployed

| Path | Purpose |
|------|---------|
| `Dockerfile` | Runs Streamlit on port 7860 (HF Docker SDK) |
| `app.py` | Streamlit UI with honeypot/rankable stats |
| `rank.py` | Production ranker |
| `src/`, `config/` | Feature extraction, retrieval, scoring |
| `indices_sample/` | 50-profile FAISS + BM25 + features (Git LFS on HF) |
| `sample_candidates.json` | Default demo pool |

**Not deployed:** `indices/` (1 GB GitHub LFS), `candidates.jsonl`, build scripts.

## Sandbox behavior (any upload)

- Shows **pool size**, **honeypots excluded**, **rankable max** (pool − honeypots).
- Slider capped at rankable count — no crash when honeypots reduce the pool.
- **Hybrid mode** when all uploaded `candidate_id`s exist in `indices_sample/`.
- **Structured fallback** otherwise (same honeypot filtering, no FAISS).

Bundled sample: 50 profiles, 7 honeypots → **43 rankable max**.
