from __future__ import annotations


def profile(candidate: dict) -> dict:
    return candidate.get("profile") or {}


def current_role(candidate: dict) -> dict:
    roles = candidate.get("career_history") or []
    for role in roles:
        if role.get("is_current"):
            return role
    return roles[0] if roles else {}


def career_text(candidate: dict) -> str:
    parts: list[str] = []
    for role in candidate.get("career_history") or []:
        title = role.get("title") or ""
        company = role.get("company") or ""
        industry = role.get("industry") or ""
        desc = role.get("description") or ""
        parts.append(f"{title} at {company} ({industry}). {desc}")
    return "\n".join(p for p in parts if p.strip())


def summary_text(candidate: dict) -> str:
    p = profile(candidate)
    return "\n".join(str(x) for x in [p.get("headline"), p.get("summary")] if x)


def profile_text(candidate: dict) -> str:
    p = profile(candidate)
    return "\n".join(
        str(x)
        for x in [
            p.get("headline"),
            p.get("summary"),
            p.get("current_title"),
            p.get("current_industry"),
            p.get("location"),
            p.get("country"),
        ]
        if x
    )


def certification_text(candidate: dict) -> str:
    certs = candidate.get("certifications") or []
    if not certs:
        return ""
    names = [f"{c.get('name', '')} ({c.get('issuer', '')})" for c in certs[:6] if c.get("name")]
    return "Certifications: " + ", ".join(names) if names else ""


def language_text(candidate: dict) -> str:
    langs = candidate.get("languages") or []
    if not langs:
        return ""
    names = [f"{l.get('language', '')} ({l.get('proficiency', '')})" for l in langs[:4] if l.get("language")]
    return "Languages: " + ", ".join(names) if names else ""


def trusted_skill_names(candidate: dict, limit: int = 8) -> list[str]:
    skills = candidate.get("skills") or []
    ranked = sorted(
        skills,
        key=lambda s: (
            int(s.get("endorsements") or 0),
            int(s.get("duration_months") or 0),
            str(s.get("proficiency") or ""),
        ),
        reverse=True,
    )
    return [str(s.get("name")) for s in ranked[:limit] if s.get("name")]


def full_text(candidate: dict) -> str:
    skills = trusted_skill_names(candidate)
    skill_part = f"Skills: {', '.join(skills)}" if skills else ""
    return "\n".join(
        p
        for p in [
            profile_text(candidate),
            career_text(candidate),
            certification_text(candidate),
            language_text(candidate),
            skill_part,
        ]
        if p
    )
