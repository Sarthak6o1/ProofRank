# ProofRank Approach

## Problem

The Senior AI Engineer JD is intentionally not a keyword-matching task. The right candidate has production experience with retrieval, ranking, embeddings, vector search, evaluation frameworks, and product engineering. The dataset includes keyword stuffers, behavioral traps, and honeypots, so a raw skills or embedding match is unsafe.

## Core Idea

ProofRank ranks by career proof first. Candidate `career_history` is treated as the primary source of truth, while skills, platform behavior, and profile metadata are supporting signals.

## Architecture

```text
Offline:
  candidates -> career/full narratives -> MiniLM embeddings -> FAISS
             -> full narrative tokens -> BM25
             -> structured features -> features.parquet

Online:
  JD query -> cached retrieval -> top candidate pool
           -> honeypot hard-drop
           -> career-proof composite score
           -> behavioral multiplier
           -> top-10 guard
           -> rule-based reasoning
           -> top-100 CSV
```

## Scoring

The composite score uses these signals:

- Career evidence: retrieval, ranking, production deployment, evaluation, RAG/LLM terms in career history
- Title tier: strong ML/AI/search titles over generic or trap titles
- YoE and location: 5-9 years, India, Pune/Noida/major Indian city or relocation
- Skill trust: AI skills weighted by proficiency, endorsements, and duration
- Assessment score: Redrob assessments for relevant skills
- Product company signal: product/platform/marketplace evidence
- Anti-pattern penalty: keyword stuffing, consulting-only, research-only, LangChain-only, title chasing, and profile/title mismatch

Behavioral signals are applied as a multiplier: recent activity, recruiter response rate, notice period, open-to-work, recruiter saves, GitHub activity, and interview/offer reliability.

## Honeypot Defense

ProofRank does not claim access to hidden honeypot labels. It uses layered deterministic checks:

- Expert skills with near-zero or zero duration
- Many skills with zero endorsements
- Claimed years of experience contradict role start dates
- Role durations exceed total career length
- Education timeline conflicts with claimed experience
- Trap title plus high assessment score but no career proof
- Keyword-stuffed weak/trap titles
- Repeated career narratives receive a tie-breaking penalty

Flagged honeypots are hard-dropped before ranking. Remaining subtle traps are controlled through career-first scoring, trap-title exclusion, and the top-10 guard.

## Constraints

- No hosted LLM or API calls during ranking
- CPU-only ranking
- Precomputed FAISS/BM25/features cache
- `rank.py` writes exactly 100 rows with monotonic scores
- Explanations are rule-based and grounded in profile fields
- `validate_submission.py` should be run before upload

## Limitation

The hidden relevance and honeypot labels are not available, so no system can honestly guarantee perfect hidden-score performance. ProofRank is designed to be Stage-3-safe and Stage-4-defensible: reproducible, local, explainable, and aligned with the JD's actual intent.
