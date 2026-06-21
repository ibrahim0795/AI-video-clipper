from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.captioner import burn_subtitles, generate_srt


class SubtitleTests(unittest.TestCase):
    def test_clips_and_shifts_overlapping_segments(self) -> None:
        transcript = [
            {"start": 8.0, "end": 12.0, "text": "Starts before the clip"},
            {"start": 15.0, "end": 18.0, "text": "Inside clip"},
            {"start": 25.0, "end": 30.0, "text": "Outside clip"},
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "clip.srt"
            count = generate_srt(transcript, 10.0, 20.0, path)
            content = path.read_text(encoding="utf-8")
        self.assertEqual(count, 2)
        self.assertIn("00:00:00,000 --> 00:00:02,000", content)
        self.assertIn("00:00:05,000 --> 00:00:08,000", content)
        self.assertNotIn("Outside clip", content)

    def test_long_caption_has_at_most_two_lines(self) -> None:
        transcript = [{"start": 0, "end": 5, "text": "word " * 40}]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "clip.srt"
            generate_srt(transcript, 0, 10, path)
            block = path.read_text(encoding="utf-8").strip().splitlines()
        self.assertLessEqual(len(block[2:]), 2)

    def test_burn_uses_vertical_reference_resolution(self) -> None:
        with patch("app.captioner.run_command") as run:
            burn_subtitles(Path("raw.mp4"), Path("clip.srt"), Path("final.mp4"))
        subtitle_filter = run.call_args.args[0][run.call_args.args[0].index("-vf") + 1]
        self.assertIn("original_size=1080x1920", subtitle_filter)
        self.assertIn("FontSize=7.20", subtitle_filter)


if __name__ == "__main__":
    unittest.main()
