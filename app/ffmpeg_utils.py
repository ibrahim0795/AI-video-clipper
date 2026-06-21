"""FFmpeg and ffprobe helpers."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.utils import run_command


def check_media_tools() -> list[str]:
    """Return names of missing media executables."""
    return [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]


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


def validate_video(path: Path) -> None:
    """Ensure a path is a readable media file with positive duration."""
    if not path.is_file():
        raise FileNotFoundError(f"Video file not found: {path}")
    if get_video_duration(path) <= 0:
        raise ValueError(f"Video has no playable duration: {path}")
