#!/usr/bin/env python3
"""Create the machine-readable aggregate for the published 10-user snapshot."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("b0", "b1", "b2", "b3")


def line_count(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def main() -> None:
    result = {
        "dataset": "HaluMem-Medium",
        "subset": "10-user evaluation snapshot",
        "configuration": {
            "llm_model": "gpt-4o-mini",
            "embedding_model": "text-embedding-3-small",
            "retrieval_top_k": 20,
            "qa_context_top_k": 20,
            "qa_repeats": 3,
        },
        "variants": {},
        "notes": [
            "Construction memory_units are published in full for every variant.",
            "Exact provider construction-token attribution is unavailable at subset level and is not fabricated.",
            "Retrieval metrics use the post-hoc gold-session audit because native target_boxes uses an incompatible evidence schema.",
        ],
    }
    for variant in VARIANTS:
        base = ROOT / "artifacts" / "10user" / variant
        qa = json.loads((base / "qa_summary.json").read_text(encoding="utf-8"))
        posthoc = json.loads((base / "retrieval_posthoc_gold_session.json").read_text(encoding="utf-8"))
        result["variants"][variant] = {
            "memory_units": line_count(base / "memory_units.jsonl"),
            "retrieval_rows": line_count(base / "retrieval_full.jsonl"),
            "qa_rows": line_count(base / "qa_results_3repeats.jsonl"),
            "qa": qa,
            "retrieval_posthoc_gold_session": posthoc["summary"],
        }
    output = ROOT / "reports" / "HALUMEM_10USER_RESULTS.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
