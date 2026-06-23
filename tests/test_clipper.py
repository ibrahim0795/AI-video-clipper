from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.clipper import _encoding_args, _vertical_filter_graph, create_final_clip, create_raw_clip


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
        graph = command[command.index("-filter_complex") + 1]
        self.assertIn("[foreground_source]scale=1080:1920:force_original_aspect_ratio=decrease", graph)
        self.assertIn("boxblur=", graph)
        self.assertIn("overlay=(W-w)/2:(H-h)/2", graph)
        self.assertIn("0:a:0?", command)

    def test_black_bar_mode_never_crops_foreground(self) -> None:
        with patch("app.clipper.USE_BLUR_BACKGROUND", False):
            graph, output = _vertical_filter_graph()
        self.assertIn("force_original_aspect_ratio=decrease", graph)
        self.assertIn("pad=1080:1920", graph)
        self.assertNotIn("crop=", graph)
        self.assertEqual(output, "[composed]")

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
        self.assertIn("subtitles=", command[command.index("-filter_complex") + 1])

    def test_hardware_failure_rebuilds_clean_cpu_encoding_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temp, patch(
            "app.clipper.OUTPUT_DIR", Path(temp)
        ), patch(
            "app.clipper.run_command", side_effect=[RuntimeError("QSV unavailable"), None]
        ) as run:
            create_raw_clip(Path("source.mp4"), "job", 1, 0, 30)
        retry = run.call_args_list[1].args[0]
        self.assertIn("libx264", retry)
        self.assertIn("-crf", retry)
        self.assertNotIn("h264_qsv", retry)
        self.assertNotIn("-global_quality", retry)


if __name__ == "__main__":
    unittest.main()
