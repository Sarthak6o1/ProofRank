from __future__ import annotations

import hashlib

MAX_LEN = 360


def _pct(x: object) -> str:
    try:
        return f"{float(x):.0%}"
    except (TypeError, ValueError):
        return "n/a"


def _pick(cid: str, salt: str, options: list[str]) -> str:
    """Deterministically choose one phrasing variant per candidate (reproducible)."""
    if not options:
        return ""
    digest = hashlib.sha1(f"{salt}:{cid}".encode("utf-8")).hexdigest()
    return options[int(digest, 16) % len(options)]


def _shuffle(cid: str, salt: str, items: list[str]) -> list[str]:
    """Stable, candidate-specific ordering so supporting clauses are not in fixed order."""
    return sorted(
        items,
        key=lambda s: hashlib.sha1(f"{salt}:{cid}:{s}".encode("utf-8")).hexdigest(),
    )


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + ", and " + items[-1]


def _cap(text: str) -> str:
    text = " ".join(text.split())
    if len(text) > MAX_LEN:
        return text[: MAX_LEN - 3].rstrip(" ,;.") + "..."
    return text


def _terms_phrase(row: dict, n: int = 3) -> str:
    raw = str(row.get("career_terms") or "")
    terms = [t.strip() for t in raw.split("|") if t.strip()]
    return _join(terms[:n])


def _sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    return text[0].upper() + text[1:]


