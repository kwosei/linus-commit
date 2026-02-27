from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import threading
import time
from typing import Callable, TypeVar

from .analyze import analyze_commits
from .collect import collect_commits
from .evaluate import evaluate_style_fit
from .package_skill import package_skill
from .prepare import prepare_dataset
from .synthesize import synthesize_guidelines
from .utils import slugify

T = TypeVar("T")
_STATUS_LOCK = threading.Lock()


def _slug_for(repo: str, username: str) -> str:
    return slugify(f"{repo}-{username}")


def _status(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    with _STATUS_LOCK:
        print(f"[{timestamp}] {message}", flush=True)


def _stage_start(name: str, details: str = "") -> None:
    suffix = f" ({details})" if details else ""
    _status(f"{name}: starting{suffix}")


def _print_stage(name: str, result_path: str, count: int) -> None:
    _status(f"{name}: completed records={count} output={result_path}")


class _StageHeartbeat:
    def __init__(self, stage: str, interval_seconds: float = 5.0) -> None:
        self._stage = stage
        self._interval_seconds = interval_seconds
        self._started_at = 0.0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._started_at = time.monotonic()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=0.2)

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval_seconds):
            elapsed = int(time.monotonic() - self._started_at)
            _status(f"{self._stage}: still running ({elapsed}s elapsed)")


def _run_with_loader(stage: str, details: str, work: Callable[[], T]) -> T:
    _stage_start(stage, details)
    heartbeat = _StageHeartbeat(stage)
    heartbeat.start()
    try:
        return work()
    finally:
        heartbeat.stop()


def run_collect(args: argparse.Namespace) -> None:
    result = _run_with_loader(
        "collect",
        f"repo={args.repo} username={args.username}",
        lambda: collect_commits(
            repo=args.repo,
            username=args.username,
            output_path=Path(args.output),
            cache_root=Path(args.cache_dir),
            include_merges=args.include_merges,
            limit=args.limit,
            refresh=args.refresh,
            status=lambda msg: _status(f"collect: {msg}"),
        ),
    )
    _print_stage("collect", result.path, result.record_count)


def run_prepare(args: argparse.Namespace) -> None:
    result = _run_with_loader(
        "prepare",
        f"input={args.input}",
        lambda: prepare_dataset(
            input_path=Path(args.input),
            output_path=Path(args.output),
            summary_path=Path(args.summary),
            drop_merges=args.drop_merges,
            drop_reverts=args.drop_reverts,
        ),
    )
    _print_stage("prepare", result.path, result.record_count)


def run_analyze(args: argparse.Namespace) -> None:
    result = _run_with_loader(
        "analyze",
        f"input={args.input}",
        lambda: analyze_commits(input_path=Path(args.input), output_path=Path(args.output)),
    )
    _print_stage("analyze", result.path, result.record_count)


def run_synthesize(args: argparse.Namespace) -> None:
    result = _run_with_loader(
        "synthesize",
        f"provider={args.provider} model={args.model or 'default'}",
        lambda: synthesize_guidelines(
            analysis_path=Path(args.analysis),
            output_path=Path(args.output),
            username=args.username,
            repo=args.repo,
            provider=args.provider,
            model=args.model,
        ),
    )
    _print_stage("synthesize", result.path, result.record_count)


def run_package_skill(args: argparse.Namespace) -> None:
    result = _run_with_loader(
        "package-skill",
        f"skill={args.skill_name}",
        lambda: package_skill(
            guidelines_path=Path(args.guidelines),
            profile_path=Path(args.profile),
            commits_path=Path(args.commits),
            output_dir=Path(args.output_dir),
            skill_name=args.skill_name,
            username=args.username,
            repo=args.repo,
        ),
    )
    _print_stage("package-skill", result.path, result.record_count)


def run_evaluate(args: argparse.Namespace) -> None:
    result = _run_with_loader(
        "evaluate",
        f"holdout_ratio={args.holdout_ratio}",
        lambda: evaluate_style_fit(
            commits_path=Path(args.commits),
            profile_path=Path(args.profile),
            guidelines_path=Path(args.guidelines),
            output_path=Path(args.output),
            holdout_ratio=args.holdout_ratio,
            seed=args.seed,
        ),
    )
    _print_stage("evaluate", result.path, result.record_count)


