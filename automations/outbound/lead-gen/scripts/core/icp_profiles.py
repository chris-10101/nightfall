import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = BASE_DIR / "config" / "icp_profiles.json"


def normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower().replace("-", " "))


@lru_cache(maxsize=1)
def load_profiles() -> dict[str, dict[str, Any]]:
    with CONFIG_PATH.open(encoding="utf-8") as config_file:
        return json.load(config_file)


def active_profiles() -> dict[str, dict[str, Any]]:
    return {key: profile for key, profile in load_profiles().items() if profile.get("active")}


def active_segments() -> set[str]:
    segments = set()
    for profile in active_profiles().values():
        segments.update(normalize(segment) for segment in profile.get("segments", []))
    return segments


def profile_for_segment(segment: str) -> tuple[str, dict[str, Any]] | tuple[str, None]:
    normalized_segment = normalize(segment)
    for key, profile in active_profiles().items():
        if normalized_segment in {normalize(value) for value in profile.get("segments", [])}:
            return key, profile
    return "", None


def profile_for_row(row: dict[str, Any]) -> tuple[str, dict[str, Any]] | tuple[str, None]:
    return profile_for_segment(str(row.get("segment", "")))


def is_active_segment(segment: str) -> bool:
    return normalize(segment) in active_segments()


def text_haystack(row: dict[str, Any]) -> str:
    fields = (
        "subtype",
        "company_name",
        "city_region",
        "website_url",
        "source",
        "source_url",
        "notes",
        "personalisation",
        "short_reason",
    )
    return normalize(" ".join(str(row.get(field, "")) for field in fields))


def profile_exclusion_hits(row: dict[str, Any]) -> list[str]:
    _, profile = profile_for_row(row)
    if not profile:
        return []
    haystack = text_haystack(row)
    return [term for term in profile.get("exclude_terms", []) if normalize(term) in haystack]


def profile_positive_score(row: dict[str, Any]) -> int:
    _, profile = profile_for_row(row)
    if not profile:
        return 0
    haystack = text_haystack(row)
    hits = {term for term in profile.get("positive_terms", []) if normalize(term) in haystack}
    return min(len(hits) * 5, 20)


def profile_required_signal(row: dict[str, Any]) -> bool:
    _, profile = profile_for_row(row)
    if not profile:
        return False
    required_terms = profile.get("required_terms_any", [])
    if not required_terms:
        return True
    haystack = text_haystack(row)
    return any(normalize(term) in haystack for term in required_terms)


def outreach_config(row: dict[str, Any]) -> dict[str, str]:
    _, profile = profile_for_row(row)
    if not profile:
        return {}
    return profile.get("outreach", {})


def campaign_name(row: dict[str, Any], fallback: str = "vesra_partner_program_v1") -> str:
    _, profile = profile_for_row(row)
    if not profile:
        return fallback
    return str(profile.get("campaign_name") or fallback)
