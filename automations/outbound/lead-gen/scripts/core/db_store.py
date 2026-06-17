import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


ROW_TABLE = "nightfall_csv_rows"
HEADER_TABLE = "nightfall_csv_headers"


def database_enabled() -> bool:
    backend = (
        os.environ.get("NIGHTFALL_STORAGE_BACKEND")
        or os.environ.get("VESRA_STORAGE_BACKEND")
        or ""
    ).strip().lower()
    return backend in {"db", "database", "mysql"}


def database_url() -> str:
    value = (os.environ.get("DATABASE_URL") or "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL is required when database storage is enabled.")
    return value


def dataset_name(path: Path) -> str:
    return path.stem.strip().lower().replace("-", "_")


def row_key(dataset: str, row: dict[str, str], index: int) -> str:
    preferred_keys = {
        "prospects": ("lead_id", "email", "company_domain", "company_name"),
        "campaign_queue": ("lead_id", "email", "company_domain", "company_name"),
        "suppression": ("email", "domain", "company_name"),
        "reply_events": ("message_id", "received_at", "sender"),
        "agent_events": ("event_id", "lead_id", "created_at"),
        "test_campaign_state": ("step", "recipient"),
    }
    parts = [row.get(key, "").strip().lower() for key in preferred_keys.get(dataset, ())]
    value = "|".join(part for part in parts if part)
    if value:
        return value[:191]
    return f"{index:08d}"


def unique_row_keys(dataset: str, rows: list[dict[str, str]]) -> list[str]:
    counts: dict[str, int] = {}
    keys = []
    for index, row in enumerate(rows):
        base_key = row_key(dataset, row, index)
        count = counts.get(base_key, 0)
        counts[base_key] = count + 1
        if count == 0:
            keys.append(base_key)
            continue
        suffix = f"#{count + 1}"
        keys.append(f"{base_key[: 191 - len(suffix)]}{suffix}")
    return keys


def load_sqlalchemy():
    try:
        from sqlalchemy import create_engine, text
    except ImportError as exc:
        raise RuntimeError(
            "Database storage requires SQLAlchemy. Install the outbound package dependencies first."
        ) from exc
    return create_engine, text


def engine():
    create_engine, _ = load_sqlalchemy()
    return create_engine(database_url(), pool_pre_ping=True, future=True)


@contextmanager
def connection() -> Iterator:
    db_engine = engine()
    with db_engine.begin() as conn:
        ensure_schema(conn)
        yield conn


def ensure_schema(conn) -> None:
    _, text = load_sqlalchemy()
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {HEADER_TABLE} (
              dataset VARCHAR(191) PRIMARY KEY,
              headers_json TEXT NOT NULL,
              updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {ROW_TABLE} (
              dataset VARCHAR(191) NOT NULL,
              row_key VARCHAR(191) NOT NULL,
              row_index INTEGER NOT NULL,
              data_json TEXT NOT NULL,
              updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (dataset, row_key)
            )
            """
        )
    )


def read_rows(path: Path) -> list[dict[str, str]]:
    _, text = load_sqlalchemy()
    dataset = dataset_name(path)
    with connection() as conn:
        result = conn.execute(
            text(
                f"""
                SELECT data_json
                FROM {ROW_TABLE}
                WHERE dataset = :dataset
                ORDER BY row_index ASC, row_key ASC
                """
            ),
            {"dataset": dataset},
        )
        rows = []
        for item in result:
            payload = json.loads(item.data_json)
            rows.append({str(key): str(value or "") for key, value in payload.items()})
        return rows


def write_rows(path: Path, rows: list[dict[str, str]], headers: list[str]) -> None:
    _, text = load_sqlalchemy()
    dataset = dataset_name(path)
    clean_headers = [str(header) for header in headers]
    clean_rows = [
        {header: str(row.get(header, "") or "") for header in clean_headers}
        for row in rows
    ]
    with connection() as conn:
        conn.execute(text(f"DELETE FROM {ROW_TABLE} WHERE dataset = :dataset"), {"dataset": dataset})
        conn.execute(text(f"DELETE FROM {HEADER_TABLE} WHERE dataset = :dataset"), {"dataset": dataset})
        conn.execute(
            text(
                f"""
                INSERT INTO {HEADER_TABLE} (dataset, headers_json)
                VALUES (:dataset, :headers_json)
                """
            ),
            {"dataset": dataset, "headers_json": json.dumps(clean_headers)},
        )
        if not clean_rows:
            return
        keys = unique_row_keys(dataset, clean_rows)
        conn.execute(
            text(
                f"""
                INSERT INTO {ROW_TABLE} (dataset, row_key, row_index, data_json)
                VALUES (:dataset, :row_key, :row_index, :data_json)
                """
            ),
            [
                {
                    "dataset": dataset,
                    "row_key": keys[index],
                    "row_index": index,
                    "data_json": json.dumps(row, sort_keys=True),
                }
                for index, row in enumerate(clean_rows)
            ],
        )


def append_row(path: Path, row: dict[str, str], headers: list[str]) -> None:
    rows = read_rows(path)
    rows.append({header: row.get(header, "") for header in headers})
    write_rows(path, rows, headers)
