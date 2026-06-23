"""Cut source video into vertical short-form clips."""

from __future__ import annotations

from pathlib import Path

from app.config import (
    AUDIO_CODEC, HARDWARE_VIDEO_CODEC, OUTPUT_DIR, VIDEO_CODEC, VIDEO_CRF,
    USE_BLUR_BACKGROUND, VIDEO_HEIGHT, VIDEO_PRESET, VIDEO_WIDTH,
)
from app.captioner import build_subtitle_filter
from app.logger import get_logger
from app.utils import run_command

logger = get_logger(__name__)


def _vertical_filter_graph(subtitle_path: Path | None = None) -> tuple[str, str]:
    """Compose a full-frame landscape source on a 9:16 canvas without cropping it."""
    if USE_BLUR_BACKGROUND:
        graph = (
            f"[0:v]split=2[background_source][foreground_source];"
            f"[background_source]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:"
            f"force_original_aspect_ratio=increase,crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
            "boxblur=luma_radius=30:luma_power=2,"
            "eq=brightness=-0.18:saturation=0.75[background];"
            f"[foreground_source]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:"
            "force_original_aspect_ratio=decrease[foreground];"
            "[background][foreground]overlay=(W-w)/2:(H-h)/2[composed]"
        )
    else:
        graph = (
            f"[0:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black[composed]"
        )
    if subtitle_path is None:
        return graph, "[composed]"
    graph += f";[composed]{build_subtitle_filter(subtitle_path)}[captioned]"
    return graph, "[captioned]"


def _encoding_args(codec: str) -> list[str]:
    """Return quality-oriented options supported by the selected encoder."""
    if codec.endswith("_qsv"):
        return ["-c:v", codec, "-preset", "veryfast", "-global_quality", "23"]
    return ["-c:v", codec, "-preset", VIDEO_PRESET, "-crf", str(VIDEO_CRF)]


def _run_clip_command(command: list[str], description: str, destination: Path) -> None:
    """Try Intel Quick Sync first and transparently fall back to libx264."""
    try:
        run_command(command, description)
    except RuntimeError as exc:
        if HARDWARE_VIDEO_CODEC == VIDEO_CODEC or HARDWARE_VIDEO_CODEC not in command:
            raise
        logger.warning("Hardware encoding unavailable; retrying on CPU: %s", exc)
        if destination.exists():
            destination.unlink()
        codec_index = command.index("-c:v")
        audio_index = command.index("-c:a", codec_index)
        command[codec_index:audio_index] = _encoding_args(VIDEO_CODEC)
        run_command(command, f"{description} (CPU fallback)")


def create_raw_clip(
    video_path: Path, job_id: str, clip_number: int, start: float, end: float
) -> Path:
    """Cut an exact interval onto a full-frame vertical canvas."""
    if end <= start:
        raise ValueError("Clip end time must be after start time")
    output_dir = OUTPUT_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"clip_{clip_number}_raw.mp4"
    filter_graph, video_output = _vertical_filter_graph()
    command = [
        "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(video_path),
        "-t", f"{end - start:.3f}", "-filter_complex", filter_graph,
        "-map", video_output, "-map", "0:a:0?", *_encoding_args(HARDWARE_VIDEO_CODEC),
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
    """Cut, compose, caption, and encode a full-frame clip in one pass."""
    if end <= start:
        raise ValueError("Clip end time must be after start time")
    output_dir = OUTPUT_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"clip_{clip_number}.mp4"
    filter_graph, video_output = _vertical_filter_graph(subtitle_path)
    command = [
        "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(video_path),
        "-t", f"{end - start:.3f}", "-filter_complex", filter_graph,
        "-map", video_output, "-map", "0:a:0?", *_encoding_args(HARDWARE_VIDEO_CODEC),
        "-c:a", AUDIO_CODEC, "-b:a", "160k", "-movflags", "+faststart",
        str(destination),
    ]
    _run_clip_command(command, f"exporting final clip {clip_number}", destination)
    logger.info("Exported final clip in one pass: %s", destination)
    return destination
