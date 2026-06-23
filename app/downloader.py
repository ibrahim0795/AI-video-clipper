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
JOB_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")


def is_web_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def safe_source_label(value: str) -> str:
    """Remove query strings and credentials before writing a URL to logs."""
    if not is_web_url(value):
        return value
    parsed = urlparse(value)
    host = parsed.hostname or parsed.netloc
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return parsed._replace(netloc=host, query="", fragment="").geturl()


def validate_source(source: str) -> None:
    """Reject missing local paths and malformed URLs before expensive setup."""
    if not source or not source.strip():
        raise ValueError("Video source cannot be empty")
    local = Path(source).expanduser()
    if local.is_file():
        if local.suffix.lower() not in VIDEO_SUFFIXES:
            raise ValueError(f"Unsupported video extension: {local.suffix or '(none)'}")
        return
    if is_web_url(source):
        return
    raise ValueError(f"Video file does not exist or URL is invalid: {source}")


def _download_options(job_dir: Path) -> dict[str, object]:
    """Build conservative yt-dlp options with an available JavaScript runtime."""
    options: dict[str, object] = {
        # The final output is 1080 pixels wide, so downloading 1440p/4K only
        # wastes bandwidth, storage, transcription time, and decode cycles.
        "format": "bv*[height<=1080]+ba/b[height<=1080]/b",
        "merge_output_format": "mp4",
        "outtmpl": str(job_dir / "download.%(ext)s"),
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "progress_hooks": [lambda data: logger.debug("Download status: %s", data.get("status"))],
    }
    node = shutil.which("node")
    if node:
        options["js_runtimes"] = {"node": {"path": node}}
    return options


def get_video(source: str, job_id: str | None = None) -> tuple[Path, str]:
    """Copy a local video or download a URL into a job directory."""
    job_id = job_id or uuid.uuid4().hex[:12]
    if JOB_ID_PATTERN.fullmatch(job_id) is None:
        raise ValueError("Invalid job ID")

    validate_source(source)
    local = Path(source).expanduser()
    if local.is_file():
        job_dir = DOWNLOADS_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        destination = job_dir / f"original{local.suffix.lower()}"
        if local.resolve() != destination.resolve():
            shutil.copy2(local, destination)
        logger.info("Loaded local video: %s", destination)
        return destination, job_id

    job_dir = DOWNLOADS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
    except ImportError as exc:
        raise RuntimeError("yt-dlp is not installed. Run: pip install -r requirements.txt") from exc

    options = _download_options(job_dir)
    logger.info("Downloading video: %s", safe_source_label(source))
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(source, download=True)
            prepared = Path(ydl.prepare_filename(info))
    except DownloadError as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise RuntimeError(f"Video download failed: {exc}") from exc
    except Exception as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise RuntimeError(f"Video download failed unexpectedly: {exc}") from exc
    candidates = [job_dir / "download.mp4", prepared]
    downloaded = next(
        (path for path in candidates if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES),
        None,
    )
    if downloaded is None:
        matches = [
            path for path in job_dir.glob("download.*")
            if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES
        ]
        downloaded = matches[0] if matches else None
    if downloaded is None:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise RuntimeError("Download completed but no video file was produced")
    destination = job_dir / f"original{downloaded.suffix.lower()}"
    if downloaded != destination:
        downloaded.replace(destination)
    logger.info("Download complete: %s", destination)
    return destination, job_id
