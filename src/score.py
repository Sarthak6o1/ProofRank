from __future__ import annotations

from datetime import datetime, timezone


def _float(row: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def composite_score(row: dict, spec: dict) -> float:
    weights = spec.get("scoring_weights") or {}
    score = (
        weights.get("retrieval_rrf", 0.14) * _float(row, "retrieval_rrf")
        + weights.get("career_evidence", 0.38) * _float(row, "career_evidence")
        + weights.get("title_tier", 0.13) * _float(row, "title_tier_score")
        + weights.get("yoe_location_fit", 0.09) * _float(row, "yoe_location_fit")
        + weights.get("skill_trust", 0.07) * _float(row, "skill_trust")
        + weights.get("assessment_score", 0.05) * _float(row, "assessment_score")
        + weights.get("product_company", 0.04) * _float(row, "product_company_score")
        + weights.get("education_score", 0.04) * _float(row, "education_score")
        + weights.get("company_scale_score", 0.03) * _float(row, "company_scale_score")
        + weights.get("work_mode_fit", 0.02) * _float(row, "work_mode_fit")
        + weights.get("platform_activity_score", 0.02) * _float(row, "platform_activity_score")
        - weights.get("anti_pattern_penalty", 0.12) * _float(row, "anti_pattern_penalty")
        + _float(row, "rank_time_bonus")
    )
    return max(0.0, min(1.0, score))


def _recency_multiplier(last_active: str | None) -> float:
    if not last_active:
        return 0.78
    try:
        dt = datetime.fromisoformat(str(last_active).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - dt).days
    except (TypeError, ValueError):
        return 0.82
    if days <= 30:
        return 1.00
    if days <= 90:
        return 0.93
    if days <= 180:
        return 0.84
    if days <= 365:
        return 0.76
    return 0.68


def behavioral_multiplier(row: dict) -> float:
    mult = _recency_multiplier(row.get("last_active_date"))

    response = _float(row, "recruiter_response_rate")
    if response >= 0.60:
        mult *= 1.06
    elif response < 0.10:
        mult *= 0.76
    elif response < 0.25:
        mult *= 0.90

    avg_hours = _float(row, "avg_response_time_hours", 48)
    if avg_hours and avg_hours <= 12:
        mult *= 1.02
    elif avg_hours > 96:
        mult *= 0.95

    notice = int(_float(row, "notice_period_days", 90))
    if notice <= 30:
        mult *= 1.05
    elif notice > 90:
        mult *= 0.90

    if row.get("open_to_work_flag"):
        mult *= 1.04
    if row.get("willing_to_relocate"):
        mult *= 1.02

    completeness = _float(row, "profile_completeness_score")
    if completeness >= 80:
        mult *= 1.02
    elif completeness < 40:
        mult *= 0.95

    if _float(row, "github_activity_score", -1) >= 50:
        mult *= 1.02
    if _float(row, "saved_by_recruiters_30d") >= 3:
        mult *= 1.03
    if _float(row, "interview_completion_rate") >= 0.85:
        mult *= 1.02
    if 0 <= _float(row, "offer_acceptance_rate", -1) < 0.25:
        mult *= 0.96
    if _float(row, "verified_trust") >= 0.66:
        mult *= 1.01
    if _float(row, "work_mode_fit") >= 0.90:
        mult *= 1.02
    if _float(row, "platform_activity_score") >= 0.50:
        mult *= 1.02

    return max(0.70, min(1.15, mult))


def final_score(row: dict, spec: dict) -> float:
    base = composite_score(row, spec)
    return base * behavioral_multiplier(row)


def monotonic_submission_scores(raw_scores: list[float]) -> list[float]:
    if not raw_scores:
        return []
    hi, lo = max(raw_scores), min(raw_scores)
    if hi == lo:
        return [round(max(0.01, 0.99 - i * 0.001), 4) for i in range(len(raw_scores))]
    scaled = [0.20 + 0.79 * (s - lo) / (hi - lo) for s in raw_scores]
    out = [min(0.99, scaled[0])]
    for score in scaled[1:]:
        out.append(min(out[-1] - 0.0001, score))
    return [round(max(0.01, s), 4) for s in out]
