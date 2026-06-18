from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime

from .narrative import career_text, current_role, full_text, profile, summary_text

PROF_WEIGHT = {"beginner": 0.30, "intermediate": 0.60, "advanced": 0.85, "expert": 1.00}
TIER_ORDER = {"trap": 0, "weak": 1, "possible": 2, "strong": 3}
AI_SKILL_TERMS = (
    "machine learning", "deep learning", "nlp", "pytorch", "tensorflow", "llm", "rag",
    "vector", "embedding", "fine-tun", "lora", "qlora", "faiss", "ranking",
    "recommendation", "search", "retrieval", "python", "evaluation",
)
ASSESSMENT_TERMS = (
    "machine learning", "deep learning", "nlp", "pytorch", "tensorflow", "llm", "rag",
    "vector", "embedding", "ranking", "retrieval", "python", "evaluation", "search",
)
CV_SPEECH_ROBOTICS = ("computer vision", "image classification", "speech", "tts", "robotics", "autonomous")
DEFAULT_CONSULTING = (
    "tcs", "tata consultancy", "infosys", "wipro", "accenture", "cognizant", "capgemini",
    "hcl", "tech mahindra", "mindtree", "ltimindtree", "mphasis", "hexaware",
)
STARTUP_SIZES = {"1-10", "11-50", "51-200", "201-500"}


def _lower(x: object) -> str:
    return str(x or "").lower()


def _year(date_text: object) -> int | None:
    m = re.search(r"\d{4}", str(date_text or ""))
    return int(m.group(0)) if m else None


def _title_tier(title: str, spec: dict) -> tuple[str, float]:
    tl = _lower(title)
    tiers = spec.get("title_tiers") or {}
    for trap in tiers.get("trap", []):
        if _lower(trap) in tl:
            return "trap", 0.0
    for strong in tiers.get("strong", []):
        if _lower(strong) in tl:
            return "strong", 1.0
    for possible in tiers.get("possible", []):
        if _lower(possible) in tl:
            return "possible", 0.70
    if any(k in tl for k in ("machine learning", " ml", " ai ", "ai engineer", "nlp", "search", "recommend", "data scien")):
        return "possible", 0.65
    return "weak", 0.35


def _best_title_tier(candidate: dict, spec: dict) -> tuple[str, float, str]:
    best_tier, best_score, best_title = "weak", 0.35, str(profile(candidate).get("current_title") or "")
    for role in candidate.get("career_history") or []:
        title = str(role.get("title") or "")
        tier, base = _title_tier(title, spec)
        months = int(role.get("duration_months") or 0)
        weighted = base * min(1.0, 0.35 + months / 30.0)
        if TIER_ORDER[tier] > TIER_ORDER[best_tier] or (
            TIER_ORDER[tier] == TIER_ORDER[best_tier] and weighted > best_score
        ):
            best_tier, best_score, best_title = tier, weighted, title
    cur_title = str(profile(candidate).get("current_title") or "")
    cur_tier, cur_score = _title_tier(cur_title, spec)
    if TIER_ORDER[cur_tier] >= TIER_ORDER[best_tier]:
        return cur_tier, max(best_score, cur_score), cur_title or best_title
    return best_tier, best_score, best_title


def _family_score(text: str, terms: list[str], hits_out: list[str], cap_hits: int = 3) -> float:
    hits = [term for term in terms if _lower(term) in text]
    hits_out.extend(hits[:3])
    return min(1.0, len(hits) / cap_hits)


def career_evidence(text: str, spec: dict) -> tuple[float, list[str]]:
    tl = _lower(text)
    families = spec.get("career_evidence_terms") or {}
    weights = {"retrieval": 0.28, "ranking": 0.28, "production": 0.24, "llm": 0.12, "plain_language": 0.08}
    hits: list[str] = []
    score = 0.0
    for family, weight in weights.items():
        score += weight * _family_score(tl, [str(x) for x in families.get(family, [])], hits)
    return min(1.0, score), list(dict.fromkeys(hits))[:6]


