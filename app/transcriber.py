"""Timestamped speech-to-text using faster-whisper."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import TRANSCRIPTS_DIR, WHISPER_MODEL
from app.logger import get_logger
from app.utils import format_timestamp

logger = get_logger(__name__)


def _device_settings() -> tuple[str, str]:
    """Use CUDA when ctranslate2 reports an available GPU."""
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except (ImportError, RuntimeError, OSError):
        pass
    return "cpu", "int8"


def transcribe_video(video_path: Path, job_id: str) -> list[dict[str, Any]]:
    """Transcribe a video and save a readable timestamped transcript."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is not installed. Run: pip install -r requirements.txt"
        ) from exc
    device, compute_type = _device_settings()
    logger.info("Loading Whisper model '%s' on %s", WHISPER_MODEL, device)
    try:
        model = WhisperModel(WHISPER_MODEL, device=device, compute_type=compute_type)
    except Exception as exc:
        raise RuntimeError(
            f"Could not load Whisper model '{WHISPER_MODEL}'. Check the model name, "
            "internet connection, and available disk space."
        ) from exc
    try:
        segments, info = model.transcribe(
            str(video_path), beam_size=5, vad_filter=True, condition_on_previous_text=False
        )
        probability = float(info.language_probability or 0.0)
        logger.info("Detected language: %s (%.1f%%)", info.language, probability * 100)
        transcript: list[dict[str, Any]] = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                transcript.append({
                    "start": float(segment.start), "end": float(segment.end), "text": text,
                })
    except Exception as exc:
        raise RuntimeError(f"Whisper transcription failed for {video_path.name}: {exc}") from exc
    if not transcript:
        raise RuntimeError("No speech was detected in the video")

    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    transcript_path = TRANSCRIPTS_DIR / f"{job_id}.txt"
    blocks = [
        f"[{format_timestamp(item['start'])} - {format_timestamp(item['end'])}]\n{item['text']}"
        for item in transcript
    ]
    transcript_path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    logger.info("Transcription complete: %d segments", len(transcript))
    return transcript


def transcript_to_prompt(transcript: list[dict[str, Any]]) -> str:
    """Serialize transcript segments compactly for the model."""
    return "\n".join(
        f"[{format_timestamp(item['start'])}-{format_timestamp(item['end'])}] {item['text']}"
        for item in transcript
    )
