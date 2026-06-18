"""Rank-time score adjustments using precomputed parquet fields (no re-embed)."""

from __future__ import annotations

from datetime import datetime, timezone


def _terms_blob(row: dict) -> str:
    parts = [
        str(row.get("career_terms") or ""),
        str(row.get("current_role_excerpt") or ""),
        str(row.get("current_title") or ""),
        str(row.get("best_career_title") or ""),
    ]
    return " ".join(parts).lower()


def _term_hits(text: str, terms: list[str], cap: int = 3) -> float:
    hits = sum(1 for term in terms if term and str(term).lower() in text)
    return min(1.0, hits / cap)


def location_tier_score(row: dict, spec: dict) -> float:
    loc = f"{row.get('location', '')} {row.get('country', '')}".lower()
    tiers = spec.get("location_tiers") or {}
    for city in tiers.get("preferred", []):
        if str(city).lower() in loc:
            return 1.0
    for city in tiers.get("metro", []):
        if str(city).lower() in loc:
            return 0.88
    if "india" in loc:
        return 0.72
    if row.get("willing_to_relocate"):
        return 0.70
    return 0.35


def enrich_row(row: dict, spec: dict) -> None:
    """Apply rank-time bonuses/penalties from fields already in features.parquet."""
    blob = _terms_blob(row)
    rt = spec.get("rank_time") or {}

    eval_score = _term_hits(blob, [str(x) for x in rt.get("eval_evidence_terms", [])])
    shipper_score = _term_hits(blob, [str(x) for x in rt.get("shipper_terms", [])])
    hr_score = _term_hits(blob, [str(x) for x in rt.get("hr_tech_terms", [])], cap=2)

    row["rank_eval_score"] = eval_score
    row["rank_shipper_score"] = shipper_score
    row["rank_hr_tech_score"] = hr_score
    row["rank_location_tier"] = location_tier_score(row, spec)

    bonus = (
        float(rt.get("eval_weight", 0.04)) * eval_score
        + float(rt.get("shipper_weight", 0.03)) * shipper_score
        + float(rt.get("hr_tech_weight", 0.02)) * hr_score
        + float(rt.get("location_tier_weight", 0.03)) * row["rank_location_tier"]
    )

    title = str(row.get("current_title") or "").lower()
    if any(x in title for x in ("director", "architect", "head of", "vp ", "vice president")):
        if _term_hits(blob, ["production", "shipped", "deployed", "serving", "real users"]) < 0.34:
            row["anti_pattern_penalty"] = min(1.0, float(row.get("anti_pattern_penalty") or 0) + 0.15)

    row["rank_time_bonus"] = min(0.12, bonus)


def _days_since_active(last_active: object) -> int | None:
    if not last_active:
        return None
    try:
        dt = datetime.fromisoformat(str(last_active).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except (TypeError, ValueError):
        return None


def eligible_for_rank_band(row: dict, rank_cap: int, spec: dict) -> bool:
    """Soft availability guard for upper ranks without rebuilding features."""
    guard = spec.get("top_rank_availability_guard") or {}
    if not guard.get("enabled", True):
        return True

    max_rank = int(guard.get("max_rank", 25))
    if rank_cap > max_rank:
        return True

    days = _days_since_active(row.get("last_active_date"))
    response = float(row.get("recruiter_response_rate") or 0)
    career = float(row.get("career_evidence") or 0)
    strong_career = float(guard.get("strong_career_override", 0.62))

    if career >= strong_career:
        return True
    stale_days = int(guard.get("stale_days", 180))
    min_response = float(guard.get("min_response_rate", 0.15))
    if days is not None and days > stale_days and response < min_response:
        return False
    if response < float(guard.get("hard_min_response", 0.08)):
        return False
    return True