def _blended_evidence(candidate: dict, spec: dict) -> tuple[float, list[str], float, float]:
    ctext = career_text(candidate)
    stext = summary_text(candidate)
    career_score, career_hits = career_evidence(ctext, spec)
    summary_score, summary_hits = career_evidence(stext, spec)
    combined = min(1.0, 0.82 * career_score + 0.18 * summary_score)
    hits = list(dict.fromkeys([*career_hits, *summary_hits]))[:6]
    return combined, hits, career_score, summary_score


def skill_trust(candidate: dict) -> tuple[float, int, list[str]]:
    values: list[float] = []
    ai_values: list[float] = []
    ai_names: list[str] = []
    for skill in candidate.get("skills") or []:
        name = str(skill.get("name") or "")
        nl = name.lower()
        prof = PROF_WEIGHT.get(_lower(skill.get("proficiency")), 0.40)
        endorsements = int(skill.get("endorsements") or 0)
        months = float(skill.get("duration_months") or 0)
        trust = prof * math.log1p(endorsements) * min(months, 48) / 48.0
        trust = min(1.0, trust / 3.0)
        values.append(trust)
        if any(term in nl for term in AI_SKILL_TERMS):
            ai_values.append(trust)
            ai_names.append(name)
    if ai_values:
        return sum(ai_values) / len(ai_values), len(ai_values), ai_names[:6]
    return (sum(values) / len(values) if values else 0.0), 0, []


def assessment_score(candidate: dict) -> float:
    scores = (candidate.get("redrob_signals") or {}).get("skill_assessment_scores") or {}
    vals = [float(v) for k, v in scores.items() if any(term in _lower(k) for term in ASSESSMENT_TERMS)]
    if not vals:
        return 0.0
    return max(0.0, min(1.0, sum(vals) / len(vals) / 100.0))


def _education_score(candidate: dict) -> float:
    edu = candidate.get("education") or []
    if not edu:
        return 0.25
    score = 0.0
    for item in edu:
        field = _lower(item.get("field_of_study"))
        degree = _lower(item.get("degree"))
        tier = _lower(item.get("tier"))
        if any(x in field for x in ("computer", "machine learning", "artificial", "data science", "software", "electrical")):
            score += 0.35
        if any(x in degree for x in ("m.tech", "m.s", "ms", "phd", "master")):
            score += 0.20
        score += {"tier_1": 0.25, "tier_2": 0.18, "tier_3": 0.10, "tier_4": 0.05}.get(tier, 0.05)
    return min(1.0, score)


def _company_scale_score(candidate: dict) -> float:
    p = profile(candidate)
    role = current_role(candidate)
    score = 0.0
    for size in (p.get("current_company_size"), role.get("company_size")):
        if str(size or "") in STARTUP_SIZES:
            score += 0.35
        elif str(size or "") in {"501-1000", "1001-5000"}:
            score += 0.20
        elif str(size or "") == "10001+":
            score += 0.05
    return min(1.0, score)


def _work_mode_fit(candidate: dict) -> float:
    mode = _lower((candidate.get("redrob_signals") or {}).get("preferred_work_mode"))
    if mode in ("hybrid", "flexible"):
        return 1.0
    if mode == "remote":
        return 0.82
    if mode == "onsite":
        return 0.90
    return 0.70


def _platform_activity_score(candidate: dict) -> float:
    sig = candidate.get("redrob_signals") or {}
    views = int(sig.get("profile_views_received_30d") or 0)
    apps = int(sig.get("applications_submitted_30d") or 0)
    search = int(sig.get("search_appearance_30d") or 0)
    saved = int(sig.get("saved_by_recruiters_30d") or 0)
    score = 0.0
    if views >= 20:
        score += 0.25
    elif views >= 5:
        score += 0.12
    if apps >= 3:
        score += 0.15
    if search >= 10:
        score += 0.25
    elif search >= 3:
        score += 0.12
    if saved >= 3:
        score += 0.20
    elif saved >= 1:
        score += 0.10
    return min(1.0, score)


