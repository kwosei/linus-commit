from __future__ import annotations

import random
import re
from pathlib import Path

from .types import CommitRecord, StageResult
from .utils import read_json, read_jsonl, write_json

PREFIX_RE = re.compile(r"^[A-Za-z0-9_./-]{2,40}:\s+.+$")
RATIONALE_CUES = ["because", "otherwise", "so that", "to avoid", "regression", "reason"]


def _score_range(value: float, low: float, high: float) -> float:
    if high < low:
        low, high = high, low
    if low <= value <= high:
        return 1.0
    distance = min(abs(value - low), abs(value - high))
    width = max(1.0, high - low)
    penalty = min(1.0, distance / (width * 2.0))
    return max(0.0, 1.0 - penalty)


def evaluate_style_fit(
    commits_path: Path,
    profile_path: Path,
    guidelines_path: Path,
    output_path: Path,
    holdout_ratio: float = 0.2,
    seed: int = 42,
) -> StageResult:
    commits = [CommitRecord.from_dict(row) for row in read_jsonl(commits_path)]
    profile = read_json(profile_path)
    guidelines = read_json(guidelines_path)

    if not commits:
        write_json(
            output_path,
            {
                "score": 0.0,
                "reason": "no commits available",
                "holdout_count": 0,
            },
        )
        return StageResult(path=str(output_path), record_count=0)

    random.seed(seed)
    shuffled = list(commits)
    random.shuffle(shuffled)
    holdout_count = max(1, int(len(shuffled) * holdout_ratio))
    holdout = shuffled[:holdout_count]

    subject_stats = profile.get("subject", {}).get("char_length", {})
    subject_low = float(subject_stats.get("p10", 0.0))
    subject_high = float(subject_stats.get("p90", 0.0))

    expected_prefix_rate = float(profile.get("subject", {}).get("prefix_rate", 0.0))
    expected_body_rate = float(profile.get("body", {}).get("present_rate", 0.0))
    expected_trailer_rate = float(profile.get("trailers", {}).get("present_rate", 0.0))
    expected_rationale_rate = float(profile.get("semantic_cues", {}).get("rationale_rate", 0.0))

    commit_scores: list[dict] = []
    for commit in holdout:
        subject_len = len(commit.subject)
        subject_score = _score_range(subject_len, subject_low, subject_high)

        has_prefix = bool(PREFIX_RE.match(commit.subject))
        if expected_prefix_rate >= 0.3:
            prefix_score = 1.0 if has_prefix else 0.0
        elif expected_prefix_rate <= 0.1:
            prefix_score = 1.0 if not has_prefix else 0.5
        else:
            prefix_score = 1.0 if has_prefix else 0.7

        has_body = bool(commit.body.strip())
        body_score = 1.0 - abs((1.0 if has_body else 0.0) - expected_body_rate)

        has_trailers = bool(commit.trailers)
        trailer_score = 1.0 - abs((1.0 if has_trailers else 0.0) - expected_trailer_rate)

        haystack = f"{commit.subject}\n{commit.body}".lower()
        has_rationale = any(cue in haystack for cue in RATIONALE_CUES)
        rationale_score = 1.0 - abs((1.0 if has_rationale else 0.0) - expected_rationale_rate)

        style_fit = (
            (subject_score * 0.35)
            + (prefix_score * 0.15)
            + (body_score * 0.2)
            + (trailer_score * 0.15)
            + (rationale_score * 0.15)
        )

        commit_scores.append(
            {
                "hash": commit.hash,
                "subject": commit.subject,
                "subject_score": round(subject_score, 3),
                "prefix_score": round(prefix_score, 3),
                "body_score": round(body_score, 3),
                "trailer_score": round(trailer_score, 3),
                "rationale_score": round(rationale_score, 3),
                "style_fit": round(style_fit, 3),
            }
        )

    overall = sum(item["style_fit"] for item in commit_scores) / len(commit_scores)

    report = {
        "score": round(overall * 100.0, 2),
        "score_unit": "0-100",
        "holdout_count": len(holdout),
        "input_count": len(commits),
        "guideline_rule_count": len(guidelines.get("rules", [])),
        "details": {
            "expected_prefix_rate": expected_prefix_rate,
            "expected_body_rate": expected_body_rate,
            "expected_trailer_rate": expected_trailer_rate,
            "expected_rationale_rate": expected_rationale_rate,
            "subject_target": {"p10": subject_low, "p90": subject_high},
        },
        "holdout_scores": commit_scores,
    }

    write_json(output_path, report)
    return StageResult(path=str(output_path), record_count=len(holdout))
