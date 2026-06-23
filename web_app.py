"""Responsive local web interface for AI Video Clipper."""

from __future__ import annotations

import json
import re
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from app.config import OUTPUT_DIR, UPLOADS_DIR, ensure_directories
from app.downloader import VIDEO_SUFFIXES, is_web_url, safe_source_label
from app.logger import setup_logging
from main import run_pipeline

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024 * 1024

jobs: dict[str, dict[str, Any]] = {}
jobs_lock = threading.Lock()
job_worker = threading.Semaphore(1)
logger = setup_logging()


def _set_job(job_id: str, **values: Any) -> None:
    with jobs_lock:
        jobs.setdefault(job_id, {}).update(values)


def _run_job(job_id: str, source: str, max_clips: int) -> None:
    """Process one submitted video outside the request thread."""
    try:
        with job_worker:
            _set_job(job_id, status="processing", message="Preparing your video...")

            def report(stage: str, message: str) -> None:
                _set_job(job_id, status="processing", stage=stage, message=message)

            summary_path = run_pipeline(source, max_clips, progress_callback=report)
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary.pop("local_video", None)
            pipeline_job_id = summary["job_id"]
            for clip in summary["clips"]:
                clip["video_url"] = f"/media/{pipeline_job_id}/{clip['filename']}"
                clip["subtitle_url"] = f"/media/{pipeline_job_id}/{Path(clip['filename']).stem}.srt"
            used_fallback = any(
                clip.get("selection_source") == "fallback" for clip in summary["clips"]
            )
            completion_message = f"Created {len(summary['clips'])} ready-to-post clip(s)."
            if used_fallback:
                completion_message += " Groq was unavailable, so these are distributed fallback samples."
            _set_job(
                job_id,
                status="completed",
                message=completion_message,
                result=summary,
            )
    except Exception as exc:
        logger.exception("Web job %s failed", job_id)
        _set_job(job_id, status="failed", message=str(exc))
    finally:
        try:
            source_path = Path(source).resolve()
            uploads_root = UPLOADS_DIR.resolve()
            if source_path.is_relative_to(uploads_root):
                shutil.rmtree(source_path.parent, ignore_errors=True)
        except (OSError, ValueError):
            logger.warning("Could not clean temporary upload for web job %s", job_id)


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.post("/api/jobs")
def create_job():
    ensure_directories()
    max_clips = request.form.get("max_clips", "3")
    try:
        max_clips_value = int(max_clips)
        if not 1 <= max_clips_value <= 5:
            raise ValueError
    except (TypeError, ValueError):
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
        try:
            upload.save(upload_path)
        except OSError as exc:
            shutil.rmtree(upload_dir, ignore_errors=True)
            logger.exception("Could not save uploaded video")
            return jsonify({"error": f"Could not save uploaded video: {exc}"}), 500
        source = str(upload_path)
        source_name = upload.filename
    elif url:
        if not is_web_url(url):
            return jsonify({"error": "Enter a complete video URL beginning with http:// or https://."}), 400
        source = url
        source_name = safe_source_label(url)
    else:
        return jsonify({"error": "Upload a video or enter a video URL."}), 400

    job_id = uuid.uuid4().hex[:12]
    with jobs_lock:
        if len(jobs) >= 100:
            removable = next(
                (key for key, value in jobs.items() if value.get("status") in {"completed", "failed"}),
                None,
            )
            if removable:
                jobs.pop(removable, None)
            else:
                if upload and upload.filename:
                    shutil.rmtree(Path(source).parent, ignore_errors=True)
                return jsonify({"error": "The local processing queue is full. Try again later."}), 503
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
    # Pipeline job IDs are always 12 lowercase hexadecimal characters. Validate
    # the directory component itself before handing the filename to Flask's
    # safe send_from_directory implementation.
    if re.fullmatch(r"[0-9a-f]{12}", job_id) is None:
        abort(404)
    return send_from_directory(OUTPUT_DIR / job_id, filename, as_attachment=False)


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "That video is larger than the 4 GB upload limit."}), 413


@app.errorhandler(500)
def internal_error(_error):
    return jsonify({"error": "The local server encountered an unexpected error. Check logs/app.log."}), 500


if __name__ == "__main__":
    ensure_directories()
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
