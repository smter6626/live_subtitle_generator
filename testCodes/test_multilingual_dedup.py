import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stream_transcribe import simple_dedup, tokenize_for_compare  # noqa: E402


class MultilingualDedupTests(unittest.TestCase):
    def assert_exact_boundary_overlap_is_trimmed(self, old_text, new_text, expected):
        tokens, _ = tokenize_for_compare(old_text, skip_timestamps=True)
        self.assertGreaterEqual(len(tokens), 3)
        self.assertEqual(simple_dedup(new_text, old_text), expected)

    def test_japanese_exact_boundary_overlap_is_trimmed(self):
        self.assert_exact_boundary_overlap_is_trimmed(
            "[0.00s -> 4.00s] 今日は天気がとても良いです",
            "[7.00s -> 11.00s] 天気がとても良いですので散歩します",
            "[7.00s -> 11.00s] ので散歩します",
        )

    def test_korean_exact_boundary_overlap_is_trimmed(self):
        self.assert_exact_boundary_overlap_is_trimmed(
            "[0.00s -> 4.00s] 오늘 날씨가 정말 좋습니다",
            "[7.00s -> 11.00s] 날씨가 정말 좋습니다 그래서 산책합니다",
            "[7.00s -> 11.00s] 그래서 산책합니다",
        )


if __name__ == "__main__":
    unittest.main()
