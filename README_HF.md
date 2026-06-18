---
title: ProofRank
emoji: 🔍
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# ProofRank — Redrob Candidate Ranking Sandbox

Production-parity demo for the **Redrob Intelligent Candidate Discovery & Ranking** challenge.

## Same engine as `rank.py`

| Layer | Implementation |
|-------|----------------|
| Retrieval | Dual FAISS (career + full profile) + dual BM25, RRF fusion |
| Scoring | Career evidence, title tier, skills trust, behavioral multiplier |
| Guards | Honeypot drop, trap-title filter, rank-band eligibility |
| Reasoning | Rule-based evidence strings from profile fields (no LLM at rank time) |

`indices_sample/` holds pre-built indexes for the organizer's 50-profile `sample_candidates.json` bundle (~0.5 MB). Extracted from production `indices/` via FAISS vector reconstruct — no re-embedding at deploy time.

## Try it

1. Open the Space (default: bundled 50 candidates).
2. Optionally upload your own JSON array (≤100 profiles with `candidate_id`).
3. Download ranked CSV with scores and recruiter-style reasoning.

## Repo

Full submission: [github.com/Sarthak6o1/ProofRank](https://github.com/Sarthak6o1/ProofRank)
