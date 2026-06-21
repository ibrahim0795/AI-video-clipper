"""Shared parsing, formatting, and subprocess helpers."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Sequence

from app.logger import get_logger

logger = get_logger(__name__)


def parse_timestamp(value: str | int | float) -> float:
    """Convert seconds or HH:MM:SS(.mmm) into seconds."""
    if isinstance(value, (int, float)):
        if value < 0:
            raise ValueError("Timestamp cannot be negative")
        return float(value)
    text = str(value).strip()
    if not text:
        raise ValueError("Timestamp cannot be empty")
    try:
        if ":" not in text:
            seconds = float(text)
            if seconds < 0:
                raise ValueError("Timestamp cannot be negative")
            return seconds
        parts = [float(part) for part in text.split(":")]
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp: {value}") from exc
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours, (minutes, seconds) = 0.0, parts
    else:
        raise ValueError(f"Invalid timestamp: {value}")
    if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
        raise ValueError(f"Invalid timestamp: {value}")
    return hours * 3600 + minutes * 60 + seconds


def format_timestamp(seconds: float, srt: bool = False) -> str:
    """Format seconds as HH:MM:SS or SRT HH:MM:SS,mmm."""
    seconds = max(0.0, float(seconds))
    total_ms = round(seconds * 1000)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    if srt:
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def parse_json_response(text: str) -> list[dict[str, Any]]:
    """Extract and validate a JSON clip list from a model response."""
    cleaned = text.strip().lstrip("\ufeff")
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("["), cleaned.rfind("]")
        if start < 0 or end <= start:
            raise ValueError("Gemini response did not contain a JSON array")
        try:
            value = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("Gemini returned invalid JSON") from exc
    if isinstance(value, dict) and isinstance(value.get("clips"), list):
        value = value["clips"]
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("Gemini response must be a JSON array of objects")
    return value


def run_command(command: Sequence[str], description: str) -> subprocess.CompletedProcess[str]:
    """Run an external command and raise a readable error on failure."""
    logger.debug("%s command: %s", description, subprocess.list2cmdline(list(command)))
    try:
        return subprocess.run(
            list(command), check=True, capture_output=True, text=True, encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required executable not found while running {description}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "Unknown error").strip()
        raise RuntimeError(f"{description} failed: {detail}") from exc


def write_json(path: Path, value: Any) -> None:
    """Write UTF-8 JSON atomically enough for a local CLI."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
