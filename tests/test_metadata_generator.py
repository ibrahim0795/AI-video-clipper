from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.metadata_generator import save_metadata, transcript_excerpt


class MetadataTests(unittest.TestCase):
    def test_excerpt_uses_only_overlapping_text(self) -> None:
        transcript = [
            {"start": 0, "end": 5, "text": "before"},
            {"start": 9, "end": 12, "text": "overlap"},
            {"start": 15, "end": 18, "text": "inside"},
            {"start": 21, "end": 25, "text": "after"},
        ]
        self.assertEqual(transcript_excerpt(transcript, 10, 20), "overlap inside")

    def test_saves_string_timestamp_metadata(self) -> None:
        clip = {
            "start": "00:00:10", "end": "00:00:20", "title": "Title", "hook": "Hook",
            "caption": "Caption", "description": "Description", "hashtags": ["#shorts"],
        }
        transcript = [{"start": 11, "end": 12, "text": "clip words"}]
        with tempfile.TemporaryDirectory() as temp, patch(
            "app.metadata_generator.OUTPUT_DIR", Path(temp)
        ):
            save_metadata("job", [clip], transcript)
            value = json.loads((Path(temp) / "job" / "clip_1_metadata.json").read_text("utf-8"))
        self.assertEqual(value["transcript"], "clip words")


if __name__ == "__main__":
    unittest.main()
