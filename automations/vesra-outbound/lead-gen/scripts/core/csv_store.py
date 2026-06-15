import csv
import os
import time
from contextlib import contextmanager
from pathlib import Path


LOCK_TIMEOUT_SECONDS = 30
LOCK_POLL_SECONDS = 0.1


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        return list(csv.DictReader(csv_file))


def write_csv_atomic(path: Path, rows: list[dict[str, str]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path):
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with tmp_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_path, path)


def append_csv_atomic(path: Path, row: dict[str, str], headers: list[str]) -> None:
    rows = read_csv(path)
    rows.append({header: row.get(header, "") for header in headers})
    write_csv_atomic(path, rows, headers)


@contextmanager
def file_lock(path: Path):
    lock_path = path.with_suffix(path.suffix + ".lock")
    start = time.monotonic()
    fd = None
    while fd is None:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("ascii"))
        except FileExistsError:
            if time.monotonic() - start > LOCK_TIMEOUT_SECONDS:
                raise TimeoutError(f"Timed out waiting for CSV lock: {lock_path}")
            time.sleep(LOCK_POLL_SECONDS)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