def _verified_trust(candidate: dict) -> float:
    sig = candidate.get("redrob_signals") or {}
    flags = [bool(sig.get("verified_email")), bool(sig.get("verified_phone")), bool(sig.get("linkedin_connected"))]
    return sum(flags) / 3.0


def _yoe_location_fit(candidate: dict, spec: dict) -> float:
    p = profile(candidate)
    sig = candidate.get("redrob_signals") or {}
    yoe = float(p.get("years_of_experience") or 0)
    yspec = spec.get("yoe", {})
    ymin, ymax = float(yspec.get("min", 5.0)), float(yspec.get("max", 9.0))
    if ymin <= yoe <= ymax:
        yoe_score = 1.0
    elif yoe < ymin:
        yoe_score = max(0.25, 1.0 - (ymin - yoe) / 4.0)
    else:
        yoe_score = max(0.35, 1.0 - (yoe - ymax) / 7.0)
    loc_text = f"{p.get('location', '')} {p.get('country', '')}".lower()
    boosts = [_lower(x) for x in spec.get("location_boost", [])]
    loc_score = 1.0 if any(x and x in loc_text for x in boosts) else 0.35
    if sig.get("willing_to_relocate"):
        loc_score = max(loc_score, 0.70)
    return 0.60 * yoe_score + 0.40 * loc_score


def _consulting_only(candidate: dict, spec: dict) -> bool:
    roles = candidate.get("career_history") or []
    if len(roles) < 2:
        return False
    firms = tuple(_lower(x) for x in spec.get("consulting_companies", DEFAULT_CONSULTING))
    consulting_roles = 0
    for role in roles:
        blob = f"{role.get('company','')} {role.get('industry','')} {role.get('description','')}".lower()
        if any(firm in blob for firm in firms) or any(term in blob for term in ("consulting", "outsourc", "staffing")):
            consulting_roles += 1
    return consulting_roles == len(roles)


def _product_company_score(candidate: dict, spec: dict) -> float:
    roles = candidate.get("career_history") or []
    if not roles:
        return 0.0
    terms = tuple(_lower(x) for x in spec.get("product_company_terms", []))
    score = 0.0
    for role in roles:
        blob = f"{role.get('company','')} {role.get('industry','')} {role.get('description','')}".lower()
        if any(term in blob for term in terms):
            score += 0.35
        if not any(firm in blob for firm in DEFAULT_CONSULTING):
            score += 0.10
    return min(1.0, score)


def _research_only(candidate: dict, career_ev: float) -> bool:
    blob = full_text(candidate).lower()
    research = any(term in blob for term in ("research scientist", "academic lab", "phd", "paper", "publication", "university lab"))
    production = any(term in blob for term in ("production", "shipped", "deployed", "real users", "a/b test", "serving"))
    return research and not production and career_ev < 0.35


def _langchain_only(candidate: dict, career_ev: float) -> bool:
    blob = full_text(candidate).lower()
    has_framework = "langchain" in blob or "llamaindex" in blob
    real_ir = any(term in blob for term in ("retrieval", "ranking", "faiss", "bm25", "elasticsearch", "recommendation", "ndcg", "mrr"))
    return has_framework and not real_ir and career_ev < 0.35


def _title_chaser(candidate: dict) -> bool:
    roles = sorted(candidate.get("career_history") or [], key=lambda r: str(r.get("start_date") or ""), reverse=True)
    recent = roles[:5]
    short_roles = sum(1 for role in recent if int(role.get("duration_months") or 0) < 18)
    title_words = " ".join(_lower(r.get("title")) for r in recent)
    senior_titles = sum(1 for word in ("senior", "staff", "principal", "lead") if word in title_words)
    return len(recent) >= 4 and short_roles >= 4 and senior_titles >= 2


def _summary_title_mismatch(candidate: dict) -> bool:
    p = profile(candidate)
    summary = _lower(p.get("summary"))
    title = _lower(p.get("current_title"))
    if "marketing manager" in summary and "marketing" not in title:
        return True
    if "my professional background is in marketing manager" in summary and "marketing" not in title:
        return True
    return False


