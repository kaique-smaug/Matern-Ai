import json
from pathlib import Path


def test_chunk_ids_are_unique() -> None:
    path = Path(__file__).resolve().parents[1] / "data" / "chunks.jsonl"
    ids = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                ids.append(json.loads(line)["id"])
    assert len(ids) == 2771
    assert len(ids) == len(set(ids))
