from __future__ import annotations

import random
import re
from collections import Counter
from pathlib import Path

from .types import CommitRecord, StageResult
from .utils import iso_now, percentile, read_jsonl, write_json

PREFIX_RE = re.compile(r"^(?P<prefix>[A-Za-z0-9_./-]{2,40}):\s+(?P<rest>.+)$")
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_'-]*")

IMPERATIVE_VERBS = {
    "add",
    "adjust",
    "allow",
    "avoid",
    "block",
    "change",
    "clean",
    "cleanup",
    "convert",
    "disable",
    "drop",
    "enable",
    "extend",
    "extract",
    "fall",
    "fix",
    "handle",
    "improve",
    "introduce",
    "keep",
    "limit",
    "make",
    "mark",
    "merge",
    "move",
    "prevent",
    "refactor",
    "relax",
    "remove",
    "rename",
    "replace",
    "rework",
    "revert",
    "set",
    "simplify",
    "split",
    "stop",
    "switch",
    "tighten",
    "trim",
    "update",
    "use",
    "write",
}

RATIONALE_CUES = [
    "because",
    "otherwise",
    "so that",
    "to avoid",
    "in order to",
    "regression",
    "problem",
    "reason",
]
MECHANICS_CUES = [
    "rename",
    "refactor",
    "cleanup",
    "remove",
    "add",
    "update",
    "switch",
    "convert",
    "move",
    "drop",
]


def _stats(values: list[int]) -> dict[str, float | int]:
    if not values:
        return {
            "count": 0,
            "min": 0,
            "max": 0,
            "mean": 0.0,
            "median": 0.0,
            "p10": 0.0,
            "p90": 0.0,
        }
    ordered = sorted(values)
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
        "median": percentile(ordered, 50),
        "p10": percentile(ordered, 10),
        "p90": percentile(ordered, 90),
    }


def _extract_action_verb(subject: str) -> str:
    match = PREFIX_RE.match(subject.strip())
    candidate = match.group("rest") if match else subject
    tokens = TOKEN_RE.findall(candidate.lower())
    return tokens[0] if tokens else ""


def _choose_samples(commits: list[CommitRecord], seed: int = 42) -> list[dict]:
    if not commits:
        return []

    by_subject_len = sorted(commits, key=lambda c: len(c.subject))
    by_body_len = sorted(commits, key=lambda c: len(c.body))

    samples: list[CommitRecord] = []
    samples.append(by_subject_len[0])
    samples.append(by_subject_len[len(by_subject_len) // 2])
    samples.append(by_body_len[-1])

    prefixes: Counter[str] = Counter()
    by_hash = {commit.hash: commit for commit in commits}
    for commit in commits:
        match = PREFIX_RE.match(commit.subject)
        if match:
            prefixes[match.group("prefix")] += 1

    if prefixes:
        top_prefix = prefixes.most_common(1)[0][0]
        for commit in commits:
            match = PREFIX_RE.match(commit.subject)
            if match and match.group("prefix") == top_prefix:
                samples.append(commit)
                break

    random.seed(seed)
    sample_count = min(3, len(commits))
    for commit in random.sample(commits, sample_count):
        samples.append(commit)

    deduped: list[dict] = []
    seen: set[str] = set()
    for commit in samples:
        if commit.hash in seen:
            continue
        seen.add(commit.hash)
        deduped.append(
            {
                "hash": commit.hash,
                "subject": commit.subject,
                "body": commit.body,
                "trailers": commit.trailers,
                "files_changed": commit.files_changed,
                "additions": commit.additions,
                "deletions": commit.deletions,
            }
        )

    # Keep a consistent and concise sample set.
    return deduped[:8]


def analyze_commits(input_path: Path, output_path: Path) -> StageResult:
    commits = [CommitRecord.from_dict(row) for row in read_jsonl(input_path)]
    record_count = len(commits)

    subjects = [commit.subject for commit in commits if commit.subject]
    bodies = [commit.body for commit in commits]

    subject_char_lengths = [len(subject) for subject in subjects]
    subject_word_lengths = [len(TOKEN_RE.findall(subject)) for subject in subjects]
    body_char_lengths = [len(body) for body in bodies if body]
    paragraph_counts = [len([p for p in body.split("\n\n") if p.strip()]) for body in bodies if body]

    prefix_counter: Counter[str] = Counter()
    imperative_hits = 0
    capitalized_start = 0
    for subject in subjects:
        match = PREFIX_RE.match(subject)
        if match:
            prefix_counter[match.group("prefix")] += 1
        action_verb = _extract_action_verb(subject)
        if action_verb in IMPERATIVE_VERBS:
            imperative_hits += 1
        if subject[0].isupper():
            capitalized_start += 1

    trailer_counter: Counter[str] = Counter()
    with_trailers = 0
    rationale_hits = 0
    mechanics_hits = 0
    for commit in commits:
        for key, values in commit.trailers.items():
            trailer_counter[key] += len(values)
        if commit.trailers:
            with_trailers += 1

        haystack = f"{commit.subject}\n{commit.body}".lower()
        if any(cue in haystack for cue in RATIONALE_CUES):
            rationale_hits += 1
        if any(cue in haystack for cue in MECHANICS_CUES):
            mechanics_hits += 1

    report = {
        "generated_at": iso_now(),
        "record_count": record_count,
        "subject": {
            "char_length": _stats(subject_char_lengths),
            "word_length": _stats(subject_word_lengths),
            "prefix_rate": (sum(prefix_counter.values()) / record_count) if record_count else 0.0,
            "top_prefixes": [
                {"prefix": prefix, "count": count}
                for prefix, count in prefix_counter.most_common(12)
            ],
            "imperative_proxy_rate": (imperative_hits / len(subjects)) if subjects else 0.0,
            "capitalized_start_rate": (capitalized_start / len(subjects)) if subjects else 0.0,
        },
        "body": {
            "present_rate": (len(body_char_lengths) / record_count) if record_count else 0.0,
            "char_length": _stats(body_char_lengths),
            "paragraph_count": _stats(paragraph_counts),
        },
        "trailers": {
            "present_rate": (with_trailers / record_count) if record_count else 0.0,
            "top_keys": [
                {"key": key, "count": count} for key, count in trailer_counter.most_common(12)
            ],
        },
        "semantic_cues": {
            "rationale_rate": (rationale_hits / record_count) if record_count else 0.0,
            "mechanics_rate": (mechanics_hits / record_count) if record_count else 0.0,
        },
        "changes": {
            "files_changed": _stats([c.files_changed for c in commits]),
            "additions": _stats([c.additions for c in commits]),
            "deletions": _stats([c.deletions for c in commits]),
        },
        "samples": _choose_samples(commits),
    }

    write_json(output_path, report)
    return StageResult(path=str(output_path), record_count=record_count)
