"""Normalize, enrich, and store clip metadata."""

from __future__ import annotations

from typing import Any

from app.config import OUTPUT_DIR
from app.utils import parse_timestamp, write_json


def transcript_excerpt(
    transcript: list[dict[str, Any]], start: float, end: float
) -> str:
    """Return only transcript text overlapping a clip."""
    return " ".join(
        str(item["text"]).strip() for item in transcript
        if float(item["end"]) > start and float(item["start"]) < end
    ).strip()


def save_metadata(job_id: str, clips: list[dict[str, Any]], transcript: list[dict[str, Any]]) -> None:
    """Store per-clip metadata, including its source transcript excerpt."""
    output_dir = OUTPUT_DIR / job_id
    for index, clip in enumerate(clips, 1):
        start = parse_timestamp(clip["start"])
        end = parse_timestamp(clip["end"])
        value = {
            "title": clip["title"], "hook": clip["hook"], "caption": clip["caption"],
            "description": clip["description"], "hashtags": clip["hashtags"],
            "transcript": transcript_excerpt(transcript, start, end),
        }
        write_json(output_dir / f"clip_{index}_metadata.json", value)
