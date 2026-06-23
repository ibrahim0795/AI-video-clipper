from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import web_app


class WebAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = web_app.app.test_client()

    def test_index_renders_upload_interface(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Drop your video here", response.data)
        self.assertIn(b"Paste URL", response.data)

    def test_rejects_empty_submission(self) -> None:
        response = self.client.post("/api/jobs", data={"max_clips": "3"})
        self.assertEqual(response.status_code, 400)

    def test_rejects_unsupported_upload(self) -> None:
        response = self.client.post(
            "/api/jobs",
            data={"video": (io.BytesIO(b"not video"), "notes.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_out_of_range_clip_count(self) -> None:
        response = self.client.post(
            "/api/jobs", data={"max_clips": "99", "url": "https://youtube.com/watch?v=test"}
        )
        self.assertEqual(response.status_code, 400)

    def test_web_result_does_not_expose_local_video_path(self) -> None:
        summary = {
            "job_id": "abcdef123456",
            "local_video": r"C:\\private\\source.mp4",
            "clips": [],
        }
        with tempfile.TemporaryDirectory() as temp:
            summary_path = Path(temp) / "summary.json"
            summary_path.write_text(__import__("json").dumps(summary), encoding="utf-8")
            with patch("web_app.run_pipeline", return_value=summary_path):
                web_app._run_job("webjob", "https://example.com/video", 1)
        self.assertNotIn("local_video", web_app.jobs["webjob"]["result"])

    def test_rejects_invalid_media_job_directory(self) -> None:
        with patch("web_app.send_from_directory") as send:
            response = self.client.get("/media/not-a-job/README.md")
        self.assertEqual(response.status_code, 404)
        send.assert_not_called()

    def test_accepts_video_and_starts_worker(self) -> None:
        with tempfile.TemporaryDirectory() as temp, patch(
            "web_app.UPLOADS_DIR", Path(temp)
        ), patch("web_app.threading.Thread") as thread:
            response = self.client.post(
                "/api/jobs",
                data={"max_clips": "1", "video": (io.BytesIO(b"video"), "sample.mp4")},
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 202)
        self.assertIn("job_id", response.get_json())
        thread.return_value.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
