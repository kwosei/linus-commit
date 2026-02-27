import tempfile
import unittest
from pathlib import Path

from commit_style_tool.package_skill import package_skill
from commit_style_tool.utils import read_json, write_json, write_jsonl


class PackageSkillTest(unittest.TestCase):
    def test_skill_markdown_does_not_inline_evidence_hashes(self) -> None:
        guidelines = {
            "rules": [
                {
                    "id": "rule-1",
                    "instruction": "Use concise subject lines.",
                    "rationale": "Most subjects are short.",
                    "evidence_commit_ids": ["abc123", "def456"],
                }
            ],
            "anti_rules": [],
            "tone": {"summary": "Direct", "do": ["Be clear"], "avoid": ["Be vague"]},
            "format": {
                "subject": "subsystem: imperative summary",
                "body": "Explain why.",
                "trailers": "Use when needed.",
            },
        }
        profile = {"record_count": 1}
        commits = [
            {
                "hash": "abc123",
                "subject": "mm: fix test",
                "body": "Because this fails.",
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guidelines_path = root / "guidelines.json"
            profile_path = root / "profile.json"
            commits_path = root / "commits.jsonl"
            out_dir = root / "out"

            write_json(guidelines_path, guidelines)
            write_json(profile_path, profile)
            write_jsonl(commits_path, commits)

            result = package_skill(
                guidelines_path=guidelines_path,
                profile_path=profile_path,
                commits_path=commits_path,
                output_dir=out_dir,
                skill_name="test-skill",
                username="tester",
                repo="owner/repo",
            )

            skill_md = (Path(result.path) / "SKILL.md").read_text(encoding="utf-8")
            self.assertNotIn("Evidence:", skill_md)
            self.assertNotIn("abc123", skill_md)

            inference = read_json(Path(result.path) / "references" / "inference-guidelines.json")
            self.assertEqual(inference["rules"][0]["evidence_commit_ids"], ["abc123", "def456"])


if __name__ == "__main__":
    unittest.main()
