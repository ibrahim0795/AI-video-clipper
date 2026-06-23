"""Groq-powered football moment detection with validated fallback clips."""

from __future__ import annotations

import time
from typing import Any

from app.config import (
    ABSOLUTE_MAX_DURATION,
    AI_RETRIES,
    AI_RETRY_DELAY,
    GROQ_API_KEY,
    GROQ_MODEL,
    MAX_CLIPS,
    MIN_CLIP_DURATION,
    PREFERRED_MAX_DURATION,
)
from app.logger import get_logger
from app.transcriber import transcript_to_prompt
from app.utils import format_timestamp, parse_json_response, parse_timestamp

logger = get_logger(__name__)
PLACEHOLDER_API_KEYS = {"your_api_key_here", "your_real_api_key", "replace_me"}

PROMPT = """You are an expert football highlight editor and social media strategist.

Analyze this timestamped football transcript and select the moments most likely to perform well on
YouTube Shorts, Instagram Reels, and TikTok.

Prioritize goals, celebrations, emotional moments, funny moments, incredible skills, controversies,
crowd reactions, player introductions, lineup reveals, dramatic commentary, penalties, free kicks,
cards, substitutions, final-whistle moments, turning points, interviews, and iconic reactions.

Rules:
- Return no more than {max_clips} clips (normally 3 to 5 when that many strong moments exist).
- Prefer durations between 30 and 60 seconds.
- A sequence may extend up to 180 seconds when buildup, action, and reaction are all important.
- Never exceed 180 seconds and never create a clip shorter than 30 seconds.
- Include enough buildup and reaction to make each event understandable.
- Use timestamps that actually exist in the transcript.
- Do not return duplicate or overlapping moments.
- Return valid JSON only, with no markdown or explanation.
- Return an object with a "clips" array.
- Each clip object must contain start_time, end_time, viral_score (1-10), reason, title, hook,
  caption, description, and hashtags (an array of strings).

Transcript:
{transcript}
"""


def _extend_to_minimum(start: float, end: float, video_duration: float) -> tuple[float, float]:
    """Extend a short selection around its event while staying within the source."""
    if end - start >= MIN_CLIP_DURATION:
        return start, end
    missing = MIN_CLIP_DURATION - (end - start)
    start = max(0.0, start - missing / 2)
    end = min(video_duration, start + MIN_CLIP_DURATION)
    start = max(0.0, end - MIN_CLIP_DURATION)
    return start, end


def _normalize_clip(item: dict[str, Any], video_duration: float) -> dict[str, Any] | None:
    """Clamp model timestamps and normalize all metadata fields."""
    if video_duration < MIN_CLIP_DURATION:
        return None
    try:
        start = max(0.0, parse_timestamp(item.get("start_time", item.get("start", 0))))
        end = min(video_duration, parse_timestamp(item.get("end_time", item.get("end", 0))))
    except (TypeError, ValueError):
        return None
    if end <= start:
        return None
    start, end = _extend_to_minimum(start, end, video_duration)
    if end - start > ABSOLUTE_MAX_DURATION:
        end = min(video_duration, start + ABSOLUTE_MAX_DURATION)

    hashtags = item.get("hashtags", [])
    if isinstance(hashtags, str):
        hashtags = hashtags.split()
    elif not isinstance(hashtags, (list, tuple, set)):
        hashtags = []
    hashtags = [
        str(tag).strip() if str(tag).strip().startswith("#") else f"#{str(tag).strip()}"
        for tag in hashtags
        if str(tag).strip()
    ][:12]
    try:
        score = max(1, min(10, round(float(item.get("viral_score", 5)))))
    except (TypeError, ValueError):
        score = 5

    def text_field(name: str, default: str, limit: int) -> str:
        value = item.get(name)
        cleaned = " ".join(str(value).split()) if value is not None else ""
        return (cleaned or default)[:limit]

    return {
        "start": start,
        "end": end,
        "start_time": format_timestamp(start),
        "end_time": format_timestamp(end),
        "viral_score": score,
        "reason": text_field("reason", "Engaging football moment", 500),
        "title": text_field("title", "A football moment you need to see", 180),
        "hook": text_field("hook", "Watch what happens next...", 300),
        "caption": text_field("caption", "This moment deserves a replay.", 2_200),
        "description": text_field(
            "description", "A football highlight optimized for short-form video.", 5_000
        ),
        "hashtags": hashtags or ["#football", "#shorts", "#viral"],
        "selection_source": str(item.get("selection_source", "groq")),
    }


