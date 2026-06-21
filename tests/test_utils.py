from __future__ import annotations

import unittest

from app.utils import format_timestamp, parse_json_response, parse_timestamp


class TimestampTests(unittest.TestCase):
    def test_parse_hms_and_mmss(self) -> None:
        self.assertEqual(parse_timestamp("01:02:03"), 3723.0)
        self.assertEqual(parse_timestamp("02:03.5"), 123.5)

    def test_parse_rejects_invalid_values(self) -> None:
        for value in ("", "1:70:00", "bad", -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_timestamp(value)

    def test_format_srt(self) -> None:
        self.assertEqual(format_timestamp(62.345, srt=True), "00:01:02,345")


class GeminiJsonTests(unittest.TestCase):
    def test_parses_markdown_wrapped_json(self) -> None:
        result = parse_json_response('```json\n[{"start_time":"00:00:01"}]\n```')
        self.assertEqual(result[0]["start_time"], "00:00:01")

    def test_extracts_array_from_extra_text(self) -> None:
        self.assertEqual(parse_json_response('Answer: [{"viral_score":9}] done')[0]["viral_score"], 9)

    def test_rejects_non_list(self) -> None:
        with self.assertRaises(ValueError):
            parse_json_response('{"message":"no clips"}')


if __name__ == "__main__":
    unittest.main()
