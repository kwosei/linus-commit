from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from .types import CommitRecord, StageResult
from .utils import ensure_dir, run_command, slugify, write_jsonl

RECORD_SEP = "\x1e"
FIELD_SEP = "\x1f"
TRAILER_SEP = "\x1d"
TRAILER_KV_SEP = "\x1c"
REPAIRABLE_GIT_ERROR_SNIPPETS = (
    "from promisor remote",
    "repo corruption",
    "commit graph file but not in the object database",
    "could not fetch",
)


def _emit(status: Callable[[str], None] | None, message: str) -> None:
    if status is not None:
        status(message)


def _clone_to_cache(clone_url: str, checkout_path: Path) -> None:
    run_command(
        [
            "git",
            "clone",
            "--no-checkout",
            clone_url,
            str(checkout_path),
        ]
    )


def _is_remote_repo_source(repo_source: str) -> bool:
    return (
        repo_source.startswith("http://")
        or repo_source.startswith("https://")
        or repo_source.endswith(".git")
    )


def _is_cached_remote_repo(repo_path: Path, repo_source: str, cache_root: Path) -> bool:
    if not _is_remote_repo_source(repo_source):
        return False
    return repo_path.resolve().is_relative_to(cache_root.resolve())


def _is_repairable_git_error(error: RuntimeError) -> bool:
    message = str(error).lower()
    return any(snippet in message for snippet in REPAIRABLE_GIT_ERROR_SNIPPETS)


def _repair_cached_repository(
    repo_path: Path,
    clone_url: str,
    status: Callable[[str], None] | None = None,
) -> Path:
    _emit(status, "attempting cache repair with git fetch --refetch")
    try:
        run_command(["git", "-C", str(repo_path), "fetch", "--all", "--prune", "--tags", "--refetch"])
        return repo_path
    except RuntimeError:
        _emit(status, "cache refetch failed; recloning repository cache")
        if repo_path.exists():
            shutil.rmtree(repo_path)
        _clone_to_cache(clone_url, repo_path)
        return repo_path


def _build_git_log_command(
    repo_path: Path,
    username: str,
    include_merges: bool,
    limit: int | None,
) -> list[str]:
    pretty = (
        "%x1e%H%x1f%an%x1f%ae%x1f%aI%x1f%cn%x1f%ce%x1f%P%x1f%s%x1f%b"
        "%x1f%(trailers:only,separator=%x1d,key_value_separator=%x1c)"
    )
    cmd = [
        "git",
        "-C",
        str(repo_path),
        "log",
        "--date=iso-strict",
        f"--author={username}",
        f"--pretty=format:{pretty}",
        "--numstat",
    ]
    if not include_merges:
        cmd.append("--no-merges")
    if limit is not None and limit > 0:
        cmd.extend(["-n", str(limit)])
    return cmd


def resolve_repository(
    repo: str,
    cache_root: Path,
    refresh: bool = False,
    status: Callable[[str], None] | None = None,
) -> tuple[Path, str]:
    repo_path = Path(repo)
    if repo_path.exists() and (repo_path / ".git").exists():
        _emit(status, f"using local repository at {repo_path.resolve()}")
        return repo_path.resolve(), str(repo_path.resolve())

    normalized = repo.strip()
    if normalized.startswith("http://") or normalized.startswith("https://") or normalized.endswith(
        ".git"
    ):
        clone_url = normalized
    elif "/" in normalized and normalized.count("/") == 1:
        clone_url = f"https://github.com/{normalized}.git"
    else:
        raise ValueError(
            "Repository must be a local git path, owner/repo, or a full git clone URL"
        )

    cache_key = slugify(normalized.replace("https://", "").replace("http://", ""))
    checkout_path = cache_root / cache_key
    ensure_dir(cache_root)

    if not checkout_path.exists():
        _emit(status, f"cloning repository to cache: {clone_url}")
        _clone_to_cache(clone_url, checkout_path)
    elif refresh:
        _emit(status, f"refreshing cached repository: {checkout_path}")
        run_command(["git", "-C", str(checkout_path), "fetch", "--all", "--prune", "--tags"])
    else:
        _emit(status, f"using cached repository: {checkout_path}")

    return checkout_path, clone_url


