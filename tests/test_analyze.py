import tempfile
import unittest
from pathlib import Path

from commit_style_tool.analyze import analyze_commits
from commit_style_tool.utils import read_json, write_jsonl


class AnalyzeCommitsTest(unittest.TestCase):
    def test_analyze_reports_prefix_and_body_rates(self) -> None:
        rows = [
            {
                "hash": "a",
                "author_name": "Linus",
                "author_email": "a@example.com",
                "authored_date": "2024-01-01T00:00:00+00:00",
                "committer_name": "Linus",
                "committer_email": "a@example.com",
                "parents": ["p1"],
                "subject": "mm: fix page accounting",
                "body": "Explain why.",
                "trailers": {},
                "files_changed": 1,
                "additions": 3,
                "deletions": 1,
                "is_merge": False,
                "is_revert": False,
            },
            {
                "hash": "b",
                "author_name": "Linus",
                "author_email": "a@example.com",
                "authored_date": "2024-01-02T00:00:00+00:00",
                "committer_name": "Linus",
                "committer_email": "a@example.com",
                "parents": ["p2"],
                "subject": "Fix lock ordering",
                "body": "",
                "trailers": {},
                "files_changed": 2,
                "additions": 4,
                "deletions": 2,
                "is_merge": False,
                "is_revert": False,
            },
            {
                "hash": "c",
                "author_name": "Linus",
                "author_email": "a@example.com",
                "authored_date": "2024-01-03T00:00:00+00:00",
                "committer_name": "Linus",
                "committer_email": "a@example.com",
                "parents": ["p3"],
                "subject": "sched: adjust wakeup path",
                "body": "Avoid regression otherwise latency grows.",
                "trailers": {"Fixes": ["123"]},
                "files_changed": 3,
                "additions": 8,
                "deletions": 5,
                "is_merge": False,
                "is_revert": False,
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "in.jsonl"
            output_path = Path(tmp) / "out.json"
            write_jsonl(input_path, rows)
            result = analyze_commits(input_path=input_path, output_path=output_path)

            self.assertEqual(result.record_count, 3)
            report = read_json(output_path)
            self.assertEqual(report["record_count"], 3)
            self.assertGreater(report["subject"]["prefix_rate"], 0.6)
            self.assertGreater(report["body"]["present_rate"], 0.6)


if __name__ == "__main__":
    unittest.main()
