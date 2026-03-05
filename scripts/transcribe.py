"""
transcribe.py
=============
Transcribes audio files using:
  - Pyannote speaker diarization (WHO spoke)
  - Groq Whisper (WHAT they said)

HOW TO RUN:
  # Single file:
  python scripts/transcribe.py --file raw_audio/bens_electric_demo.m4a

  # Whole folder at once:
  python scripts/transcribe.py --folder raw_audio
"""

import os
import sys
import tempfile
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

from groq import Groq
from pyannote.audio import Pipeline
from pydub import AudioSegment

# ── Keys ──────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
HF_TOKEN     = os.environ.get("HUGGINGFACE_TOKEN", "")
AUDIO_EXTS   = {".m4a", ".mp3", ".mp4", ".wav", ".ogg", ".webm", ".flac"}

BASE_DIR     = Path(__file__).parent.parent
INPUT_DIR    = BASE_DIR / "inputs"


def check_keys():
    missing = []
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY  → get free at https://console.groq.com")
    if not HF_TOKEN:
        missing.append("HUGGINGFACE_TOKEN → get free at https://huggingface.co/settings/tokens")
    if missing:
        print("\n❌ Missing environment variables:\n")
        for m in missing:
            print(f"   {m}")
        sys.exit(1)


def convert_to_wav(input_path: str) -> str:
    """Convert any audio format to 16kHz mono WAV."""
    print(f"  🔄 Converting to WAV...")
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_frame_rate(16000).set_channels(1)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    audio.export(tmp.name, format="wav")
    print(f"  ✅ Converted ({len(audio)/1000:.1f} seconds)")
    return tmp.name, audio


def run_diarization(wav_path: str) -> object:
    """Run Pyannote speaker diarization."""
    print(f"  🔍 Detecting speakers with Pyannote...")
    print(f"  ⏳ First run downloads ~300MB model (one-time only)...")

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=HF_TOKEN
    )

    diarization = pipeline(wav_path)
    print(f"  ✅ Diarization complete")
    return diarization


def transcribe_segments(diarization, audio: AudioSegment) -> list:
    """
    For each speaker segment:
    - Cut that chunk of audio
    - Send to Groq Whisper
    - Collect text with speaker label
    """
    print(f"  📝 Transcribing each segment with Groq Whisper...")

    client = Groq(api_key=GROQ_API_KEY)
    turns  = []
    total  = sum(1 for _ in diarization.itertracks(yield_label=True))
    count  = 0

    for segment, track, speaker in diarization.itertracks(yield_label=True):
        count += 1

        start_ms = int(segment.start * 1000)
        end_ms   = int(segment.end   * 1000)
        chunk    = audio[start_ms:end_ms]

        # Skip very short chunks — usually noise
        if len(chunk) < 500:
            continue

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            chunk.export(tmp.name, format="wav")
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                transcription = client.audio.transcriptions.create(
                    file=f,
                    model="whisper-large-v3"
                )
            text = transcription.text.strip()
        except Exception as e:
            text = ""
            print(f"  ⚠️  Segment {count} failed: {e}")
        finally:
            os.unlink(tmp_path)

        if text:
            turns.append({
                "speaker": speaker,
                "start":   round(segment.start, 2),
                "end":     round(segment.end,   2),
                "text":    text
            })

        if count % 10 == 0:
            print(f"  ... {count}/{total} segments done")

    print(f"  ✅ Transcribed {len(turns)} segments")
    return turns


def format_transcript(turns: list) -> str:
    """Format turns into readable transcript."""
    lines = []
    for t in turns:
        start   = f"{t['start']:.2f}"
        end     = f"{t['end']:.2f}"
        speaker = t["speaker"]
        text    = t["text"]
        lines.append(f"[{start} - {end}] {speaker}: {text}")
    return "\n".join(lines)