def parse_git_log_output(blob: str) -> list[CommitRecord]:
    records: list[CommitRecord] = []
    for raw_record in blob.split(RECORD_SEP):
        if not raw_record.strip():
            continue

        record = raw_record.lstrip("\n")
        fields = record.split(FIELD_SEP, 9)
        if len(fields) < 10:
            continue

        (
            commit_hash,
            author_name,
            author_email,
            authored_date,
            committer_name,
            committer_email,
            parents_raw,
            subject,
            body,
            trailers_and_stats,
        ) = fields

        if "\n" in trailers_and_stats:
            trailers_raw, stats_blob = trailers_and_stats.split("\n", 1)
        else:
            trailers_raw, stats_blob = trailers_and_stats, ""

        parents = [parent for parent in parents_raw.split() if parent]
        trailers: dict[str, list[str]] = {}
        for item in trailers_raw.split(TRAILER_SEP):
            item = item.strip()
            if not item:
                continue
            if TRAILER_KV_SEP in item:
                key, value = item.split(TRAILER_KV_SEP, 1)
            else:
                key, value = item, ""
            clean_key = key.strip()
            if not clean_key:
                continue
            trailers.setdefault(clean_key, []).append(value.strip())

        additions = 0
        deletions = 0
        files_changed = 0
        for line in stats_blob.splitlines():
            clean = line.strip()
            if not clean:
                continue
            chunks = clean.split("\t")
            if len(chunks) != 3:
                continue
            add_raw, del_raw, _path = chunks
            files_changed += 1
            if add_raw.isdigit():
                additions += int(add_raw)
            if del_raw.isdigit():
                deletions += int(del_raw)

        body = body.rstrip()
        subject = subject.strip()
        is_merge = len(parents) > 1
        is_revert = subject.startswith('Revert "') or "This reverts commit" in body

        records.append(
            CommitRecord(
                hash=commit_hash.strip(),
                author_name=author_name.strip(),
                author_email=author_email.strip(),
                authored_date=authored_date.strip(),
                committer_name=committer_name.strip(),
                committer_email=committer_email.strip(),
                parents=parents,
                subject=subject,
                body=body,
                trailers=trailers,
                files_changed=files_changed,
                additions=additions,
                deletions=deletions,
                is_merge=is_merge,
                is_revert=is_revert,
            )
        )

    return records


def collect_commits(
    repo: str,
    username: str,
    output_path: Path,
    cache_root: Path,
    include_merges: bool = False,
    limit: int | None = None,
    refresh: bool = False,
    status: Callable[[str], None] | None = None,
) -> StageResult:
    repo_path, repo_source = resolve_repository(
        repo,
        cache_root=cache_root,
        refresh=refresh,
        status=status,
    )
    cmd = _build_git_log_command(
        repo_path=repo_path,
        username=username,
        include_merges=include_merges,
        limit=limit,
    )

    _emit(status, "running git log query for matching commits")
    try:
        blob = run_command(cmd)
    except RuntimeError as error:
        if not _is_cached_remote_repo(repo_path, repo_source, cache_root) or not _is_repairable_git_error(
            error
        ):
            raise

        _emit(status, "git log failed due to cache corruption; attempting repository repair")
        try:
            repo_path = _repair_cached_repository(repo_path, repo_source, status=status)
        except RuntimeError as repair_error:
            raise RuntimeError(
                f"{error}\nRepository cache repair failed for {repo_path}: {repair_error}"
            ) from repair_error

        _emit(status, "retrying git log query after repository repair")
        retry_cmd = _build_git_log_command(
            repo_path=repo_path,
            username=username,
            include_merges=include_merges,
            limit=limit,
        )
        try:
            blob = run_command(retry_cmd)
        except RuntimeError as retry_error:
            raise RuntimeError(
                f"{retry_error}\nRepository cache at {repo_path} is still unusable. "
                "Delete the cache directory and rerun with network access."
            ) from retry_error
    _emit(status, "parsing commit records from git log output")
    commits = parse_git_log_output(blob)

    _emit(status, f"writing {len(commits)} commit records")
    count = write_jsonl(output_path, (item.to_dict() for item in commits))
    _emit(status, f"finished writing dataset to {output_path}")
    return StageResult(
        path=str(output_path),
        record_count=count,
        metadata={
            "repo_source": repo_source,
            "repo_path": str(repo_path),
            "username": username,
            "include_merges": include_merges,
            "limit": limit,
        },
    )
