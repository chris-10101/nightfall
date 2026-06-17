import json
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


LEGACY_ROW_TABLE = "nightfall_csv_rows"
LEGACY_HEADER_TABLE = "nightfall_csv_headers"
INTERNAL_COLUMNS = {"_nightfall_row_key", "_nightfall_row_index", "_nightfall_updated_at"}
IDENTIFIER_RE = re.compile(r"[^a-zA-Z0-9_]+")


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
    return safe_identifier(path.stem.strip().lower().replace("-", "_"), fallback="dataset")


def safe_identifier(value: str, *, fallback: str = "field") -> str:
    clean = IDENTIFIER_RE.sub("_", str(value or "").strip()).strip("_").lower()
    if not clean:
        clean = fallback
    if clean[0].isdigit():
        clean = f"{fallback}_{clean}"
    return clean[:60]


def quote_identifier(value: str) -> str:
    return "`" + value.replace("`", "``") + "`"


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
        from sqlalchemy import create_engine, inspect, text
    except ImportError as exc:
        raise RuntimeError(
            "Database storage requires SQLAlchemy. Install the outbound package dependencies first."
        ) from exc
    return create_engine, inspect, text


def engine():
    create_engine, _, _ = load_sqlalchemy()
    return create_engine(database_url(), pool_pre_ping=True, future=True)


@contextmanager
def connection() -> Iterator:
    db_engine = engine()
    with db_engine.begin() as conn:
        yield conn


def inspector(conn):
    _, inspect, _ = load_sqlalchemy()
    return inspect(conn)


def table_exists(conn, table: str) -> bool:
    return inspector(conn).has_table(table)


def current_columns(conn, table: str) -> list[str]:
    return [column["name"] for column in inspector(conn).get_columns(table)]


def user_columns(conn, table: str) -> list[str]:
    return [column for column in current_columns(conn, table) if column not in INTERNAL_COLUMNS]


