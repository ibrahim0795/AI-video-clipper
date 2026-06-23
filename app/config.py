"""Central configuration for paths and media settings."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

DOWNLOADS_DIR = ROOT_DIR / "downloads"
TRANSCRIPTS_DIR = ROOT_DIR / "transcripts"
OUTPUT_DIR = ROOT_DIR / "output"
LOGS_DIR = ROOT_DIR / "logs"
UPLOADS_DIR = ROOT_DIR / "uploads"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny")

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_CODEC = "libx264"
HARDWARE_VIDEO_CODEC = os.getenv("HARDWARE_VIDEO_CODEC", "h264_qsv")
AUDIO_CODEC = "aac"
VIDEO_CRF = 22
VIDEO_PRESET = "veryfast"

SUBTITLE_FONT_SIZE = 48
SUBTITLE_MARGIN_V = 100
SUBTITLE_MAX_CHARS = 42

MIN_CLIP_DURATION = 30.0
PREFERRED_MAX_DURATION = 60.0
ABSOLUTE_MAX_DURATION = 180.0
MAX_CLIPS = 5
DEFAULT_MAX_CLIPS = MAX_CLIPS
USE_BLUR_BACKGROUND = os.getenv("USE_BLUR_BACKGROUND", "true").lower() in {
    "1", "true", "yes", "on",
}
AI_RETRIES = 3
AI_RETRY_DELAY = 5


def ensure_directories() -> None:
    """Create all runtime directories if they do not exist."""
    for directory in (DOWNLOADS_DIR, TRANSCRIPTS_DIR, OUTPUT_DIR, LOGS_DIR, UPLOADS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
