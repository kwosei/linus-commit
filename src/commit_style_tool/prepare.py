from __future__ import annotations

from collections import Counter
from pathlib import Path

from .types import CommitRecord, StageResult
from .utils import read_jsonl, write_json, write_jsonl


def _normalize_subject(subject: str) -> str:
    return " ".join(subject.strip().split())


def _normalize_body(body: str) -> str:
    lines = [line.rstrip() for line in body.splitlines()]
    # collapse repeated empty lines while preserving paragraph breaks
    normalized: list[str] = []
    previous_blank = False
    for line in lines:
        blank = line.strip() == ""
        if blank and previous_blank:
            continue
        normalized.append(line)
        previous_blank = blank
    return "\n".join(normalized).strip()


def prepare_dataset(
    input_path: Path,
    output_path: Path,
    summary_path: Path,
    drop_merges: bool = True,
    drop_reverts: bool = False,
) -> StageResult:
    seen_hashes: set[str] = set()
    prepared: list[CommitRecord] = []

    summary_counter: Counter[str] = Counter()
    for raw in read_jsonl(input_path):
        summary_counter["total_rows"] += 1
        commit = CommitRecord.from_dict(raw)

        if not commit.hash or commit.hash in seen_hashes:
            summary_counter["deduped"] += 1
            continue
        seen_hashes.add(commit.hash)

        if drop_merges and commit.is_merge:
            summary_counter["dropped_merges"] += 1
            continue
        if drop_reverts and commit.is_revert:
            summary_counter["dropped_reverts"] += 1
            continue

        commit.subject = _normalize_subject(commit.subject)
        commit.body = _normalize_body(commit.body)
        commit.trailers = {
            key.strip(): [value.strip() for value in values if value.strip()]
            for key, values in commit.trailers.items()
            if key.strip()
        }

        if not commit.subject:
            summary_counter["dropped_empty_subject"] += 1
            continue

        summary_counter["kept"] += 1
        prepared.append(commit)

    kept_count = write_jsonl(output_path, (item.to_dict() for item in prepared))
    write_json(
        summary_path,
        {
            "input_path": str(input_path),
            "output_path": str(output_path),
            "drop_merges": drop_merges,
            "drop_reverts": drop_reverts,
            "stats": dict(summary_counter),
        },
    )

    return StageResult(
        path=str(output_path),
        record_count=kept_count,
        metadata={"summary_path": str(summary_path), "stats": dict(summary_counter)},
    )
