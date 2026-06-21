# AI Video Clipper

AI Video Clipper turns a local video or a yt-dlp-supported URL into ready-to-post vertical clips. It transcribes speech locally with faster-whisper, asks Google Gemini to select engaging moments and write social metadata, then uses FFmpeg to crop, caption, and export 1080x1920 MP4 files.

Only Gemini requests leave your computer. Video downloading, transcription, clipping, subtitles, and export happen locally.

## Requirements

- Python 3.10 or newer
- FFmpeg and ffprobe available on `PATH`
- A Google Gemini API key
- Approximately 2 GB of free disk space for the default Whisper model and temporary media

On Windows, install Python from [python.org](https://www.python.org/downloads/) and enable **Add Python to PATH**. Install FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html), then open a new terminal and confirm:

```powershell
python --version
ffmpeg -version
ffprobe -version
```

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
GEMINI_API_KEY=your_real_api_key
```

Never commit `.env`. It is ignored by Git.

## Usage

### Web interface

```powershell
python web_app.py
```

Open `http://127.0.0.1:5000` to upload a video or paste a URL, follow processing status, preview finished clips, and download videos or subtitles.

### Command line

Local file:

```powershell
python main.py --video "C:\Videos\match.mp4"
```

YouTube or another URL supported by yt-dlp:

```powershell
python main.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

Limit output and keep intermediate unc captioned clips:

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

The application retries Gemini three times. If the API is unavailable, the key is missing, or the response is invalid, it safely falls back to consecutive 30-second clips. Individual FFmpeg clip failures are logged and skipped without losing successful clips.

## Configuration

Defaults live in `app/config.py`. You can select another installed Whisper model or Gemini model in `.env`:

```dotenv
WHISPER_MODEL=tiny
GEMINI_MODEL=gemini-2.5-flash
```

Whisper uses CUDA automatically when faster-whisper's runtime can see a compatible GPU; otherwise it uses CPU with int8 inference.

## Tests

The test suite uses only Python's standard library and mocks external downloads:

```powershell
python -m unittest discover -s tests -v
```

For an end-to-end run, use a real video containing at least 15 seconds of speech:

```powershell
python main.py --video "sample.mp4" --max-clips 2
```

Detailed diagnostics are stored in `logs/app.log`.