def select_distinct_clips(
    items: list[dict[str, Any]], video_duration: float, max_clips: int
) -> list[dict[str, Any]]:
    """Normalize, score-sort, and remove duplicate or overlapping selections."""
    normalized = [
        clip for item in items
        if (clip := _normalize_clip(item, video_duration)) is not None
    ]
    normalized.sort(key=lambda clip: (-clip["viral_score"], clip["start"]))
    selected: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for clip in normalized:
        title_key = " ".join(clip["title"].lower().split())
        overlaps = any(clip["start"] < kept["end"] and kept["start"] < clip["end"] for kept in selected)
        if title_key in seen_titles or overlaps:
            logger.info(
                "Discarding duplicate/overlapping selection %s-%s: %s",
                clip["start_time"], clip["end_time"], clip["title"],
            )
            continue
        selected.append(clip)
        seen_titles.add(title_key)
        if len(selected) >= min(max_clips, MAX_CLIPS):
            break
    return selected


def fallback_clips(video_duration: float, max_clips: int) -> list[dict[str, Any]]:
    """Distribute 30-45 second fallback windows across the source."""
    if video_duration < MIN_CLIP_DURATION:
        return []
    count = min(max_clips, MAX_CLIPS, max(1, int(video_duration // MIN_CLIP_DURATION)))
    clip_duration = min(PREFERRED_MAX_DURATION, video_duration / count)
    available_start_range = max(0.0, video_duration - clip_duration)
    starts = [
        0.0 if count == 1 else index * available_start_range / (count - 1)
        for index in range(count)
    ]
    items = [
        {
            "start": start,
            "end": min(video_duration, start + clip_duration),
            "viral_score": 3,
            "reason": "Fallback sample because Groq analysis was unavailable",
            "title": f"Fallback football segment {index + 1}",
            "hook": "A moment from the match...",
            "caption": "Automatically sampled while AI analysis was unavailable.",
            "description": "A fallback football segment selected without Groq analysis.",
            "hashtags": ["#football", "#shorts"],
            "selection_source": "fallback",
        }
        for index, start in enumerate(starts)
    ]
    clips = select_distinct_clips(items, video_duration, max_clips)
    logger.warning("Fallback mode selected %d distributed clip(s)", len(clips))
    return clips


def detect_viral_clips(
    transcript: list[dict[str, Any]], video_duration: float, max_clips: int
) -> list[dict[str, Any]]:
    """Ask Groq for event-driven selections, falling back only after total failure."""
    if not GROQ_API_KEY or GROQ_API_KEY.lower() in PLACEHOLDER_API_KEYS:
        logger.warning("GROQ_API_KEY is missing or still a placeholder; fallback mode enabled")
        return fallback_clips(video_duration, max_clips)
    try:
        from groq import Groq
    except ImportError:
        logger.exception("groq is not installed; fallback mode enabled")
        return fallback_clips(video_duration, max_clips)

    prompt = PROMPT.format(max_clips=min(max_clips, MAX_CLIPS), transcript=transcript_to_prompt(transcript))
    client = Groq(api_key=GROQ_API_KEY, timeout=60.0)
    for attempt in range(1, AI_RETRIES + 1):
        try:
            logger.info("Requesting football moment analysis from Groq (attempt %d/%d)", attempt, AI_RETRIES)
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a precise football highlight editor. "
                            "Return only valid JSON. No markdown, no commentary."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.25,
                response_format={"type": "json_object"},
            )
            response_text = response.choices[0].message.content if response.choices else ""
            if not response_text:
                raise ValueError("Groq returned an empty response")
            raw_items = parse_json_response(response_text)
            logger.debug("Groq returned %d candidate object(s)", len(raw_items))
            selected = select_distinct_clips(raw_items, video_duration, max_clips)
            if not selected:
                raise ValueError("Groq returned no valid, distinct clips")
            for clip in selected:
                clip["selection_source"] = "groq"
                logger.info(
                    "Selected %s-%s (%.1fs, score %d): %s",
                    clip["start_time"], clip["end_time"], clip["end"] - clip["start"],
                    clip["viral_score"], clip["reason"],
                )
            logger.info("Groq selection succeeded; fallback mode was not used")
            return selected
        except Exception as exc:  # API libraries expose several transport errors.
            logger.warning("Groq analysis failed: %s", exc)
            error_text = str(exc).upper()
            if any(marker in error_text for marker in ("AUTHENTICATION", "INVALID_API_KEY", "INVALID_ARGUMENT", " 401", " 403", " 404")):
                logger.error("Groq returned a permanent error; skipping further retries")
                break
            if attempt < AI_RETRIES:
                time.sleep(AI_RETRY_DELAY * attempt)
    logger.error("Groq failed completely; fallback mode enabled")
    return fallback_clips(video_duration, max_clips)
