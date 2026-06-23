"""Create SRT captions and burn them into video clips."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from app.config import (
    AUDIO_CODEC, SUBTITLE_FONT_SIZE, SUBTITLE_MARGIN_V, SUBTITLE_MAX_CHARS,
    VIDEO_CODEC, VIDEO_CRF, VIDEO_HEIGHT, VIDEO_PRESET, VIDEO_WIDTH,
)
from app.logger import get_logger
from app.utils import format_timestamp, run_command

logger = get_logger(__name__)
ASS_REFERENCE_HEIGHT = 288


def _subtitle_chunks(text: str) -> list[str]:
    """Split a long caption into sequential cues of at most two lines."""
    lines = textwrap.wrap(
        " ".join(text.split()), width=SUBTITLE_MAX_CHARS,
        break_long_words=False, break_on_hyphens=False,
    )
    return ["\n".join(lines[index : index + 2]) for index in range(0, len(lines), 2)]


def generate_srt(
    transcript: list[dict[str, Any]], clip_start: float, clip_end: float, destination: Path
) -> int:
    """Write transcript segments overlapping a clip, shifted to clip-relative time."""
    if clip_start < 0 or clip_end <= clip_start:
        raise ValueError("Subtitle clip range must have a non-negative start and end after start")
    entries: list[str] = []
    for segment in transcript:
        start = max(float(segment["start"]), clip_start)
        end = min(float(segment["end"]), clip_end)
        if end <= start or not str(segment.get("text", "")).strip():
            continue
        relative_start = start - clip_start
        relative_end = end - clip_start
        chunks = _subtitle_chunks(str(segment["text"]))
        if not chunks:
            continue
        chunk_duration = (relative_end - relative_start) / len(chunks)
        for index, chunk in enumerate(chunks):
            cue_start = relative_start + index * chunk_duration
            cue_end = relative_start + (index + 1) * chunk_duration
            entries.append(
                f"{len(entries) + 1}\n"
                f"{format_timestamp(cue_start, srt=True)} --> {format_timestamp(cue_end, srt=True)}\n"
                f"{chunk}\n"
            )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(entries), encoding="utf-8")
    return len(entries)


def _escape_subtitle_path(path: Path) -> str:
    """Escape a path for FFmpeg's subtitles filter on Windows and POSIX."""
    value = path.resolve().as_posix()
    return value.replace("'", r"\'").replace(":", r"\:").replace("[", r"\[").replace("]", r"\]")


def build_subtitle_filter(subtitle_path: Path) -> str:
    """Build a correctly scaled libass filter for a vertical output."""
    # Plain SRT files have no script resolution, so libass uses a 288-line
    # reference canvas. Convert output-pixel settings into that coordinate space.
    ass_scale = ASS_REFERENCE_HEIGHT / VIDEO_HEIGHT
    ass_font_size = SUBTITLE_FONT_SIZE * ass_scale
    ass_margin_v = round(SUBTITLE_MARGIN_V * ass_scale)
    ass_outline = max(0.5, 3 * ass_scale)
    style = (
        f"FontName=Arial,FontSize={ass_font_size:.2f},PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H00000000,BorderStyle=1,Outline={ass_outline:.2f},Shadow=0,"
        f"Alignment=2,MarginV={ass_margin_v}"
    )
    return (
        f"subtitles='{_escape_subtitle_path(subtitle_path)}':"
        f"original_size={VIDEO_WIDTH}x{VIDEO_HEIGHT}:force_style='{style}'"
    )


def burn_subtitles(raw_clip: Path, subtitle_path: Path, destination: Path) -> Path:
    """Burn styled subtitles into a raw vertical clip."""
    subtitle_filter = build_subtitle_filter(subtitle_path)
    run_command([
        "ffmpeg", "-y", "-i", str(raw_clip), "-map", "0:v:0", "-map", "0:a:0?",
        "-vf", subtitle_filter,
        "-c:v", VIDEO_CODEC, "-preset", VIDEO_PRESET, "-crf", str(VIDEO_CRF),
        "-c:a", AUDIO_CODEC, "-b:a", "192k", "-movflags", "+faststart", str(destination),
    ], f"burning subtitles into {destination.name}")
    logger.info("Burned subtitles: %s", destination)
    return destination