def _cv_speech_without_ir(candidate: dict) -> bool:
    blob = full_text(candidate).lower()
    cv_hits = sum(1 for term in CV_SPEECH_ROBOTICS if term in blob)
    ir_hits = sum(1 for term in ("retrieval", "ranking", "recommendation", "nlp", "search", "semantic") if term in blob)
    return cv_hits >= 3 and ir_hits == 0


def honeypot_flag(candidate: dict, title_tier: str, career_ev: float, ai_count: int, trust: float) -> tuple[bool, list[str]]:
    p = profile(candidate)
    yoe = float(p.get("years_of_experience") or 0)
    skills = candidate.get("skills") or []
    roles = candidate.get("career_history") or []
    reasons: list[str] = []

    expert_tiny = [s for s in skills if _lower(s.get("proficiency")) == "expert" and float(s.get("duration_months") or 0) < 3]
    if len(expert_tiny) >= 3:
        reasons.append("expert skills with near-zero duration")
    expert_zero = [s for s in skills if _lower(s.get("proficiency")) == "expert" and float(s.get("duration_months") or 0) == 0]
    if expert_zero:
        reasons.append("expert skill with zero duration")
    if len(skills) >= 10 and sum(int(s.get("endorsements") or 0) for s in skills) == 0:
        reasons.append("many skills with zero endorsements")

    years = [_year(r.get("start_date")) for r in roles if _year(r.get("start_date"))]
    if years and yoe >= 8 and min(years) > datetime.now().year - 4:
        reasons.append("claimed YoE contradicts role start dates")

    total_role_months = sum(int(r.get("duration_months") or 0) for r in roles)
    if yoe > 0 and total_role_months > int(yoe * 12 + 30):
        reasons.append("role durations exceed total experience")
    if yoe > 0 and any(int(r.get("duration_months") or 0) > int(yoe * 12 + 6) for r in roles):
        reasons.append("single role longer than total experience")

    edu_end_years = [int(e.get("end_year")) for e in candidate.get("education") or [] if e.get("end_year")]
    if edu_end_years and years:
        earliest_job = min(years)
        latest_edu = max(edu_end_years)
        if latest_edu > earliest_job + 2 and yoe >= 6:
            reasons.append("education timeline conflicts with claimed experience")

    assess = assessment_score(candidate)
    if assess >= 0.85 and title_tier == "trap" and career_ev < 0.20:
        reasons.append("high assessments but no matching career proof")
    if title_tier in ("trap", "weak") and ai_count >= 8 and trust < 0.20 and career_ev < 0.30:
        reasons.append("keyword-stuffed profile without career proof")
    return bool(reasons), reasons[:4]


