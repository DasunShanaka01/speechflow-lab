# VoiceForge Transcriber

Convert long text into MP3 audio and generate timestamped transcripts from one or more audio files.

## Features

- Text to speech (MP3) using gTTS
- Handles long paragraphs by splitting and merging audio parts
- Audio transcription with Whisper
- Multi-file transcription support
- Continuous timeline across files (file 2 starts after file 1 ends, etc.)
- Transcript format: `[MM:SS] Transcript line`

## Project Structure

- `app.py` - Flask backend (TTS + transcription APIs)
- `templates/index.html` - Web UI
- `make_audio.py` - Standalone text-to-audio script
- `make_transcript.py` - Standalone transcription script
- `static/output/` - Generated MP3 and transcript files
- `uploads/` - Uploaded audio files for transcription

## Requirements

- Python 3.10+
- FFmpeg available in PATH (or local `tools/ffmpeg`)
- Virtual environment recommended

## Installation

```powershell
cd "D:\Study Materials\YT\Text to audio"
Activate.ps1
pip install -r requirements.txt

## Run

```powershell
cd "D:\Study Materials\YT\Text to audio"
.\.venv\Scripts\Activate.ps1
python app.py
```

Then open:

```text
http://localhost:5000
```

## Notes

- The first transcription may take a few minutes because the Whisper model downloads on first run.
- FFmpeg is required by the audio pipeline. The project includes a local portable FFmpeg under `tools\ffmpeg`.
- This project uses the `whisper` Python package for transcription compatibility with the current environment.
