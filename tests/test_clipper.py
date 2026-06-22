from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.clipper import _encoding_args, create_final_clip, create_raw_clip


class ClipperTests(unittest.TestCase):
    def test_encoding_args_preserve_requested_codec(self) -> None:
        self.assertEqual(_encoding_args("libx265")[1], "libx265")
        self.assertEqual(_encoding_args("hevc_qsv")[1], "hevc_qsv")
        self.assertIn("-global_quality", _encoding_args("hevc_qsv"))

    def test_builds_exact_vertical_ffmpeg_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp, patch(
            "app.clipper.OUTPUT_DIR", Path(temp)
        ), patch("app.clipper.run_command") as run:
            destination = create_raw_clip(Path("source.mp4"), "job", 1, 12.5, 42.5)
        command = run.call_args.args[0]
        self.assertEqual(destination.name, "clip_1_raw.mp4")
        self.assertIn("12.500", command)
        self.assertIn("30.000", command)
        self.assertIn("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", command)
        self.assertIn("0:a?", command)

    def test_final_clip_uses_one_hardware_encode_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp, patch(
            "app.clipper.OUTPUT_DIR", Path(temp)
        ), patch("app.clipper.run_command") as run:
            destination = create_final_clip(
                Path("source.mp4"), "job", 1, 0, 30, Path(temp) / "clip.srt"
            )
        command = run.call_args.args[0]
        self.assertEqual(run.call_count, 1)
        self.assertEqual(destination.name, "clip_1.mp4")
        self.assertIn("h264_qsv", command)
        self.assertIn("subtitles=", command[command.index("-vf") + 1])


if __name__ == "__main__":
    unittest.main()
