"""Gemini-powered viral moment detection with deterministic fallback."""

from __future__ import annotations

import time
from typing import Any

from app.config import (
    ABSOLUTE_MAX_CLIP_SECONDS, GEMINI_API_KEY, GEMINI_MODEL, GEMINI_RETRIES,
    GEMINI_RETRY_DELAY, MIN_CLIP_SECONDS,
)
from app.logger import get_logger
from app.transcriber import transcript_to_prompt
from app.utils import format_timestamp, parse_json_response, parse_timestamp

logger = get_logger(__name__)

PROMPT = """You are an expert social media strategist that creates viral football short videos.
Analyze the timestamped transcript and identify the best moments for Instagram Reels, TikTok, and YouTube Shorts.
Prioritize goals, celebrations, emotional or funny moments, arguments, surprising facts, incredible skills,
strong hooks, and controversial opinions.

Rules:
- Return at most {max_clips} clips.
- Prefer durations of 20-45 seconds; never exceed 60 seconds or use less than 15 seconds.
- Use timestamps that exist in the transcript.
- Return valid JSON only, with no markdown or explanation.
- Each object must contain start_time, end_time, viral_score (1-10), reason, title, hook,
  caption, description, and hashtags (an array of strings).

Transcript:
{transcript}
"""


def _normalize_clip(item: dict[str, Any], video_duration: float) -> dict[str, Any] | None:
    try:
        start = max(0.0, parse_timestamp(item.get("start_time", item.get("start", 0))))
        end = min(video_duration, parse_timestamp(item.get("end_time", item.get("end", 0))))
    except (TypeError, ValueError):
        return None
    if end - start < MIN_CLIP_SECONDS:
        return None
    if end - start > ABSOLUTE_MAX_CLIP_SECONDS:
        end = start + ABSOLUTE_MAX_CLIP_SECONDS
    hashtags = item.get("hashtags", [])
    if isinstance(hashtags, str):
        hashtags = hashtags.split()
    hashtags = [str(tag) if str(tag).startswith("#") else f"#{tag}" for tag in hashtags]
    try:
        score = max(1, min(10, int(item.get("viral_score", 5))))
    except (TypeError, ValueError):
        score = 5
    return {
        "start": start,
        "end": end,
        "start_time": format_timestamp(start),
        "end_time": format_timestamp(end),
        "viral_score": score,
        "reason": str(item.get("reason", "Engaging moment from the video")),
        "title": str(item.get("title", "A moment you need to see")),
        "hook": str(item.get("hook", "Wait for this moment...")),
        "caption": str(item.get("caption", "This moment deserves a replay.")),
        "description": str(item.get("description", "A highlight optimized for short-form video.")),
        "hashtags": hashtags or ["#shorts", "#viral", "#video"],
    }


def fallback_clips(video_duration: float, max_clips: int) -> list[dict[str, Any]]:
    """Create consecutive 30-second clips when Gemini is unavailable."""
    clips: list[dict[str, Any]] = []
    for index in range(max_clips):
        start = index * 30.0
        if video_duration - start < MIN_CLIP_SECONDS:
            break
        end = min(start + 30.0, video_duration)
        clips.append(_normalize_clip({
            "start": start, "end": end, "viral_score": 5,
            "reason": "Automatic fallback segment",
            "title": f"Video highlight {index + 1}",
            "hook": "Watch what happens next...",
            "caption": "A moment worth sharing.",
            "description": "An automatically selected highlight from the source video.",
            "hashtags": ["#shorts", "#reels", "#tiktok", "#viral"],
        }, video_duration))
    return [clip for clip in clips if clip is not None]


def detect_viral_clips(
    transcript: list[dict[str, Any]], video_duration: float, max_clips: int
) -> list[dict[str, Any]]:
    """Ask Gemini for clip selections, retrying before using fallback clips."""
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is missing; using fallback clip selection")
        return fallback_clips(video_duration, max_clips)
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.exception("google-genai is not installed; using fallback clips")
        return fallback_clips(video_duration, max_clips)

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = PROMPT.format(max_clips=max_clips, transcript=transcript_to_prompt(transcript))
    for attempt in range(1, GEMINI_RETRIES + 1):
        try:
            logger.info("Requesting clip analysis from Gemini (attempt %d/%d)", attempt, GEMINI_RETRIES)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", temperature=0.3
                ),
            )
            raw_items = parse_json_response(response.text)
            normalized = [
                clip for item in raw_items
                if (clip := _normalize_clip(item, video_duration)) is not None
            ][:max_clips]
            if normalized:
                return normalized
            raise ValueError("Gemini returned no clips with valid durations")
        except Exception as exc:  # API libraries expose several transport errors.
            logger.warning("Gemini analysis failed: %s", exc)
            error_text = str(exc).upper()
            if any(marker in error_text for marker in ("PERMISSION_DENIED", "INVALID_ARGUMENT", " 403", " 404")):
                logger.error("Gemini returned a permanent error; skipping further retries")
                break
            if attempt < GEMINI_RETRIES:
                time.sleep(GEMINI_RETRY_DELAY)
    logger.error("Gemini retries exhausted; using fallback clip selection")
    return fallback_clips(video_duration, max_clips)
