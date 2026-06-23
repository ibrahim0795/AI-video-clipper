# AI Video Clipper

AI Video Clipper turns a local video or a yt-dlp-supported URL into ready-to-post vertical clips. It transcribes speech locally with faster-whisper, asks Groq to select engaging moments and write social metadata, then uses FFmpeg to compose, caption, and export 1080x1920 MP4 files without cropping the source broadcast.

Only Groq API requests leave your computer. Video downloading, transcription, clipping, subtitles, and export happen locally.

## Tech stack

- **Frontend:** HTML, CSS, and vanilla JavaScript
- **Backend:** Python with Flask
- **AI analysis:** Groq API
- **Transcription:** faster-whisper
- **Video downloading:** yt-dlp
- **Video processing:** FFmpeg and ffprobe
- **Config/secrets:** `.env` loaded with python-dotenv

## What the app does

- Accepts a local video upload or a YouTube/video URL
- Downloads URL videos with yt-dlp
- Transcribes speech locally with faster-whisper
- Sends the transcript to Groq to choose the best football moments
- Creates 9:16 vertical clips while keeping the full original broadcast visible
- Uses blurred background or black bars instead of cutting off the original video
- Burns subtitles into the exported clips
- Generates metadata such as title, hook, caption, description, and hashtags
- Saves results and `summary.json` inside `output/<job_id>/`
- Writes logs to `logs/app.log`

## Requirements

- Python 3.10 or newer
- FFmpeg and ffprobe available on `PATH`
- A Groq API key
- Approximately 2 GB of free disk space for the default Whisper model and temporary media

On Windows, install Python from [python.org](https://www.python.org/downloads/) and enable **Add Python to PATH**. Install FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html), then open a new terminal and confirm:

```powershell
python --version
ffmpeg -version
ffprobe -version
```

The app also detects the standard WinGet `Gyan.FFmpeg` installation automatically. If FFmpeg is installed elsewhere and is not on `PATH`, set `FFMPEG_BIN_DIR` in `.env` to the directory containing `ffmpeg.exe` and `ffprobe.exe`.

## Installation

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and replace the example value:

```dotenv
GROQ_API_KEY=your_real_api_key
```

Never commit `.env`. It is ignored by Git.

## Usage

### Web interface

```powershell
python web_app.py
```

Open `http://127.0.0.1:5000` to upload a video or paste a URL, follow processing status, preview finished clips, and download videos or subtitles.

## Deploy backend on Render

This project includes Render deployment files:

- `Dockerfile` installs Python dependencies, FFmpeg, and Node.js.
- `render.yaml` defines a Docker web service, environment variables, health check, and a persistent output disk.
- `.dockerignore` keeps local videos, outputs, logs, virtual environments, and `.env` out of the deployed image.

### Recommended Render setup

1. Push this repository to GitHub.
2. Open [Render](https://render.com/) and choose **New +** → **Blueprint**.
3. Connect your GitHub repository.
4. Render should detect `render.yaml`.
5. Add the secret environment variable when Render asks:

```env
GROQ_API_KEY=your_real_groq_api_key
```

6. Keep these defaults unless you want to change them:

```env
GROQ_MODEL=llama-3.3-70b-versatile
WHISPER_MODEL=tiny
USE_BLUR_BACKGROUND=true
```

7. Deploy the service.

The deployed app will expose the same web UI. Render will use `/healthz` as the health check endpoint.

### Important Render notes

- Use a paid/starter instance for real processing. Free/small services can be too slow for Whisper and FFmpeg.
- The included persistent disk keeps exported files in `/app/output`.
- Temporary downloads, uploads, transcripts, and logs can still be cleared when the service restarts.
- Large direct uploads may hit platform/proxy limits. For deployment, YouTube/video URLs are usually safer than uploading huge files.
- Video jobs are CPU-heavy and can take several minutes. The app runs one render job at a time to avoid overloading the server.

### Command line

Local file:

```powershell
python main.py --video "C:\Videos\match.mp4"
```

YouTube or another URL supported by yt-dlp:

```powershell
python main.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

Limit output and keep intermediate uncaptioned clips:

```powershell
python main.py --video "sample.mp4" --max-clips 2 --keep-raw --verbose
```

Results are written to `output/<job_id>/`:

```text
clip_1.mp4
clip_1.srt
clip_1_metadata.json
summary.json
```

The full landscape broadcast remains visible over a blurred vertical background, preserving scoreboards and broadcast graphics. Set `USE_BLUR_BACKGROUND=false` to use black bars instead.

Groq prefers event-driven 30-60 second clips and may retain up to 180 seconds when context requires it. If Groq fails completely, the app clearly labels distributed 30-45 second samples as fallback clips instead of presenting them as AI-ranked highlights. Individual FFmpeg clip failures are logged and skipped without losing successful clips.

## Configuration

Defaults live in `app/config.py`. You can select another installed Whisper model or Groq model in `.env`:

```dotenv
WHISPER_MODEL=tiny
GROQ_MODEL=llama-3.3-70b-versatile
```

Whisper uses CUDA automatically when faster-whisper's runtime can see a compatible GPU; otherwise it uses CPU with int8 inference.

## Tests

The test suite uses only Python's standard library and mocks external downloads:

```powershell
python -m unittest discover -s tests -v
```

For an end-to-end run, use a real video at least 30 seconds long with audible speech:

```powershell
python main.py --video "sample.mp4" --max-clips 2
```

Detailed diagnostics are stored in `logs/app.log`.
