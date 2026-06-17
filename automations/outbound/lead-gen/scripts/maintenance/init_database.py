from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.db_store import connection, database_url


def masked_database_url() -> str:
    value = database_url()
    if "@" not in value or "://" not in value:
        return "[configured]"
    scheme, rest = value.split("://", 1)
    return f"{scheme}://***@{rest.rsplit('@', 1)[-1]}"


def main() -> None:
    with connection():
        pass
    print(f"Database schema is ready: {masked_database_url()}")


if __name__ == "__main__":
    main()
