from __future__ import annotations

import unittest
from unittest.mock import patch

from app.ffmpeg_utils import check_media_tools


class MediaToolTests(unittest.TestCase):
    def test_reports_only_missing_tools(self) -> None:
        with patch(
            "app.ffmpeg_utils.resolve_media_executable",
            side_effect=lambda name: None if name == "ffprobe" else name,
        ):
            self.assertEqual(check_media_tools(), ["ffprobe"])


if __name__ == "__main__":
    unittest.main()
