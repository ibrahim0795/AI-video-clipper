from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.downloader import get_video


class DownloaderTests(unittest.TestCase):
    def test_copies_local_video(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "input.mp4"
            source.write_bytes(b"test-video")
            with patch("app.downloader.DOWNLOADS_DIR", root / "downloads"):
                destination, job_id = get_video(str(source), "job123")
            self.assertEqual(job_id, "job123")
            self.assertEqual(destination.read_bytes(), b"test-video")

    def test_rejects_missing_or_invalid_source(self) -> None:
        with self.assertRaises(ValueError):
            get_video("not-a-video")

    def test_rejects_unsupported_local_extension(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "notes.txt"
            source.write_text("hello", encoding="utf-8")
            with self.assertRaises(ValueError):
                get_video(str(source))


if __name__ == "__main__":
    unittest.main()
