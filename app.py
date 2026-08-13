from __future__ import annotations

import os
import json
import re
import subprocess
from pathlib import Path
import uuid

from flask import Flask, jsonify, render_template, request
from gtts import gTTS
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
FFMPEG_DIR = BASE_DIR / "tools" / "ffmpeg"
if FFMPEG_DIR.exists():
    os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")

import whisper

app = Flask(__name__)

OUTPUT_DIR = BASE_DIR / "static" / "output"
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

model = whisper.load_model("base")

VOICE_STYLES = {
    "neutral": {"lang": "en", "tld": "com", "slow": False},
    "us": {"lang": "en", "tld": "us", "slow": False},
    "uk": {"lang": "en", "tld": "co.uk", "slow": False},
    "au": {"lang": "en", "tld": "com.au", "slow": False},
    "india": {"lang": "en", "tld": "co.in", "slow": False},
    "female": {"lang": "en", "tld": "com.au", "slow": False},
    "male": {"lang": "en", "tld": "co.in", "slow": False},
    "story": {"lang": "en", "tld": "com", "slow": True},
}


def format_time_label(seconds: float) -> str:
    total_seconds = max(0, int(float(seconds)))
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def get_audio_duration_seconds(file_path: Path) -> float:
    try:
        output = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(file_path),
            ],
            text=True,
        )
        data = json.loads(output)
        return float(data.get("format", {}).get("duration", 0.0))
    except Exception:
        return 0.0


def split_text_for_tts(text: str, max_chars: int = 160):
    cleaned = (text or "").replace("\r\n", "\n").strip()
    if not cleaned:
        return []

    chunks = []
    current = ""

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", cleaned) if p.strip()]

    for paragraph in paragraphs:
        sentences = re.split(r"(?<=[.!?])\s+", paragraph)
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_parts = sentence.split()
            if len(sentence) > max_chars and sentence_parts:
                for part in sentence_parts:
                    candidate = f"{current} {part}".strip() if current else part
                    if len(candidate) <= max_chars:
                        current = candidate
                    else:
                        if current:
                            chunks.append(current)
                        current = part
                continue

            candidate = f"{current} {sentence}".strip() if current else sentence
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = sentence

    if current:
        chunks.append(current)

    return [chunk.strip() for chunk in chunks if chunk.strip()]


def save_tts_chunk(
    text: str,
    lang: str,
    output_path: Path,
    retries: int = 2,
    tld: str = "com",
    slow: bool = False,
):
    last_error = None
    for _ in range(retries + 1):
        try:
            gTTS(text=text, lang=lang, tld=tld, slow=slow).save(str(output_path))
            return
        except Exception as error:  # gTTS raises gTTSError and request-related failures here
            last_error = error
    raise last_error


