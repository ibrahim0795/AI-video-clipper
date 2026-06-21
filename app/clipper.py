"""Cut source video into vertical short-form clips."""

from __future__ import annotations

from pathlib import Path

from app.config import (
    AUDIO_CODEC, HARDWARE_VIDEO_CODEC, OUTPUT_DIR, VIDEO_CODEC, VIDEO_CRF,
    VIDEO_HEIGHT, VIDEO_PRESET, VIDEO_WIDTH,
)
from app.captioner import build_subtitle_filter
from app.logger import get_logger
from app.utils import run_command

logger = get_logger(__name__)


def _encoding_args(codec: str) -> list[str]:
    """Return quality-oriented options supported by the selected encoder."""
    if codec == "h264_qsv":
        return ["-c:v", codec, "-preset", "veryfast", "-global_quality", "23"]
    return ["-c:v", VIDEO_CODEC, "-preset", VIDEO_PRESET, "-crf", str(VIDEO_CRF)]


def _run_clip_command(command: list[str], description: str, destination: Path) -> None:
    """Try Intel Quick Sync first and transparently fall back to libx264."""
    try:
        run_command(command, description)
    except RuntimeError as exc:
        if HARDWARE_VIDEO_CODEC not in command:
            raise
        logger.warning("Hardware encoding unavailable; retrying on CPU: %s", exc)
        if destination.exists():
            destination.unlink()
        codec_index = command.index("-c:v")
        quality_end = codec_index + 6
        command[codec_index:quality_end] = _encoding_args(VIDEO_CODEC)
        run_command(command, f"{description} (CPU fallback)")


def create_raw_clip(
    video_path: Path, job_id: str, clip_number: int, start: float, end: float
) -> Path:
    """Cut an exact interval and center-crop it to 9:16."""
    if end <= start:
        raise ValueError("Clip end time must be after start time")
    output_dir = OUTPUT_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"clip_{clip_number}_raw.mp4"
    video_filter = (
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}"
    )
    command = [
        "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(video_path),
        "-t", f"{end - start:.3f}", "-map", "0:v:0", "-map", "0:a?",
        "-vf", video_filter, *_encoding_args(HARDWARE_VIDEO_CODEC),
        "-c:a", AUDIO_CODEC, "-b:a", "192k",
        "-movflags", "+faststart", str(destination),
    ]
    _run_clip_command(command, f"creating clip {clip_number}", destination)
    logger.info("Created vertical clip: %s", destination)
    return destination


def create_final_clip(
    video_path: Path,
    job_id: str,
    clip_number: int,
    start: float,
    end: float,
    subtitle_path: Path | None,
) -> Path:
    """Cut, crop, caption, and encode a clip in a single FFmpeg pass."""
    if end <= start:
        raise ValueError("Clip end time must be after start time")
    output_dir = OUTPUT_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"clip_{clip_number}.mp4"
    filters = [
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase",
        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}",
    ]
    if subtitle_path is not None:
        filters.append(build_subtitle_filter(subtitle_path))
    command = [
        "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(video_path),
        "-t", f"{end - start:.3f}", "-map", "0:v:0", "-map", "0:a?",
        "-vf", ",".join(filters), *_encoding_args(HARDWARE_VIDEO_CODEC),
        "-c:a", AUDIO_CODEC, "-b:a", "160k", "-movflags", "+faststart",
        str(destination),
    ]
    _run_clip_command(command, f"exporting final clip {clip_number}", destination)
    logger.info("Exported final clip in one pass: %s", destination)
    return destination
