"""Command-line entry point for AI Video Clipper."""

from __future__ import annotations

import argparse
import shutil
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any, Callable

from app.ai_detector import detect_viral_clips
from app.captioner import burn_subtitles, generate_srt
from app.clipper import create_final_clip, create_raw_clip
from app.config import DEFAULT_MAX_CLIPS, OUTPUT_DIR, ensure_directories
from app.downloader import get_video
from app.ffmpeg_utils import check_media_tools, get_video_duration, validate_video
from app.logger import setup_logging
from app.metadata_generator import save_metadata
from app.transcriber import transcribe_video
from app.utils import write_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Turn a long video into captioned vertical clips.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--video", help="Path to a local video")
    source.add_argument("--url", help="YouTube or another yt-dlp-supported URL")
    parser.add_argument("--max-clips", type=int, default=DEFAULT_MAX_CLIPS, choices=range(1, 6))
    parser.add_argument("--keep-raw", action="store_true", help="Keep intermediate raw clips")
    parser.add_argument("--verbose", action="store_true")
    return parser


ProgressCallback = Callable[[str, str], None]


def run_pipeline(
    source: str,
    max_clips: int,
    keep_raw: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """Run the complete clipping pipeline and return summary.json."""
    logger = setup_logging()
    def progress(stage: str, message: str) -> None:
        if progress_callback:
            progress_callback(stage, message)

    ensure_directories()
    missing = check_media_tools()
    if missing:
        raise RuntimeError(
            f"Missing required tools: {', '.join(missing)}. Install FFmpeg and ensure both "
            "ffmpeg and ffprobe are available on PATH. See https://ffmpeg.org/download.html"
        )

    job_id = uuid.uuid4().hex[:12]
    progress("download", "Loading or downloading your source video…")
    video_path, job_id = get_video(source, job_id)
    validate_video(video_path)
    duration = get_video_duration(video_path)
    progress("transcribe", "Transcribing speech locally with Whisper…")
    transcript = transcribe_video(video_path, job_id)
    progress("analyze", "Finding the strongest moments with Gemini…")
    candidates = detect_viral_clips(transcript, duration, max_clips)
    if not candidates:
        raise RuntimeError("The video is too short to create a clip of at least 15 seconds")

    completed: list[dict[str, Any]] = []
    for candidate in candidates:
        number = len(completed) + 1
        raw_path: Path | None = None
        try:
            progress("export", f"Rendering clip {number} of {len(candidates)}…")
            output_dir = OUTPUT_DIR / job_id
            subtitle_path = output_dir / f"clip_{number}.srt"
            subtitle_count = generate_srt(
                transcript, candidate["start"], candidate["end"], subtitle_path
            )
            if keep_raw:
                raw_path = create_raw_clip(
                    video_path, job_id, number, candidate["start"], candidate["end"]
                )
                final_path = output_dir / f"clip_{number}.mp4"
                if subtitle_count:
                    burn_subtitles(raw_path, subtitle_path, final_path)
                else:
                    shutil.copy2(raw_path, final_path)
            else:
                final_path = create_final_clip(
                    video_path, job_id, number, candidate["start"], candidate["end"],
                    subtitle_path if subtitle_count else None,
                )
            record = dict(candidate)
            record.update({
                "filename": final_path.name,
                "start": candidate["start_time"], "end": candidate["end_time"],
                "duration": round(candidate["end"] - candidate["start"], 3),
            })
            record.pop("start_time", None)
            record.pop("end_time", None)
            completed.append(record)
        except Exception:
            logger.exception("Clip %d failed and will be skipped", number)
        finally:
            if raw_path and raw_path.exists() and not keep_raw:
                raw_path.unlink()

    if not completed:
        raise RuntimeError("All clip exports failed; inspect logs/app.log for FFmpeg details")
    save_metadata(job_id, completed, transcript)
    progress("finalize", "Saving metadata and preparing your downloads…")
    summary = {"job_id": job_id, "input_video": str(video_path), "clips": completed}
    summary_path = OUTPUT_DIR / job_id / "summary.json"
    write_json(summary_path, summary)
    logger.info("Export complete: %s", summary_path.parent)
    return summary_path


def main() -> int:
    args = build_parser().parse_args()
    logger = setup_logging(args.verbose)
    try:
        summary_path = run_pipeline(args.video or args.url, args.max_clips, args.keep_raw)
        print(f"Done. Results: {summary_path.parent}")
        print(f"Summary: {summary_path}")
        return 0
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        logger.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        logger.warning("Cancelled by user")
        return 130
    except Exception as exc:
        logger.error("Unexpected error: %s\n%s", exc, traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
