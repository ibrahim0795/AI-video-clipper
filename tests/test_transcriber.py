from __future__ import annotations

import unittest

from app.transcriber import transcript_to_prompt


class TranscriptParserTests(unittest.TestCase):
    def test_prompt_preserves_timestamp_and_text(self) -> None:
        prompt = transcript_to_prompt([{"start": 12.5, "end": 18.2, "text": "Goal!"}])
        self.assertEqual(prompt, "[00:00:12.500-00:00:18.200] Goal!")


if __name__ == "__main__":
    unittest.main()
