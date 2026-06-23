from __future__ import annotations

import unittest

from app.ai_detector import fallback_clips, select_distinct_clips


class FallbackClipTests(unittest.TestCase):
    def test_respects_duration_and_limit(self) -> None:
        clips = fallback_clips(75.0, 5)
        self.assertEqual(len(clips), 2)
        self.assertEqual(clips[-1]["end"], 75.0)
        self.assertTrue(all(30 <= clip["end"] - clip["start"] <= 60 for clip in clips))
        self.assertTrue(all(clip["selection_source"] == "fallback" for clip in clips))

    def test_does_not_make_too_short_clip(self) -> None:
        clips = fallback_clips(40.0, 5)
        self.assertEqual(len(clips), 1)

    def test_short_ai_selection_is_extended_to_minimum(self) -> None:
        clips = select_distinct_clips([
            {"start": 50, "end": 60, "viral_score": 8, "title": "Goal"},
        ], 120, 5)
        self.assertEqual(clips[0]["end"] - clips[0]["start"], 30)

    def test_long_ai_selection_is_trimmed_to_absolute_maximum(self) -> None:
        clips = select_distinct_clips([
            {"start": 10, "end": 250, "viral_score": 9, "title": "Final drama"},
        ], 300, 5)
        self.assertEqual(clips[0]["end"] - clips[0]["start"], 180)

    def test_overlap_keeps_higher_scored_selection(self) -> None:
        clips = select_distinct_clips([
            {"start": 10, "end": 50, "viral_score": 6, "title": "Build up"},
            {"start": 20, "end": 60, "viral_score": 10, "title": "Winning goal"},
            {"start": 90, "end": 130, "viral_score": 8, "title": "Celebration"},
        ], 180, 5)
        self.assertEqual([clip["title"] for clip in clips], ["Winning goal", "Celebration"])

    def test_malformed_optional_metadata_is_safely_normalized(self) -> None:
        clips = select_distinct_clips([
            {
                "start": 0,
                "end": 35,
                "viral_score": "8.6",
                "title": None,
                "hashtags": None,
            },
        ], 60, 1)
        self.assertEqual(clips[0]["viral_score"], 9)
        self.assertEqual(clips[0]["title"], "A football moment you need to see")
        self.assertEqual(clips[0]["hashtags"], ["#football", "#shorts", "#viral"])


if __name__ == "__main__":
    unittest.main()
