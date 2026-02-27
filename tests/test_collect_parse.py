import unittest

from commit_style_tool.collect import parse_git_log_output


class ParseGitLogOutputTest(unittest.TestCase):
    def test_parse_single_record_with_numstat_and_trailers(self) -> None:
        blob = (
            "\x1e"
            "abc123"
            "\x1fLinus Torvalds"
            "\x1ftorvalds@linux-foundation.org"
            "\x1f2025-01-01T00:00:00+00:00"
            "\x1fLinus Torvalds"
            "\x1ftorvalds@linux-foundation.org"
            "\x1fparent1 parent2"
            "\x1fkernel: fix race in startup"
            "\x1fExplain why this ordering matters.\nSecond line."
            "\x1fFixes\x1cdeadbeef\x1dSigned-off-by\x1cLinus Torvalds"
            "\n10\t2\tkernel/sched/core.c"
            "\n-\t-\tdocs/diagram.png\n"
        )

        rows = parse_git_log_output(blob)
        self.assertEqual(len(rows), 1)

        row = rows[0]
        self.assertEqual(row.hash, "abc123")
        self.assertTrue(row.is_merge)
        self.assertFalse(row.is_revert)
        self.assertEqual(row.files_changed, 2)
        self.assertEqual(row.additions, 10)
        self.assertEqual(row.deletions, 2)
        self.assertIn("Fixes", row.trailers)
        self.assertIn("Signed-off-by", row.trailers)


if __name__ == "__main__":
    unittest.main()