def run_generate(args: argparse.Namespace) -> None:
    _stage_start(
        "generate",
        f"repo={args.repo} username={args.username} provider={args.provider} model={args.model or 'default'}",
    )
    slug = _slug_for(args.repo, args.username)

    raw_path = Path(args.raw_output or f"data/raw/{slug}.jsonl")
    prepared_path = Path(args.prepared_output or f"data/prepared/{slug}.jsonl")
    summary_path = Path(args.prepare_summary or f"data/prepared/{slug}.summary.json")
    profile_path = Path(args.profile_output or f"outputs/profiles/{slug}.analysis.json")
    guidelines_path = Path(args.guidelines_output or f"outputs/profiles/{slug}.guidelines.json")
    evaluation_path = Path(args.evaluation_output or f"outputs/profiles/{slug}.evaluation.json")

    skill_name = args.skill_name or f"{args.username}-{slugify(args.repo)}-commit-style"
    skill_output = Path(args.skill_output_dir or "outputs/skills")

    collect_result = _run_with_loader(
        "collect",
        f"repo={args.repo} username={args.username}",
        lambda: collect_commits(
            repo=args.repo,
            username=args.username,
            output_path=raw_path,
            cache_root=Path(args.cache_dir),
            include_merges=args.include_merges,
            limit=args.limit,
            refresh=args.refresh,
            status=lambda msg: _status(f"collect: {msg}"),
        ),
    )
    _print_stage("collect", collect_result.path, collect_result.record_count)

    prepare_result = _run_with_loader(
        "prepare",
        f"input={raw_path}",
        lambda: prepare_dataset(
            input_path=raw_path,
            output_path=prepared_path,
            summary_path=summary_path,
            drop_merges=not args.include_merges,
            drop_reverts=args.drop_reverts,
        ),
    )
    _print_stage("prepare", prepare_result.path, prepare_result.record_count)

    analyze_result = _run_with_loader(
        "analyze",
        f"input={prepared_path}",
        lambda: analyze_commits(input_path=prepared_path, output_path=profile_path),
    )
    _print_stage("analyze", analyze_result.path, analyze_result.record_count)

    synth_result = _run_with_loader(
        "synthesize",
        f"provider={args.provider} model={args.model or 'default'}",
        lambda: synthesize_guidelines(
            analysis_path=profile_path,
            output_path=guidelines_path,
            username=args.username,
            repo=args.repo,
            provider=args.provider,
            model=args.model,
        ),
    )
    _print_stage("synthesize", synth_result.path, synth_result.record_count)

    eval_result = _run_with_loader(
        "evaluate",
        f"holdout_ratio={args.holdout_ratio}",
        lambda: evaluate_style_fit(
            commits_path=prepared_path,
            profile_path=profile_path,
            guidelines_path=guidelines_path,
            output_path=evaluation_path,
            holdout_ratio=args.holdout_ratio,
            seed=args.seed,
        ),
    )
    _print_stage("evaluate", eval_result.path, eval_result.record_count)

    package_result = _run_with_loader(
        "package-skill",
        f"skill={skill_name}",
        lambda: package_skill(
            guidelines_path=guidelines_path,
            profile_path=profile_path,
            commits_path=prepared_path,
            output_dir=skill_output,
            skill_name=skill_name,
            username=args.username,
            repo=args.repo,
        ),
    )
    _print_stage("package-skill", package_result.path, package_result.record_count)
    _status("generate: all stages completed")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="commit-style",
        description="Generate commit-style profiles and Claude Code skills from git commit history.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_cmd = subparsers.add_parser("collect", help="Collect raw commits for an author")
    collect_cmd.add_argument("--repo", required=True, help="Local git path, owner/repo, or clone URL")
    collect_cmd.add_argument("--username", required=True, help="Git author pattern to filter")
    collect_cmd.add_argument("--output", required=True, help="Output JSONL path")
    collect_cmd.add_argument("--cache-dir", default=".context/repos", help="Repository cache directory")
    collect_cmd.add_argument("--include-merges", action="store_true", help="Include merge commits")
    collect_cmd.add_argument("--limit", type=int, default=None, help="Optional max number of commits")
    collect_cmd.add_argument("--refresh", action="store_true", help="Fetch latest changes for cached repo")
    collect_cmd.set_defaults(func=run_collect)

    prepare_cmd = subparsers.add_parser("prepare", help="Normalize and clean raw commit dataset")
    prepare_cmd.add_argument("--input", required=True, help="Input raw JSONL")
    prepare_cmd.add_argument("--output", required=True, help="Output prepared JSONL")
    prepare_cmd.add_argument("--summary", required=True, help="Output summary JSON")
    prepare_cmd.add_argument("--drop-merges", action="store_true", default=False)
    prepare_cmd.add_argument("--drop-reverts", action="store_true", default=False)
    prepare_cmd.set_defaults(func=run_prepare)

    analyze_cmd = subparsers.add_parser("analyze", help="Analyze commit-style metrics")
    analyze_cmd.add_argument("--input", required=True, help="Prepared JSONL")
    analyze_cmd.add_argument("--output", required=True, help="Output profile JSON")
    analyze_cmd.set_defaults(func=run_analyze)

    synth_cmd = subparsers.add_parser("synthesize", help="Infer writing guidelines from style profile")
    synth_cmd.add_argument("--analysis", required=True, help="Input analysis JSON")
    synth_cmd.add_argument("--output", required=True, help="Output guidelines JSON")
    synth_cmd.add_argument("--username", required=True, help="Target user")
    synth_cmd.add_argument("--repo", required=True, help="Target repository")
    synth_cmd.add_argument("--provider", default="anthropic", choices=["anthropic", "openai", "gemini", "none"])
    synth_cmd.add_argument("--model", default=None, help="Model name; provider default is used when omitted")
    synth_cmd.set_defaults(func=run_synthesize)

    package_cmd = subparsers.add_parser("package-skill", help="Generate a Claude-style skill folder")
    package_cmd.add_argument("--guidelines", required=True, help="Guidelines JSON path")
    package_cmd.add_argument("--profile", required=True, help="Profile JSON path")
    package_cmd.add_argument("--commits", required=True, help="Prepared commits JSONL path")
    package_cmd.add_argument("--output-dir", required=True, help="Output root directory")
    package_cmd.add_argument("--skill-name", required=True, help="Skill directory name")
    package_cmd.add_argument("--username", required=True, help="Target user")
    package_cmd.add_argument("--repo", required=True, help="Target repository")
    package_cmd.set_defaults(func=run_package_skill)

    eval_cmd = subparsers.add_parser("evaluate", help="Evaluate inferred style against holdout commits")
    eval_cmd.add_argument("--commits", required=True, help="Prepared commits JSONL")
    eval_cmd.add_argument("--profile", required=True, help="Profile JSON")
    eval_cmd.add_argument("--guidelines", required=True, help="Guidelines JSON")
    eval_cmd.add_argument("--output", required=True, help="Evaluation JSON output")
    eval_cmd.add_argument("--holdout-ratio", type=float, default=0.2)
    eval_cmd.add_argument("--seed", type=int, default=42)
    eval_cmd.set_defaults(func=run_evaluate)

    gen_cmd = subparsers.add_parser("generate", help="Run the full pipeline")
    gen_cmd.add_argument("--repo", required=True, help="Local git path, owner/repo, or clone URL")
    gen_cmd.add_argument("--username", required=True, help="Git author pattern to filter")
    gen_cmd.add_argument("--cache-dir", default=".context/repos")
    gen_cmd.add_argument("--include-merges", action="store_true")
    gen_cmd.add_argument("--drop-reverts", action="store_true")
    gen_cmd.add_argument("--limit", type=int, default=None)
    gen_cmd.add_argument("--refresh", action="store_true")
    gen_cmd.add_argument("--provider", default="anthropic", choices=["anthropic", "openai", "gemini", "none"])
    gen_cmd.add_argument("--model", default=None, help="Model name; provider default is used when omitted")
    gen_cmd.add_argument("--holdout-ratio", type=float, default=0.2)
    gen_cmd.add_argument("--seed", type=int, default=42)

    gen_cmd.add_argument("--raw-output", default=None)
    gen_cmd.add_argument("--prepared-output", default=None)
    gen_cmd.add_argument("--prepare-summary", default=None)
    gen_cmd.add_argument("--profile-output", default=None)
    gen_cmd.add_argument("--guidelines-output", default=None)
    gen_cmd.add_argument("--evaluation-output", default=None)
    gen_cmd.add_argument("--skill-output-dir", default=None)
    gen_cmd.add_argument("--skill-name", default=None)

    gen_cmd.set_defaults(func=run_generate)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