def parse_zoom_chat(chat_path: str) -> str:
    """Append Zoom chat as extra context if provided."""
    if not chat_path or not os.path.exists(chat_path):
        return ""
    with open(chat_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    entries = []
    for line in lines:
        line = line.strip()
        if "From " in line and " : " in line:
            parts  = line.split("From ", 1)[1]
            sender, msg = parts.split(" : ", 1)
            entries.append(f"  {sender.strip()}: {msg.strip()}")
    if not entries:
        return ""
    return (
        "\n\n--- ZOOM CHAT (extra info shared during call) ---\n"
        + "\n".join(entries)
        + "\n--- END ZOOM CHAT ---"
    )


def process_file(audio_path: str, account_id: str, call_type: str,
                 chat_path: str = None) -> str:
    """Full pipeline for one audio file."""
    check_keys()

    print(f"\n{'='*55}")
    print(f"🎙️  {Path(audio_path).name}")
    print(f"    Account: {account_id} | Type: {call_type}")
    print(f"{'='*55}")

    # Step 1: Convert to WAV
    wav_path, audio = convert_to_wav(audio_path)

    try:
        # Step 2: Speaker diarization
        diarization = run_diarization(wav_path)

        # Step 3: Transcribe each segment
        turns = transcribe_segments(diarization, audio)
    finally:
        os.unlink(wav_path)  # clean up temp wav

    # Step 4: Format transcript
    transcript = format_transcript(turns)

    # Step 5: Append Zoom chat if provided
    if chat_path:
        transcript += parse_zoom_chat(chat_path)

    # Step 6: Save to inputs/
    INPUT_DIR.mkdir(exist_ok=True)
    out_path = INPUT_DIR / f"{account_id}_{call_type}.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(transcript)

    print(f"\n  💾 Saved: {out_path}")
    print(f"\n  📄 Preview (first 5 lines):")
    for line in transcript.split("\n")[:5]:
        print(f"     {line}")

    return str(out_path)


def process_folder(folder: str):
    """Batch process all audio files in a folder."""
    check_keys()

    audio_files = sorted([
        f for f in Path(folder).iterdir()
        if f.suffix.lower() in AUDIO_EXTS
    ])

    if not audio_files:
        print(f"⚠️  No audio files found in: {folder}")
        print(f"   Supported formats: {', '.join(AUDIO_EXTS)}")
        print(f"   File names must end in _demo or _onboarding")
        return

    print(f"\n📁 Found {len(audio_files)} audio file(s) to process")
    results = []

    for audio_file in audio_files:
        stem = audio_file.stem

        if "_demo" in stem:
            account_id = stem.replace("_demo", "")
            call_type  = "demo"
        elif "_onboarding" in stem:
            account_id = stem.replace("_onboarding", "")
            call_type  = "onboarding"
        else:
            account_id = stem
            call_type  = "demo"
            print(f"  ⚠️  Can't detect type from '{stem}', treating as demo")

        # Look for matching Zoom chat file
        chat_file = Path(folder) / f"{stem}_chat.txt"
        chat_path = str(chat_file) if chat_file.exists() else None

        try:
            out = process_file(str(audio_file), account_id, call_type,
                               chat_path=chat_path)
            results.append({"file": audio_file.name, "status": "✅", "out": out})
        except Exception as e:
            results.append({"file": audio_file.name, "status": "❌", "error": str(e)})
            print(f"\n  ❌ Failed: {e}")

    print(f"\n{'='*55}")
    print(f"BATCH SUMMARY")
    print(f"{'='*55}")
    for r in results:
        print(f"  {r['status']} {r['file']}")


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcribe audio with speaker labels")
    parser.add_argument("--file",    help="Single audio file path")
    parser.add_argument("--account", help="Account ID e.g. bens_electric")
    parser.add_argument("--type",    help="demo or onboarding", default="demo")
    parser.add_argument("--chat",    help="Optional Zoom chat .txt file")
    parser.add_argument("--folder",  help="Folder of audio files (batch mode)")
    args = parser.parse_args()

    if args.folder:
        process_folder(args.folder)
    elif args.file:
        if not args.account:
            print("❌ --account required when using --file. Example:")
            print("   python scripts/transcribe.py --file raw_audio/bens_electric_demo.m4a --account bens_electric --type demo")
            sys.exit(1)
        process_file(args.file, args.account, args.type, chat_path=args.chat)
    else:
        parser.print_help()