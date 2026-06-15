from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import re
from collections import Counter

from core.paths import kb_dir


def tokenize(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 2]


def chunks(path: Path, text: str) -> list[dict[str, str]]:
    parts = re.split(r"\n(?=#{1,3}\s+)", text)
    output = []
    for index, part in enumerate(parts):
        clean = part.strip()
        if not clean:
            continue
        title = clean.splitlines()[0].strip("# ").strip() if clean.splitlines() else path.stem
        output.append(
            {
                "path": str(path),
                "chunk_id": f"{path.name}:{index}",
                "title": title,
                "text": clean[:2000],
            }
        )
    return output


def score(query_terms: Counter, text: str) -> int:
    terms = Counter(tokenize(text))
    return sum(min(count, terms.get(term, 0)) for term, count in query_terms.items())


def retrieve(query: str, limit: int) -> list[dict[str, str | int]]:
    root = kb_dir()
    query_terms = Counter(tokenize(query))
    results = []
    for path in sorted(root.rglob("*.md")):
        for chunk in chunks(path, path.read_text(encoding="utf-8", errors="replace")):
            value = score(query_terms, f"{chunk['title']} {chunk['text']}")
            if value <= 0:
                continue
            results.append({**chunk, "score": value})
    results.sort(key=lambda item: (-int(item["score"]), str(item["path"]), str(item["chunk_id"])))
    return results[:limit]


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieve relevant markdown KB snippets.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps({"query": args.query, "results": retrieve(args.query, args.limit)}, indent=2))


if __name__ == "__main__":
    main()