def ensure_dataset_table(conn, dataset: str, headers: list[str]) -> None:
    _, _, text = load_sqlalchemy()
    table = quote_identifier(dataset)
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {table} (
              _nightfall_row_key VARCHAR(191) NOT NULL,
              _nightfall_row_index INTEGER NOT NULL,
              _nightfall_updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (_nightfall_row_key)
            )
            """
        )
    )
    existing = set(current_columns(conn, dataset))
    for header in normalized_headers(headers):
        if header in INTERNAL_COLUMNS or header in existing:
            continue
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {quote_identifier(header)} TEXT"))
        existing.add(header)


def normalized_headers(headers: list[str]) -> list[str]:
    clean_headers: list[str] = []
    seen: set[str] = set()
    for header in headers:
        clean = safe_identifier(header)
        if clean in INTERNAL_COLUMNS or clean in seen:
            suffix = 2
            base = clean[:55]
            while f"{base}_{suffix}" in seen or f"{base}_{suffix}" in INTERNAL_COLUMNS:
                suffix += 1
            clean = f"{base}_{suffix}"
        seen.add(clean)
        clean_headers.append(clean)
    return clean_headers


def read_rows(path: Path) -> list[dict[str, str]]:
    _, _, text = load_sqlalchemy()
    dataset = dataset_name(path)
    with connection() as conn:
        if not table_exists(conn, dataset):
            legacy_rows = read_legacy_rows(conn, dataset)
            return legacy_rows
        columns = user_columns(conn, dataset)
        if not columns:
            return []
        select_columns = ", ".join(quote_identifier(column) for column in columns)
        result = conn.execute(
            text(
                f"""
                SELECT {select_columns}
                FROM {quote_identifier(dataset)}
                ORDER BY _nightfall_row_index ASC, _nightfall_row_key ASC
                """
            )
        )
        rows = []
        for item in result.mappings():
            rows.append({column: str(item.get(column) or "") for column in columns})
        return rows


def write_rows(path: Path, rows: list[dict[str, str]], headers: list[str]) -> None:
    _, _, text = load_sqlalchemy()
    dataset = dataset_name(path)
    clean_headers = normalized_headers(headers or sorted({key for row in rows for key in row}))
    clean_rows = [
        {header: str(row.get(header, "") or "") for header in clean_headers}
        for row in rows
    ]
    with connection() as conn:
        ensure_dataset_table(conn, dataset, clean_headers)
        conn.execute(text(f"DELETE FROM {quote_identifier(dataset)}"))
        if not clean_rows:
            return
        keys = unique_row_keys(dataset, clean_rows)
        data_columns = ["_nightfall_row_key", "_nightfall_row_index", *clean_headers]
        column_sql = ", ".join(quote_identifier(column) for column in data_columns)
        value_sql = ", ".join(f":{column}" for column in data_columns)
        statement = text(
            f"""
            INSERT INTO {quote_identifier(dataset)} ({column_sql})
            VALUES ({value_sql})
            """
        )
        conn.execute(
            statement,
            [
                {
                    "_nightfall_row_key": keys[index],
                    "_nightfall_row_index": index,
                    **row,
                }
                for index, row in enumerate(clean_rows)
            ],
        )


def append_row(path: Path, row: dict[str, str], headers: list[str]) -> None:
    rows = read_rows(path)
    clean_headers = normalized_headers(headers)
    rows.append({header: row.get(header, "") for header in clean_headers})
    write_rows(path, rows, clean_headers)


def list_datasets() -> list[str]:
    with connection() as conn:
        names = inspector(conn).get_table_names()
    return sorted(
        name
        for name in names
        if name not in {LEGACY_ROW_TABLE, LEGACY_HEADER_TABLE}
        and not name.startswith("mysql")
    )


def read_headers(dataset: str) -> list[str]:
    with connection() as conn:
        if table_exists(conn, dataset):
            return user_columns(conn, dataset)
        return read_legacy_headers(conn, dataset)


def read_legacy_headers(conn, dataset: str) -> list[str]:
    _, _, text = load_sqlalchemy()
    if not table_exists(conn, LEGACY_HEADER_TABLE):
        return []
    row = conn.execute(
        text(f"SELECT headers_json FROM {quote_identifier(LEGACY_HEADER_TABLE)} WHERE dataset = :dataset"),
        {"dataset": dataset},
    ).first()
    return json.loads(row.headers_json) if row else []


def read_legacy_rows(conn, dataset: str) -> list[dict[str, str]]:
    _, _, text = load_sqlalchemy()
    if not table_exists(conn, LEGACY_ROW_TABLE):
        return []
    result = conn.execute(
        text(
            f"""
            SELECT data_json
            FROM {quote_identifier(LEGACY_ROW_TABLE)}
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


def legacy_datasets() -> list[tuple[str, list[str]]]:
    _, _, text = load_sqlalchemy()
    with connection() as conn:
        if not table_exists(conn, LEGACY_HEADER_TABLE):
            return []
        rows = conn.execute(
            text(f"SELECT dataset, headers_json FROM {quote_identifier(LEGACY_HEADER_TABLE)} ORDER BY dataset ASC")
        )
        return [(row.dataset, json.loads(row.headers_json)) for row in rows]


def migrate_legacy_tables(*, drop_legacy: bool = False) -> list[tuple[str, int]]:
    migrated: list[tuple[str, int]] = []
    for dataset, headers in legacy_datasets():
        path = Path(f"{dataset}.csv")
        with connection() as conn:
            rows = read_legacy_rows(conn, dataset)
        write_rows(path, rows, headers)
        migrated.append((dataset, len(rows)))
    if drop_legacy and migrated:
        _, _, text = load_sqlalchemy()
        with connection() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {quote_identifier(LEGACY_ROW_TABLE)}"))
            conn.execute(text(f"DROP TABLE IF EXISTS {quote_identifier(LEGACY_HEADER_TABLE)}"))
    return migrated
