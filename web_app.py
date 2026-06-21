"""Responsive local web interface for AI Video Clipper."""

from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from app.config import OUTPUT_DIR, UPLOADS_DIR, ensure_directories
from app.downloader import VIDEO_SUFFIXES
from app.logger import setup_logging
from main import run_pipeline

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024 * 1024

jobs: dict[str, dict[str, Any]] = {}
jobs_lock = threading.Lock()
logger = setup_logging()


def _set_job(job_id: str, **values: Any) -> None:
    with jobs_lock:
        jobs.setdefault(job_id, {}).update(values)


def _run_job(job_id: str, source: str, max_clips: int) -> None:
    """Process one submitted video outside the request thread."""
    _set_job(job_id, status="processing", message="Transcribing and finding the best moments…")
    try:
        def report(stage: str, message: str) -> None:
            _set_job(job_id, status="processing", stage=stage, message=message)

        summary_path = run_pipeline(source, max_clips, progress_callback=report)
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        pipeline_job_id = summary["job_id"]
        for clip in summary["clips"]:
            clip["video_url"] = f"/media/{pipeline_job_id}/{clip['filename']}"
            clip["subtitle_url"] = f"/media/{pipeline_job_id}/{Path(clip['filename']).stem}.srt"
        _set_job(
            job_id,
            status="completed",
            message=f"Created {len(summary['clips'])} ready-to-post clip(s).",
            result=summary,
        )
    except Exception as exc:
        logger.exception("Web job %s failed", job_id)
        _set_job(job_id, status="failed", message=str(exc))


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.post("/api/jobs")
def create_job():
    ensure_directories()
    max_clips = request.form.get("max_clips", "3")
    try:
        max_clips_value = max(1, min(5, int(max_clips)))
    except ValueError:
        return jsonify({"error": "Maximum clips must be between 1 and 5."}), 400

    upload = request.files.get("video")
    url = request.form.get("url", "").strip()
    if upload and upload.filename:
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in VIDEO_SUFFIXES:
            return jsonify({"error": "Choose an MP4, MOV, MKV, WebM, AVI, or M4V video."}), 400
        upload_id = uuid.uuid4().hex
        name = secure_filename(upload.filename) or f"video{suffix}"
        upload_dir = UPLOADS_DIR / upload_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        upload_path = upload_dir / name
        upload.save(upload_path)
        source = str(upload_path)
        source_name = upload.filename
    elif url:
        if not url.startswith(("http://", "https://")):
            return jsonify({"error": "Enter a complete video URL beginning with http:// or https://."}), 400
        source = url
        source_name = url
    else:
        return jsonify({"error": "Upload a video or enter a video URL."}), 400

    job_id = uuid.uuid4().hex[:12]
    _set_job(
        job_id,
        status="queued",
        message="Your video is queued…",
        source_name=source_name,
    )
    threading.Thread(
        target=_run_job, args=(job_id, source, max_clips_value), daemon=True
    ).start()
    return jsonify({"job_id": job_id}), 202


@app.get("/api/jobs/<job_id>")
def get_job(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
        payload = dict(job) if job else None
    if payload is None:
        return jsonify({"error": "Job not found."}), 404
    return jsonify(payload)


@app.get("/media/<job_id>/<path:filename>")
def media(job_id: str, filename: str):
    return send_from_directory(OUTPUT_DIR / job_id, filename, as_attachment=False)


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "That video is larger than the 4 GB upload limit."}), 413


if __name__ == "__main__":
    ensure_directories()
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
