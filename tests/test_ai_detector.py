from __future__ import annotations

import unittest

from app.ai_detector import fallback_clips


class FallbackClipTests(unittest.TestCase):
    def test_respects_duration_and_limit(self) -> None:
        clips = fallback_clips(75.0, 5)
        self.assertEqual(len(clips), 3)
        self.assertEqual(clips[-1]["end"], 75.0)

    def test_does_not_make_too_short_clip(self) -> None:
        clips = fallback_clips(40.0, 5)
        self.assertEqual(len(clips), 1)


if __name__ == "__main__":
    unittest.main()
