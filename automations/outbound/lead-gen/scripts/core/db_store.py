import json
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


LEGACY_ROW_TABLE = "nightfall_csv_rows"
LEGACY_HEADER_TABLE = "nightfall_csv_headers"
ORGANISATIONS_TABLE = "organisations"
ROW_KEY_COLUMN = "nightfall_row_key"
ROW_INDEX_COLUMN = "nightfall_row_index"
UPDATED_AT_COLUMN = "nightfall_updated_at"
ORGANISATION_ID_COLUMN = "organisation_id"
OLD_INTERNAL_COLUMN_MAP = {
    "_nightfall_row_key": ROW_KEY_COLUMN,
    "_nightfall_row_index": ROW_INDEX_COLUMN,
    "_nightfall_updated_at": UPDATED_AT_COLUMN,
}
INTERNAL_COLUMNS = {ROW_KEY_COLUMN, ROW_INDEX_COLUMN, UPDATED_AT_COLUMN}
SYSTEM_TABLES = {LEGACY_ROW_TABLE, LEGACY_HEADER_TABLE, ORGANISATIONS_TABLE}
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


def default_organisation_id() -> int:
    value = (os.environ.get("NIGHTFALL_ORGANISATION_ID") or os.environ.get("VESRA_ORGANISATION_ID") or "1").strip()
    try:
        return int(value)
    except ValueError:
        return 1


def default_organisation_name() -> str:
    return (os.environ.get("NIGHTFALL_ORGANISATION_NAME") or os.environ.get("VESRA_ORGANISATION_NAME") or "vesra").strip() or "vesra"


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
    value = "|".join(part for part in parts if part) or f"{index:08d}"
    organisation_id = str(row.get(ORGANISATION_ID_COLUMN) or default_organisation_id()).strip() or "1"
    return f"{organisation_id}|{value}"[:191]


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
        ensure_base_schema(conn)
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


def ensure_base_schema(conn) -> None:
    _, _, text = load_sqlalchemy()
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {quote_identifier(ORGANISATIONS_TABLE)} (
              id INTEGER NOT NULL PRIMARY KEY,
              organisation_name VARCHAR(191) NOT NULL UNIQUE,
              created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    organisation_id = default_organisation_id()
    organisation_name = default_organisation_name()
    existing = conn.execute(
        text(f"SELECT id FROM {quote_identifier(ORGANISATIONS_TABLE)} WHERE id = :id"),
        {"id": organisation_id},
    ).first()
    if not existing:
        conn.execute(
            text(
                f"""
                INSERT INTO {quote_identifier(ORGANISATIONS_TABLE)} (id, organisation_name)
                VALUES (:id, :organisation_name)
                """
            ),
            {"id": organisation_id, "organisation_name": organisation_name},
        )


def rename_legacy_internal_columns(conn, dataset: str) -> None:
    _, _, text = load_sqlalchemy()
    columns = set(current_columns(conn, dataset))
    for old_name, new_name in OLD_INTERNAL_COLUMN_MAP.items():
        if old_name in columns and new_name not in columns:
            conn.execute(
                text(
                    f"ALTER TABLE {quote_identifier(dataset)} RENAME COLUMN "
                    f"{quote_identifier(old_name)} TO {quote_identifier(new_name)}"
                )
            )
            columns.remove(old_name)
            columns.add(new_name)


def ensure_dataset_table(conn, dataset: str, headers: list[str]) -> None:
    _, _, text = load_sqlalchemy()
    table = quote_identifier(dataset)
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {table} (
              {quote_identifier(ROW_KEY_COLUMN)} VARCHAR(191) NOT NULL,
              {quote_identifier(ROW_INDEX_COLUMN)} INTEGER NOT NULL,
              {quote_identifier(ORGANISATION_ID_COLUMN)} INTEGER NOT NULL DEFAULT 1,
              {quote_identifier(UPDATED_AT_COLUMN)} TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY ({quote_identifier(ROW_KEY_COLUMN)})
            )
            """
        )
    )
    rename_legacy_internal_columns(conn, dataset)
    existing = set(current_columns(conn, dataset))
    if ORGANISATION_ID_COLUMN not in existing:
        conn.execute(
            text(
                f"ALTER TABLE {table} ADD COLUMN {quote_identifier(ORGANISATION_ID_COLUMN)} "
                f"INTEGER NOT NULL DEFAULT {default_organisation_id()}"
            )
        )
        existing.add(ORGANISATION_ID_COLUMN)
    for internal_name, definition in (
        (ROW_KEY_COLUMN, "VARCHAR(191)"),
        (ROW_INDEX_COLUMN, "INTEGER"),
        (UPDATED_AT_COLUMN, "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
    ):
        if internal_name not in existing:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {quote_identifier(internal_name)} {definition}"))
            existing.add(internal_name)
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
        ensure_dataset_table(conn, dataset, [])
        columns = user_columns(conn, dataset)
        if not columns:
            return []
        select_columns = ", ".join(quote_identifier(column) for column in columns)
        result = conn.execute(
            text(
                f"""
                SELECT {select_columns}
                FROM {quote_identifier(dataset)}
                ORDER BY {quote_identifier(ROW_INDEX_COLUMN)} ASC, {quote_identifier(ROW_KEY_COLUMN)} ASC
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
    inferred_headers = sorted({key for row in rows for key in row})
    clean_headers = normalized_headers(headers or inferred_headers)
    if ORGANISATION_ID_COLUMN not in clean_headers:
        clean_headers.append(ORGANISATION_ID_COLUMN)
    clean_rows = [
        {
            header: str(row.get(header, default_organisation_id() if header == ORGANISATION_ID_COLUMN else "") or "")
            for header in clean_headers
        }
        for row in rows
    ]
    with connection() as conn:
        ensure_dataset_table(conn, dataset, clean_headers)
        conn.execute(text(f"DELETE FROM {quote_identifier(dataset)}"))
        if not clean_rows:
            return
        keys = unique_row_keys(dataset, clean_rows)
        data_columns = [ROW_KEY_COLUMN, ROW_INDEX_COLUMN, *clean_headers]
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
                    ROW_KEY_COLUMN: keys[index],
                    ROW_INDEX_COLUMN: index,
                    **row,
                }
                for index, row in enumerate(clean_rows)
            ],
        )


def append_row(path: Path, row: dict[str, str], headers: list[str]) -> None:
    rows = read_rows(path)
    clean_headers = normalized_headers(headers)
    if ORGANISATION_ID_COLUMN not in clean_headers:
        clean_headers.append(ORGANISATION_ID_COLUMN)
    rows.append(
        {
            header: row.get(header, str(default_organisation_id()) if header == ORGANISATION_ID_COLUMN else "")
            for header in clean_headers
        }
    )
    write_rows(path, rows, clean_headers)


def list_datasets() -> list[str]:
    with connection() as conn:
        names = inspector(conn).get_table_names()
    return sorted(
        name
        for name in names
        if name not in SYSTEM_TABLES
        and not name.startswith("mysql")
    )


def read_headers(dataset: str) -> list[str]:
    with connection() as conn:
        if table_exists(conn, dataset):
            ensure_dataset_table(conn, dataset, [])
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


def migrate_current_tables() -> list[str]:
    migrated: list[str] = []
    with connection() as conn:
        names = sorted(
            name
            for name in inspector(conn).get_table_names()
            if name not in SYSTEM_TABLES and not name.startswith("mysql")
        )
        for dataset in names:
            ensure_dataset_table(conn, dataset, [])
            migrated.append(dataset)
    return migrated
