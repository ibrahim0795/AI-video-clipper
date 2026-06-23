"""FFmpeg and ffprobe helpers."""

from __future__ import annotations

import json
import math
from pathlib import Path

from app.utils import resolve_media_executable, run_command


def check_media_tools() -> list[str]:
    """Return names of missing media executables."""
    return [name for name in ("ffmpeg", "ffprobe") if resolve_media_executable(name) is None]


def get_video_duration(path: Path) -> float:
    """Read media duration through ffprobe."""
    result = run_command(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "json", str(path),
        ],
        "probing video duration",
    )
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not determine duration of {path}") from exc


def validate_video(path: Path) -> float:
    """Ensure a path contains a readable video stream and return its duration."""
    if not path.is_file():
        raise FileNotFoundError(f"Video file not found: {path}")
    result = run_command(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration:stream=codec_type,width,height", "-of", "json", str(path),
        ],
        "validating video",
    )
    try:
        payload = json.loads(result.stdout)
        duration = float(payload["format"]["duration"])
        video_streams = [
            stream for stream in payload.get("streams", [])
            if stream.get("codec_type") == "video"
            and int(stream.get("width", 0)) > 0
            and int(stream.get("height", 0)) > 0
        ]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not validate video stream in {path}") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"Video has no playable duration: {path}")
    if not video_streams:
        raise ValueError(f"Media contains no playable video stream: {path}")
    return duration
