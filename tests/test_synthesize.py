import tempfile
import unittest
from pathlib import Path
from unittest import mock

from commit_style_tool.synthesize import synthesize_guidelines
from commit_style_tool.utils import read_json, write_json


class SynthesizeTest(unittest.TestCase):
    def test_synthesize_none_provider_uses_fallback(self) -> None:
        analysis = {
            "record_count": 12,
            "subject": {
                "char_length": {"median": 44, "p10": 20, "p90": 70},
                "prefix_rate": 0.7,
                "imperative_proxy_rate": 0.6,
            },
            "body": {"present_rate": 0.8},
            "trailers": {"present_rate": 0.3},
            "samples": [
                {
                    "hash": "abc",
                    "subject": "mm: fix reclaim accounting",
                    "body": "Handle this because overflow can happen.",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            analysis_path = Path(tmp) / "analysis.json"
            output_path = Path(tmp) / "guidelines.json"
            write_json(analysis_path, analysis)

            result = synthesize_guidelines(
                analysis_path=analysis_path,
                output_path=output_path,
                username="torvalds",
                repo="torvalds/linux",
                provider="none",
            )
            self.assertGreater(result.record_count, 0)

            guidelines = read_json(output_path)
            self.assertEqual(guidelines["source"], "heuristic")
            self.assertTrue(guidelines["rules"])

    def test_synthesize_gemini_without_key_uses_fallback(self) -> None:
        analysis = {
            "record_count": 6,
            "subject": {
                "char_length": {"median": 36, "p10": 18, "p90": 65},
                "prefix_rate": 0.4,
                "imperative_proxy_rate": 0.5,
            },
            "body": {"present_rate": 0.7},
            "trailers": {"present_rate": 0.2},
            "samples": [{"hash": "def", "subject": "net: fix timeout logic", "body": "Avoid hangs."}],
        }

        with tempfile.TemporaryDirectory() as tmp:
            analysis_path = Path(tmp) / "analysis.json"
            output_path = Path(tmp) / "guidelines.json"
            write_json(analysis_path, analysis)

            with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}, clear=False):
                result = synthesize_guidelines(
                    analysis_path=analysis_path,
                    output_path=output_path,
                    username="torvalds",
                    repo="torvalds/linux",
                    provider="gemini",
                )

            self.assertGreater(result.record_count, 0)
            guidelines = read_json(output_path)
            self.assertEqual(guidelines["source"], "heuristic")
            self.assertTrue(guidelines["rules"])


if __name__ == "__main__":
    unittest.main()
