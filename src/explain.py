from __future__ import annotations


def _pct(x: object) -> str:
    try:
        return f"{float(x):.0%}"
    except (TypeError, ValueError):
        return "n/a"


def _first_pipe(text: object, default: str = "") -> str:
    value = str(text or "")
    if not value:
        return default
    return value.split("|")[0]


def build_reasoning(row: dict, rank: int) -> str:
    """Build fact-grounded, rank-aware reasoning without an LLM."""
    title = str(row.get("current_title") or "Candidate")
    best_title = str(row.get("best_career_title") or title)
    company = str(row.get("current_company") or "").strip()
    yoe = float(row.get("years_of_experience") or 0)
    location = str(row.get("location") or row.get("country") or "").strip()
    career = float(row.get("career_evidence") or 0)
    response = row.get("recruiter_response_rate", 0)
    notice = int(float(row.get("notice_period_days") or 90))
    terms = str(row.get("career_terms") or "").replace("|", ", ")
    skills = str(row.get("ai_skill_names") or "").replace("|", ", ")
    edu = str(row.get("education_top") or "").strip()
    work_mode = str(row.get("preferred_work_mode") or "").strip()

    if rank <= 10:
        opener = f"Top-{rank} fit: {title}"
    elif rank <= 50:
        opener = f"Shortlist fit: {title}"
    else:
        opener = f"Depth pick: {title}"
    if company:
        opener += f" at {company}"
    if best_title and best_title != title:
        opener += f"; strongest role: {best_title}"

    parts = [opener]
    if career >= 0.65:
        parts.append(f"strong career proof for retrieval/ranking ({terms or 'production ML evidence'})")
    elif career >= 0.40:
        parts.append(f"partial JD evidence in career history ({terms or 'search/ML adjacent work'})")
    else:
        parts.append("limited direct retrieval/ranking proof")

    if 5 <= yoe <= 9:
        parts.append(f"{yoe:.1f} years in the JD band")
    elif yoe < 5:
        parts.append(f"{yoe:.1f} years, slightly junior for the JD")
    else:
        parts.append(f"{yoe:.1f} years, above the preferred band")

    if location:
        if str(row.get("country") or "").lower() == "india" or row.get("willing_to_relocate"):
            parts.append(f"{location} location/relocation fit")
        else:
            parts.append(f"{location}; India onsite fit unclear")

    if edu and rank <= 60:
        parts.append(f"education: {edu}")
    if work_mode:
        parts.append(f"prefers {work_mode} work")

    if row.get("open_to_work_flag"):
        parts.append("open to work")
    if float(response or 0) >= 0.50:
        parts.append(f"recruiter response rate {_pct(response)}")
    elif float(response or 0) < 0.20:
        parts.append(f"concern: low recruiter response rate {_pct(response)}")

    if notice <= 30:
        parts.append(f"{notice}d notice")
    elif notice > 90:
        parts.append(f"concern: long {notice}d notice")

    if skills and rank <= 60:
        parts.append(f"trusted AI skills include {_first_pipe(row.get('ai_skill_names'), skills)}")

    concerns: list[str] = []
    if row.get("consulting_only"):
        concerns.append("consulting-only background")
    if row.get("stuffer_flag"):
        concerns.append("keyword-stuffing risk")
    if row.get("research_only"):
        concerns.append("research-heavy profile")
    if row.get("langchain_only"):
        concerns.append("LangChain-only signal")
    if row.get("summary_title_mismatch"):
        concerns.append("profile/title mismatch")
    if row.get("title_tier") == "weak" and rank > 25:
        concerns.append("weaker title alignment")
    if concerns:
        parts.append("concern: " + ", ".join(concerns[:2]))

    text = "; ".join(parts)
    return text[:297] + "..." if len(text) > 300 else text
