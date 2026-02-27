import tempfile
import unittest
from pathlib import Path
from unittest import mock

from commit_style_tool.collect import collect_commits, resolve_repository


class CollectRecoveryTest(unittest.TestCase):
    def test_resolve_repository_clones_without_partial_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_root = Path(tmp) / "cache"

            with mock.patch("commit_style_tool.collect.run_command", return_value="") as run_cmd:
                checkout_path, clone_url = resolve_repository(
                    "torvalds/linux",
                    cache_root=cache_root,
                )

            self.assertEqual(clone_url, "https://github.com/torvalds/linux.git")
            self.assertEqual(checkout_path, cache_root / "torvalds-linux")
            clone_cmd = run_cmd.call_args.args[0]
            self.assertEqual(clone_cmd[:3], ["git", "clone", "--no-checkout"])
            self.assertNotIn("--filter=blob:none", clone_cmd)

    def test_collect_repairs_promisor_cache_and_retries_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_root = root / "cache"
            repo_path = cache_root / "torvalds-linux"
            output_path = root / "out.jsonl"
            calls: list[list[str]] = []
            log_calls = 0

            def fake_run_command(cmd: list[str], cwd: str | None = None) -> str:
                nonlocal log_calls
                calls.append(cmd)
                if "log" in cmd:
                    log_calls += 1
                    if log_calls == 1:
                        raise RuntimeError(
                            "Command failed (128): git ...\n"
                            "fatal: could not fetch deadbeef from promisor remote"
                        )
                return ""

            with mock.patch(
                "commit_style_tool.collect.resolve_repository",
                return_value=(repo_path, "https://github.com/torvalds/linux.git"),
            ), mock.patch(
                "commit_style_tool.collect.run_command",
                side_effect=fake_run_command,
            ), mock.patch(
                "commit_style_tool.collect.parse_git_log_output",
                return_value=[],
            ), mock.patch(
                "commit_style_tool.collect.write_jsonl",
                return_value=0,
            ):
                result = collect_commits(
                    repo="torvalds/linux",
                    username="torvalds",
                    output_path=output_path,
                    cache_root=cache_root,
                    include_merges=False,
                    limit=1000,
                )

            self.assertEqual(result.record_count, 0)
            self.assertEqual(log_calls, 2)
            self.assertIn(
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "fetch",
                    "--all",
                    "--prune",
                    "--tags",
                    "--refetch",
                ],
                calls,
            )

    def test_collect_does_not_attempt_cache_repair_for_local_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_root = root / "cache"
            local_repo = root / "local-repo"
            output_path = root / "out.jsonl"
            calls: list[list[str]] = []

            def failing_run_command(cmd: list[str], cwd: str | None = None) -> str:
                calls.append(cmd)
                raise RuntimeError(
                    "Command failed (128): git ...\n"
                    "fatal: could not fetch deadbeef from promisor remote"
                )

            with mock.patch(
                "commit_style_tool.collect.resolve_repository",
                return_value=(local_repo, str(local_repo)),
            ), mock.patch(
                "commit_style_tool.collect.run_command",
                side_effect=failing_run_command,
            ):
                with self.assertRaises(RuntimeError):
                    collect_commits(
                        repo=str(local_repo),
                        username="torvalds",
                        output_path=output_path,
                        cache_root=cache_root,
                        include_merges=False,
                        limit=1000,
                    )

            fetch_calls = [cmd for cmd in calls if "fetch" in cmd]
            self.assertEqual(fetch_calls, [])


if __name__ == "__main__":
    unittest.main()