def build_reasoning(row: dict, rank: int) -> str:
    """Build fact-grounded, rank-aware reasoning without an LLM.

    Reasoning leads with whichever signal actually drove the candidate's rank
    (career proof, a title-vs-substance gap, evaluation rigor, location, or
    product-company background), then adds a varied, candidate-specific set of
    supporting clauses. Phrasing variants are chosen by a hash of candidate_id
    so output stays deterministic and reproducible while avoiding a single
    templated pattern across rows.
    """
    cid = str(row.get("candidate_id") or "")
    title = (str(row.get("current_title") or "Candidate").strip()) or "Candidate"
    best_title = str(row.get("best_career_title") or title).strip()
    company = str(row.get("current_company") or "").strip()
    yoe = float(row.get("years_of_experience") or 0)
    location = str(row.get("location") or row.get("country") or "").strip()
    country = str(row.get("country") or "").lower()
    career = float(row.get("career_evidence") or 0)
    tier = str(row.get("title_tier") or "")
    response = float(row.get("recruiter_response_rate") or 0)
    notice = int(float(row.get("notice_period_days") or 90))
    edu = str(row.get("education_top") or "").strip()
    relocate = bool(row.get("willing_to_relocate"))
    open_to_work = bool(row.get("open_to_work_flag"))
    product = float(row.get("product_company_score") or 0)
    eval_score = float(row.get("rank_eval_score") or 0)
    loc_tier = float(row.get("rank_location_tier") or 0)
    terms = _terms_phrase(row, 3)

    at_company = f" at {company}" if company else ""
    is_gap = (tier == "possible" or (best_title and best_title != title)) and career >= 0.5

    # ---------- lead sentence ----------
    if career < 0.40 and rank > 50:
        opener = _pick(cid, "thin", [
            f"{title}{at_company} is a depth pick at #{rank} — adjacent ML background rather than hard retrieval/ranking proof, but still in the AI-engineering lane.",
            f"At #{rank}, {title}{at_company} rounds out the shortlist; the direct retrieval/ranking signal is thin, so this is a breadth selection.",
            f"{title}{at_company} lands at #{rank} on partial evidence — worth a look, though the core retrieval/ranking work the JD wants is only lightly attested.",
        ])
    elif is_gap:
        proof = terms or "production ML systems"
        strongest = f"; strongest role: {best_title}" if best_title and best_title != title else ""
        proof_full = f"{proof}{strongest}"
        opener = _pick(cid, "gap", [
            f"On paper a {title}{at_company}, but the career history is what earns rank #{rank}: hands-on {proof_full} — exactly the kind of substance-over-buzzwords fit the JD asked us to surface.",
            f"{title}{at_company} reads generic by title, yet the actual work ({proof_full}) maps straight onto the JD's retrieval/ranking mandate — the title-vs-substance gap Redrob flagged.",
            f"The label undersells this one: {title}{at_company} has built {proof_full}, the evidence the JD weighs above any job title, placing them at #{rank}.",
        ])
    elif eval_score >= 0.66 and rank <= 50:
        opener = _pick(cid, "eval", [
            f"{title}{at_company} stands out on a must-have most profiles miss — evaluation rigor ({terms or 'NDCG/MRR/A-B testing'}) — earning #{rank}.",
            f"What lifts {title}{at_company} to #{rank} is demonstrated eval-framework experience, the must-have the JD warns is painful to lack.",
        ])
    elif career >= 0.65:
        strength = terms or "retrieval, ranking and production ML"
        if rank <= 10:
            opener = _pick(cid, "career_top", [
                f"A clear top-{rank} fit: {title}{at_company}, with direct, career-long proof of {strength}.",
                f"{title}{at_company} sits at #{rank} on the strength of real {strength} experience — squarely the intelligence-layer work this role owns.",
                f"#{rank} goes to {title}{at_company}; the career history shows {strength}, not just a skills list.",
            ])
        else:
            opener = _pick(cid, "career", [
                f"{title}{at_company} brings solid {strength} experience, landing at #{rank}.",
                f"Ranked #{rank}: {title}{at_company}, with concrete {strength} work in the career history.",
                f"{title}{at_company} earns #{rank} through hands-on {strength}.",
            ])
    elif product >= 0.5 and loc_tier >= 0.88:
        opener = _pick(cid, "prod", [
            f"{title}{at_company} pairs product-company ML background with strong India-location fit at #{rank}.",
            f"At #{rank}, {title}{at_company} brings product-engineering ML experience in a preferred location.",
        ])
    else:
        opener = _pick(cid, "mid", [
            f"{title}{at_company} is a shortlist fit at #{rank}, with partial JD evidence ({terms or 'search/ML-adjacent work'}).",
            f"#{rank}: {title}{at_company} shows some of the JD's retrieval/ranking signal ({terms or 'ML-adjacent work'}).",
        ])

    # ---------- supporting clauses ----------
    # Experience + location, woven into one sentence.
    if 5 <= yoe <= 9:
        exp_phrase = f"{yoe:.1f} years places them right in the 5-9 band"
    elif yoe < 5:
        exp_phrase = f"at {yoe:.1f} years they run slightly junior to the band"
    else:
        exp_phrase = f"at {yoe:.1f} years they sit above the preferred band"

    in_india = country == "india"
    if loc_tier >= 1.0:
        loc_phrase = f"{location} is one of the JD's preferred hubs"
    elif in_india:
        loc_phrase = f"{location} works for the India-based role"
    elif relocate:
        loc_phrase = f"{location}, but open to relocate"
    elif location:
        loc_phrase = f"{location} is outside India, so onsite/visa fit is unclear"
    else:
        loc_phrase = ""

    if exp_phrase and loc_phrase:
        explo_s = _pick(cid, "explo", [
            _sentence(f"{exp_phrase}, and {loc_phrase}."),
            _sentence(f"{loc_phrase}; {exp_phrase}."),
        ])
    elif loc_phrase:
        explo_s = _sentence(loc_phrase + ".")
    else:
        explo_s = _sentence(exp_phrase + ".")

    # Availability (behavioral) — only when there is something notable to say.
    pos: list[str] = []
    neg: list[str] = []
    if open_to_work:
        pos.append("open to work")
    if response >= 0.60:
        pos.append(f"a strong {_pct(response)} recruiter-response rate")
    elif response >= 0.50:
        pos.append(f"a solid {_pct(response)} response rate")
    elif 0 < response < 0.15:
        neg.append(f"a low {_pct(response)} recruiter-response rate")
    if notice <= 30:
        pos.append(f"a short {notice}-day notice")
    elif notice > 90:
        neg.append(f"a {notice}-day notice period")

    avail_s = ""
    if pos and neg:
        avail_s = _sentence(f"availability is mixed — {_join(pos)}, though {_join(neg)}.")
    elif pos:
        avail_s = _pick(cid, "avail", [
            _sentence(f"on availability they look reachable: {_join(pos)}."),
            _sentence(f"behaviorally a green light — {_join(pos)}."),
        ])
    elif neg:
        avail_s = _sentence(f"availability is a caveat: {_join(neg)}.")

    # Education — included occasionally (not on every row) to avoid a fixed tail.
    edu_s = ""
    if edu and rank <= 40 and _pick(cid, "edu_gate", ["show", "skip", "show"]) == "show":
        edu_s = f"Academic background: {edu}."

    # Concerns / JD disqualifiers, folded into prose.
    concerns: list[str] = []
    if row.get("consulting_only"):
        concerns.append("a consulting-only background the JD is explicitly wary of")
    if row.get("research_only"):
        concerns.append("a research-heavy profile light on production")
    if row.get("langchain_only"):
        concerns.append("mostly recent LangChain-style work")
    if row.get("title_chaser"):
        concerns.append("short, frequent stints that read as title-chasing")
    if row.get("summary_title_mismatch"):
        concerns.append("a summary that does not match the stated title")
    if row.get("stuffer_flag"):
        concerns.append("some keyword-stuffing risk")
    concern_s = ""
    if concerns:
        lead = _pick(cid, "concern", ["Worth probing in interview:", "One flag to check:", "Caveat:"])
        concern_s = f"{lead} {_join(concerns[:2])}."

    # ---------- assemble with rank-based budget and varied order ----------
    budget = 3 if rank <= 10 else (2 if rank <= 50 else 1)
    body = _shuffle(cid, "order", [s for s in (explo_s, avail_s, edu_s) if s])
    reserve = 1 if concern_s else 0

    chosen: list[str] = []
    for sentence in body:
        if len(chosen) >= budget - reserve:
            break
        chosen.append(sentence)
    if concern_s and len(chosen) < budget:
        chosen.append(concern_s)

    return _cap(" ".join([opener, *chosen]))
