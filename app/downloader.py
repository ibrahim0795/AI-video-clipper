"""Resolve local videos and download supported remote URLs."""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path
from urllib.parse import urlparse

from app.config import DOWNLOADS_DIR
from app.logger import get_logger

logger = get_logger(__name__)
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def _is_web_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def get_video(source: str, job_id: str | None = None) -> tuple[Path, str]:
    """Copy a local video or download a URL into a job directory."""
    job_id = job_id or uuid.uuid4().hex[:12]
    job_dir = DOWNLOADS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    local = Path(source).expanduser()
    if local.is_file():
        if local.suffix.lower() not in VIDEO_SUFFIXES:
            raise ValueError(f"Unsupported video extension: {local.suffix or '(none)'}")
        destination = job_dir / f"original{local.suffix.lower()}"
        if local.resolve() != destination.resolve():
            shutil.copy2(local, destination)
        logger.info("Loaded local video: %s", destination)
        return destination, job_id

    if not _is_web_url(source):
        raise ValueError("Input must be an existing local video or a valid HTTP(S) URL")

    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
    except ImportError as exc:
        raise RuntimeError("yt-dlp is not installed. Run: pip install -r requirements.txt") from exc

    output_template = str(job_dir / "download.%(ext)s")
    options = {
        # The final output is 1080 pixels wide, so downloading 1440p/4K only
        # wastes bandwidth, storage, transcription time, and decode cycles.
        "format": "bv*[height<=1080]+ba/b[height<=1080]/b",
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": False,
        "progress_hooks": [lambda data: logger.debug("Download status: %s", data.get("status"))],
    }
    logger.info("Downloading video: %s", re.sub(r"([?&]t=)[^&]+", r"\1...", source))
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(source, download=True)
            prepared = Path(ydl.prepare_filename(info))
    except DownloadError as exc:
        raise RuntimeError(f"Video download failed: {exc}") from exc
    candidates = [job_dir / "download.mp4", prepared]
    downloaded = next((path for path in candidates if path.exists()), None)
    if downloaded is None:
        matches = list(job_dir.glob("download.*"))
        downloaded = matches[0] if matches else None
    if downloaded is None:
        raise RuntimeError("Download completed but no video file was produced")
    destination = job_dir / "original.mp4"
    if downloaded != destination:
        downloaded.replace(destination)
    logger.info("Download complete: %s", destination)
    return destination, job_id