def extract_features(candidate: dict, spec: dict) -> dict:
    p = profile(candidate)
    sig = candidate.get("redrob_signals") or {}
    role = current_role(candidate)
    evidence, evidence_terms, career_only_ev, summary_ev = _blended_evidence(candidate, spec)
    title = str(p.get("current_title") or "")
    tier, tier_score, best_title = _best_title_tier(candidate, spec)
    trust, ai_count, ai_skill_names = skill_trust(candidate)
    assess = assessment_score(candidate)
    consulting = _consulting_only(candidate, spec)
    stuffer = tier in ("weak", "trap") and ai_count >= 6 and trust < 0.35 and evidence < 0.45
    research_only = _research_only(candidate, evidence)
    langchain_only = _langchain_only(candidate, evidence)
    title_chaser = _title_chaser(candidate)
    mismatch = _summary_title_mismatch(candidate)
    cv_only = _cv_speech_without_ir(candidate)
    hp, hp_reasons = honeypot_flag(candidate, tier, evidence, ai_count, trust)

    anti = 0.0
    if stuffer:
        anti += 0.50
    if consulting:
        anti += 0.30
    if research_only:
        anti += 0.40
    if langchain_only:
        anti += 0.25
    if title_chaser:
        anti += 0.20
    if mismatch:
        anti += 0.35
    if cv_only:
        anti += 0.20
    if tier == "trap" and evidence < 0.60:
        anti += 0.80

    ctext = career_text(candidate)
    edu_top = ""
    if candidate.get("education"):
        e0 = candidate["education"][0]
        edu_top = f"{e0.get('degree','')} {e0.get('field_of_study','')}".strip()

    return {
        "candidate_id": candidate.get("candidate_id"),
        "current_title": title,
        "best_career_title": best_title,
        "current_company": str(p.get("current_company") or ""),
        "current_industry": str(p.get("current_industry") or ""),
        "years_of_experience": float(p.get("years_of_experience") or 0),
        "location": str(p.get("location") or ""),
        "country": str(p.get("country") or ""),
        "career_evidence": evidence,
        "career_only_evidence": career_only_ev,
        "summary_evidence": summary_ev,
        "career_terms": "|".join(evidence_terms),
        "title_tier": tier,
        "title_tier_score": tier_score,
        "skill_trust": min(1.0, trust),
        "ai_skill_count": ai_count,
        "ai_skill_names": "|".join(ai_skill_names[:5]),
        "assessment_score": assess,
        "education_score": _education_score(candidate),
        "education_top": edu_top,
        "company_scale_score": _company_scale_score(candidate),
        "work_mode_fit": _work_mode_fit(candidate),
        "platform_activity_score": _platform_activity_score(candidate),
        "verified_trust": _verified_trust(candidate),
        "yoe_location_fit": _yoe_location_fit(candidate, spec),
        "product_company_score": _product_company_score(candidate, spec),
        "anti_pattern_penalty": min(1.0, anti),
        "honeypot_flag": hp,
        "honeypot_reasons": "|".join(hp_reasons),
        "stuffer_flag": stuffer,
        "consulting_only": consulting,
        "research_only": research_only,
        "langchain_only": langchain_only,
        "title_chaser": title_chaser,
        "summary_title_mismatch": mismatch,
        "cv_speech_without_ir": cv_only,
        "preferred_work_mode": str(sig.get("preferred_work_mode") or ""),
        "open_to_work_flag": bool(sig.get("open_to_work_flag", False)),
        "willing_to_relocate": bool(sig.get("willing_to_relocate", False)),
        "recruiter_response_rate": float(sig.get("recruiter_response_rate") or 0),
        "avg_response_time_hours": float(sig.get("avg_response_time_hours") or 0),
        "notice_period_days": int(sig.get("notice_period_days") or 90),
        "profile_completeness_score": float(sig.get("profile_completeness_score") or 0),
        "last_active_date": sig.get("last_active_date") or "",
        "github_activity_score": float(sig.get("github_activity_score") if sig.get("github_activity_score") is not None else -1),
        "saved_by_recruiters_30d": int(sig.get("saved_by_recruiters_30d") or 0),
        "profile_views_received_30d": int(sig.get("profile_views_received_30d") or 0),
        "search_appearance_30d": int(sig.get("search_appearance_30d") or 0),
        "interview_completion_rate": float(sig.get("interview_completion_rate") or 0),
        "offer_acceptance_rate": float(sig.get("offer_acceptance_rate") if sig.get("offer_acceptance_rate") is not None else -1),
        "verified_email": bool(sig.get("verified_email", False)),
        "verified_phone": bool(sig.get("verified_phone", False)),
        "linkedin_connected": bool(sig.get("linkedin_connected", False)),
        "career_hash": hashlib.sha1(ctext.encode("utf-8", errors="ignore")).hexdigest(),
        "career_hash_count": 1,
        "current_role_excerpt": str(role.get("description") or "")[:180].replace("\n", " "),
    }


def attach_hash_counts(features_df):
    counts = features_df["career_hash"].value_counts().to_dict()
    features_df["career_hash_count"] = features_df["career_hash"].map(counts).astype(int)
    return features_df


def features_dataframe(candidates: list[dict], spec: dict):
    import pandas as pd

    df = pd.DataFrame(extract_features(candidate, spec) for candidate in candidates)
    return attach_hash_counts(df)
