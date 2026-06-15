import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


def configured_dir(env_name: str, default: Path) -> Path:
    value = os.environ.get(env_name, "").strip()
    return Path(value).expanduser() if value else default


def config_dir() -> Path:
    return configured_dir("VESRA_LEAD_GEN_CONFIG_DIR", BASE_DIR / "config")


def data_dir() -> Path:
    return configured_dir("VESRA_LEAD_GEN_DATA_DIR", BASE_DIR / "data")


def reports_dir() -> Path:
    return configured_dir("VESRA_LEAD_GEN_REPORT_DIR", BASE_DIR / "reports" / "weekly")


def outreach_batches_dir() -> Path:
    return configured_dir("VESRA_LEAD_GEN_BATCH_DIR", BASE_DIR / "outreach" / "batches")


def orchestration_dir() -> Path:
    return configured_dir("VESRA_LEAD_GEN_ORCHESTRATION_DIR", BASE_DIR / "reports" / "orchestration")


def kb_dir() -> Path:
    return configured_dir("VESRA_LEAD_GEN_KB_DIR", BASE_DIR / "docs")