def run_ffmpeg_concat(concat_list_path: Path, output_path: Path):
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list_path),
            "-c",
            "copy",
            str(output_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def build_mp3_from_text(
    text: str,
    lang: str,
    output_path: Path,
    tld: str = "com",
    slow: bool = False,
):
    chunks = split_text_for_tts(text)

    if len(chunks) == 1:
        save_tts_chunk(chunks[0], lang, output_path, tld=tld, slow=slow)
        return

    temp_dir = OUTPUT_DIR / f"tts_{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        part_paths = []
        for index, chunk in enumerate(chunks):
            part_path = temp_dir / f"part_{index}.mp3"
            save_tts_chunk(chunk, lang, part_path, tld=tld, slow=slow)
            part_paths.append(part_path)

        concat_list = temp_dir / "concat.txt"
        with concat_list.open("w", encoding="utf-8") as file:
            for part_path in part_paths:
                file.write(f"file '{part_path.as_posix()}'\n")

        run_ffmpeg_concat(concat_list, output_path)
    finally:
        if temp_dir.exists():
            for file_path in sorted(temp_dir.iterdir(), reverse=True):
                if file_path.is_file():
                    file_path.unlink()
            temp_dir.rmdir()


def parse_speaker_styles(style_text: str):
    style_map = {}
    for line in (style_text or "").splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        speaker, style = line.split("=", 1)
        speaker = speaker.strip()
        style = style.strip().lower()
        if speaker:
            style_map[speaker] = style
    return style_map


def parse_speaker_script(script_text: str):
    turns = []
    for raw_line in (script_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" in line:
            speaker, text = line.split(":", 1)
            speaker = speaker.strip()
            text = text.strip()
            if speaker and text:
                turns.append((speaker, text))
        else:
            turns.append(("Narrator", line))
    return turns


def build_mp3_from_speaker_turns(turns, speaker_styles: dict, output_path: Path):
    temp_dir = OUTPUT_DIR / f"speaker_tts_{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        part_paths = []
        part_index = 0
        for speaker, turn_text in turns:
            style_name = speaker_styles.get(speaker, "neutral")
            style = VOICE_STYLES.get(style_name, VOICE_STYLES["neutral"])
            chunks = split_text_for_tts(turn_text)

            for chunk in chunks:
                part_path = temp_dir / f"part_{part_index}.mp3"
                save_tts_chunk(
                    chunk,
                    style["lang"],
                    part_path,
                    tld=style["tld"],
                    slow=style["slow"],
                )
                part_paths.append(part_path)
                part_index += 1

        if not part_paths:
            raise ValueError("No speaker lines found to generate audio.")

        concat_list = temp_dir / "concat.txt"
        with concat_list.open("w", encoding="utf-8") as file:
            for part_path in part_paths:
                file.write(f"file '{part_path.as_posix()}'\n")

        run_ffmpeg_concat(concat_list, output_path)
    finally:
        if temp_dir.exists():
            for file_path in sorted(temp_dir.iterdir(), reverse=True):
                if file_path.is_file():
                    file_path.unlink()
            temp_dir.rmdir()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/tts", methods=["POST"])
def generate_audio():
    text = (request.form.get("text") or "").strip()
    lang = request.form.get("lang", "en")
    voice_style = (request.form.get("voice_style") or "neutral").strip().lower()

    if not text:
        return jsonify({"error": "Please enter some text to convert to speech."}), 400

    file_name = f"{uuid.uuid4().hex}.mp3"
    output_path = OUTPUT_DIR / file_name

    style = VOICE_STYLES.get(voice_style, VOICE_STYLES["neutral"])

    build_mp3_from_text(
        text,
        lang,
        output_path,
        tld=style["tld"],
        slow=style["slow"],
    )

    return jsonify({
        "audio_url": f"/static/output/{file_name}",
        "message": "Audio created successfully."
    })


@app.route("/api/tts_speakers", methods=["POST"])
def generate_speaker_audio():
    script = (request.form.get("script") or "").strip()
    style_text = request.form.get("styles") or ""

    if not script:
        return jsonify({"error": "Please provide speaker script text."}), 400

    turns = parse_speaker_script(script)
    if not turns:
        return jsonify({"error": "No valid speaker lines found. Use 'Name: text' format."}), 400

    speaker_styles = parse_speaker_styles(style_text)

    file_name = f"{uuid.uuid4().hex}.mp3"
    output_path = OUTPUT_DIR / file_name

    build_mp3_from_speaker_turns(turns, speaker_styles, output_path)

    return jsonify({
        "audio_url": f"/static/output/{file_name}",
        "message": "Multi-speaker audio created successfully.",
    })


@app.route("/api/transcribe", methods=["POST"])
def transcribe_audio():
    uploaded_files = [
        file for file in request.files.getlist("audio")
        if file and file.filename and file.filename.strip()
    ]
    if not uploaded_files:
        return jsonify({"error": "Please upload one or more MP3/WAV audio files."}), 400

    transcript_lines = []
    combined_segments = []
    running_offset = 0.0

    for uploaded_file in uploaded_files:
        safe_name = secure_filename(uploaded_file.filename)
        file_name = f"{uuid.uuid4().hex}_{safe_name}"
        file_path = UPLOAD_DIR / file_name
        uploaded_file.save(file_path)

        result = model.transcribe(str(file_path))
        segments = result.get("segments", [])

        transcript_lines.append(f"--- {safe_name} ---")
        for segment in segments:
            local_start = float(segment.get("start", 0.0))
            local_end = float(segment.get("end", 0.0))
            global_start = round(local_start + running_offset, 1)
            global_end = round(local_end + running_offset, 1)
            text = (segment.get("text") or "").strip()

            combined_segments.append({
                "source_file": safe_name,
                "start": global_start,
                "end": global_end,
                "text": text,
            })

            if text:
                start_label = format_time_label(global_start)
                transcript_lines.append(f"[{start_label}] {text}")

        duration = get_audio_duration_seconds(file_path)
        if duration <= 0 and segments:
            duration = max(float(segment.get("end", 0.0)) for segment in segments)
        running_offset += duration
        transcript_lines.append("")

    transcript_text = "\n".join(line for line in transcript_lines).strip()
    transcript_path = OUTPUT_DIR / f"{uuid.uuid4().hex}_transcript.txt"
    transcript_path.write_text(transcript_text, encoding="utf-8")

    return jsonify({
        "transcript": transcript_text,
        "segments": combined_segments,
        "total_duration_seconds": round(running_offset, 1),
        "download_url": f"/static/output/{transcript_path.name}"
    })


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
