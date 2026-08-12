# Text to Audio + Transcript Web App

This project turns your Python scripts into a simple browser app.

## Features

- Convert text to MP3 audio
- Upload audio and generate timestamps transcript
- Browser-based interface with no terminal commands needed for normal use

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
