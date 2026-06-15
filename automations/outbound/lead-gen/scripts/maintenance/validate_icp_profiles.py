from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = BASE_DIR / "config" / "icp_profiles.json"

REQUIRED_TOP_LEVEL_KEYS = [
    "active",
    "label",
    "campaign_name",
    "segments",
    "target_count",
    "criteria",
    "operational_challenges",
    "why_good",
    "ideal_size",
    "sweet_spot",
    "target_verticals",
    "mission",
    "core_value_proposition",
    "outcomes",
    "belief",
    "required_terms_any",
    "positive_terms",
    "exclude_terms",
    "decision_maker_roles",
    "discovery",
    "outreach",
]

REQUIRED_DISCOVERY_KEYS = [
    "countries",
    "regions",
    "cities",
    "verticals",
    "query_templates",
]

REQUIRED_OUTREACH_KEYS = [
    "subject",
    "short_reason",
    "detail",
    "body_template",
]


def require_keys(name: str, value: dict, keys: list[str]) -> list[str]:
    return [f"{name}: missing {key}" for key in keys if key not in value]


def main() -> None:
    profiles = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    errors = []
    for key, profile in profiles.items():
        errors.extend(require_keys(key, profile, REQUIRED_TOP_LEVEL_KEYS))
        discovery = profile.get("discovery", {})
        outreach = profile.get("outreach", {})
        errors.extend(require_keys(f"{key}.discovery", discovery, REQUIRED_DISCOVERY_KEYS))
        errors.extend(require_keys(f"{key}.outreach", outreach, REQUIRED_OUTREACH_KEYS))
        if not profile.get("segments"):
            errors.append(f"{key}: segments must not be empty")
        if not profile.get("required_terms_any"):
            errors.append(f"{key}: required_terms_any must not be empty")
        if not discovery.get("query_templates"):
            errors.append(f"{key}.discovery: query_templates must not be empty")

    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)

    print(f"Validated {len(profiles)} ICP profiles with consistent schema.")


if __name__ == "__main__":
    main()
