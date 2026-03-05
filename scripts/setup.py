"""
setup.py
========
Run this FIRST before anything else.
Checks that all tools, packages, and API keys are correctly set up.

USAGE:
  python setup.py
"""

import os
import sys
import subprocess
from dotenv import load_dotenv

# Load .env file automatically (works on Windows too)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))


def check(label, ok, fix=None):
    status = "✅" if ok else "❌"
    print(f"  {status}  {label}")
    if not ok and fix:
        print(f"       → {fix}")
    return ok


def main():
    print("\n" + "="*55)
    print("  Clara Pipeline — Setup Check")
    print("="*55)

    all_ok = True

    # ── Python version ────────────────────────────────────────
    print("\n[1] Python")
    v = sys.version_info
    ok = v.major == 3 and v.minor >= 9
    all_ok &= check(f"Python {v.major}.{v.minor}", ok,
                    "Install Python 3.9+ from https://python.org/downloads")

    # ── Required packages ─────────────────────────────────────
    print("\n[2] Python Packages")
    packages = {
        "groq":         "pip install groq",
        "pyannote":     "pip install pyannote.audio",
        "pydub":        "pip install pydub",
        "whisper":      "pip install openai-whisper",
        "torch":        "pip install torch torchaudio",
        "dotenv":       "pip install python-dotenv",
    }
    for pkg, install_cmd in packages.items():
        try:
            __import__(pkg.split(".")[0])
            check(pkg, True)
        except ImportError:
            all_ok &= check(pkg, False, install_cmd)

    # ── ffmpeg ────────────────────────────────────────────────
    print("\n[3] ffmpeg")
    result = subprocess.run(["ffmpeg", "-version"], capture_output=True)
    ok = result.returncode == 0
    all_ok &= check("ffmpeg installed", ok,
                    "Mac: brew install ffmpeg | Windows: choco install ffmpeg")

    # ── API Keys ──────────────────────────────────────────────
    print("\n[4] API Keys")
    groq_key = os.environ.get("GROQ_API_KEY", "")
    hf_token = os.environ.get("HUGGINGFACE_TOKEN", "")

    ok1 = bool(groq_key)
    ok2 = bool(hf_token)

    all_ok &= check(
        f"GROQ_API_KEY {'(set)' if ok1 else '(missing)'}",
        ok1, "Get free at https://console.groq.com → API Keys"
    )
    all_ok &= check(
        f"HUGGINGFACE_TOKEN {'(set)' if ok2 else '(missing)'}",
        ok2, "Get free at https://huggingface.co/settings/tokens"
    )
    if ok2:
        check("Pyannote terms accepted?", True,
              "If not: visit https://hf.co/pyannote/speaker-diarization-3.1 → Agree")

    # ── Folders ───────────────────────────────────────────────
    print("\n[5] Project Folders")
    base = os.path.join(os.path.dirname(__file__), '..')
    for folder in ["raw_audio", "inputs", "outputs/accounts", "changelog"]:
        full_path = os.path.join(base, folder)
        os.makedirs(full_path, exist_ok=True)
        check(f"{folder}/", True)

    # ── LLM test ──────────────────────────────────────────────
    print("\n[6] LLM Connection Test")
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=5,
                messages=[{"role": "user", "content": "Say OK"}]
            )
            reply = resp.choices[0].message.content
            check(f"Groq LLM responded: '{reply.strip()}'", True)
        except Exception as e:
            all_ok &= check(f"Groq LLM test failed: {e}", False,
                            "Check your GROQ_API_KEY is correct")
    else:
        check("Groq LLM test (skipped — no key set)", False,
              "Set GROQ_API_KEY first, then re-run setup.py")

    # ── Summary ───────────────────────────────────────────────
    print("\n" + "="*55)
    if all_ok:
        print("  🎉  Everything looks good! You're ready to run.")
        print("\n  Next steps:")
        print("  1. Drop audio files in raw_audio/")
        print("     Name them: bens_electric_demo.m4a")
        print("  2. Transcribe:  python scripts/transcribe.py --folder raw_audio")
        print("  3. Run pipeline: python scripts/run_pipeline.py")
    else:
        print("  ⚠️   Some issues found above. Fix them and re-run setup.py")
    print("="*55 + "\n")


if __name__ == "__main__":
    main()