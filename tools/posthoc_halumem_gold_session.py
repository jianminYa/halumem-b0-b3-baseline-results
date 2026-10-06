#!/usr/bin/env python3
"""Post-hoc gold-session audit for HaluMem retrieval artifacts.

The native HaluMem adapter currently expects evidence strings such as ``D1:3``
while the cleaned HaluMem files store evidence as dictionaries containing
``memory_content``.  That mismatch makes the native ``target_boxes`` field
empty.  This script does not rerun retrieval or call an API.  It maps each
gold evidence memory to the most lexically compatible raw conversation session
and evaluates the already recorded block ranking by session coverage.

The output is explicitly an audit estimate, not a replacement for a dataset
official retrieval label.  Unresolved evidence is reported separately rather
than silently counted as a hit or a miss.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-/:][a-z0-9]+)*", re.IGNORECASE)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for",
    "from", "has", "have", "he", "her", "his", "i", "in", "is", "it",
    "its", "of", "on", "or", "she", "that", "the", "their", "them",
    "there", "these", "this", "to", "was", "were", "with", "you", "your",
    "user", "assistant", "memory", "information", "says", "said", "states",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def tokens(value: Any) -> set[str]:
    result: set[str] = set()
    for token in TOKEN_RE.findall(str(value or "").lower()):
        token = token.strip("-/: ")
        if token and token not in STOPWORDS and (len(token) > 1 or token.isdigit()):
            result.add(token)
    return result


def lexical_score(gold: str, candidate: str) -> float:
    return lexical_token_score(tokens(gold), tokens(candidate))


def lexical_token_score(gold_tokens: set[str], candidate_tokens: set[str]) -> float:
    if not gold_tokens or not candidate_tokens:
        return 0.0
    overlap = len(gold_tokens & candidate_tokens)
    containment = overlap / len(gold_tokens)
    union = len(gold_tokens | candidate_tokens)
    jaccard = overlap / union if union else 0.0
    return 0.7 * containment + 0.3 * jaccard


def conversation_sessions(user: dict[str, Any]) -> dict[str, str]:
    conversation = user.get("conversation") or {}
    result: dict[str, str] = {}
    for key, value in conversation.items():
        if not (str(key).startswith("session_") and isinstance(value, list)):
            continue
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(f"{item.get('speaker', '')}: {item.get('text', '')}")
        result[str(key)] = "\n".join(parts)
    return result


def map_evidence_to_sessions(evidence: list[dict[str, Any]], sessions: dict[str, set[str]]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for item in evidence:
        content = str(item.get("memory_content") or "").strip()
        gold_tokens = tokens(content)
        scored = sorted(((lexical_token_score(gold_tokens, value), sid) for sid, value in sessions.items()), reverse=True)
        best_score = scored[0][0] if scored else 0.0
        # Keep near-ties because repeated persona facts may legitimately occur
        # in more than one session.  A low score is unresolved, not a guessed
        # session assignment.
        selected = [sid for score, sid in scored if score >= 0.25 and score >= best_score - 0.04]
        mapped.append({
            "memory_content": content,
            "memory_type": item.get("memory_type"),
            "candidate_sessions": selected,
            "best_score": best_score,
            "resolved": bool(selected),
        })
    return mapped


def evaluate_variant(root: Path, combined: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    qa_map: dict[tuple[str, int], dict[str, Any]] = {}
    sessions_map: dict[str, dict[str, str]] = {}
    for user in combined:
        uid = str(user.get("user_id", ""))
        sessions_map[uid] = {sid: tokens(text) for sid, text in conversation_sessions(user).items()}
        for idx, qa in enumerate(user.get("qa", []) or []):
            qa_map[(uid, idx)] = qa

    boxes_by_user: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    for box in read_jsonl(root / "final_boxes_content.jsonl"):
        boxes_by_user[str(box.get("user_id"))][int(box.get("block_id", 0))] = box

    details: list[dict[str, Any]] = []
    rows = read_jsonl(root / "simple_retrieval.jsonl")
    for row in rows:
        uid = str(row.get("user_id", ""))
        idx = int(row.get("qa_idx", 0))
        qa = qa_map.get((uid, idx), {})
        evidence = qa.get("evidence") or []
        mapped = map_evidence_to_sessions(evidence, sessions_map.get(uid, {})) if evidence else []
        gold_sessions = sorted({sid for item in mapped for sid in item["candidate_sessions"]})
        ranking = ((row.get("rankings") or {}).get("content_event_topic_kw") or [])
        rank = None
        rank_block = None
        if gold_sessions:
            for position, block_id in enumerate(ranking, start=1):
                box = boxes_by_user.get(uid, {}).get(int(block_id), {})
                session_id = str((box.get("coverage") or {}).get("session_id", ""))
                if session_id in gold_sessions:
                    rank = position
                    rank_block = int(block_id)
                    break
        details.append({
            "user_id": uid,
            "qa_idx": idx,
            "question": row.get("question"),
            "evidence_count": len(evidence),
            "gold_sessions": gold_sessions,
            "evidence_mapping": mapped,
            "gold_rank": rank,
            "gold_block_id": rank_block,
            "resolved": bool(gold_sessions),
        })

    eligible = [row for row in details if row["evidence_count"]]
    resolved = [row for row in eligible if row["resolved"]]
    summary: dict[str, Any] = {
        "queries": len(details),
        "queries_with_evidence": len(eligible),
        "queries_with_resolved_gold_session": len(resolved),
        "queries_with_unresolved_gold_session": len(eligible) - len(resolved),
        "hit_rate_all_evidence_queries": {},
        "hit_rate_resolved_evidence_queries": {},
        "mrr_all_evidence_queries": 0.0,
        "mrr_resolved_evidence_queries": 0.0,
        "mean_gold_rank_resolved": None,
    }
    for denominator_name, population in (
        ("all_evidence_queries", eligible),
        ("resolved_evidence_queries", resolved),
    ):
        ranks = [int(row["gold_rank"]) for row in population if row["gold_rank"] is not None]
        summary[f"hit_rate_{denominator_name}"] = {
            f"hit@{k}": sum(rank <= k for rank in ranks) / len(population) if population else 0.0
            for k in (1, 5, 10, 20)
        }
        summary[f"mrr_{denominator_name}"] = (
            sum(1.0 / rank for rank in ranks) / len(population) if population else 0.0
        )
        if denominator_name == "resolved_evidence_queries" and ranks:
            summary["mean_gold_rank_resolved"] = statistics.mean(ranks)
    return summary, details


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--combined", type=Path, required=True)
    parser.add_argument("--variant-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    combined = read_json(args.combined)
    summary, details = evaluate_variant(args.variant_root, combined)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"summary": summary, "details": details}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
