# Clara Answers — Automation Pipeline

> Converts real-world demo and onboarding call recordings into versioned, production-ready AI voice agent configurations — fully automated, zero cost.

---

## What This Does

Clara Answers is an AI voice agent (built on Retell) that handles inbound calls for service trade businesses — fire protection, HVAC, electrical, sprinkler contractors. Each client has unique business hours, emergency routing rules, and integration constraints.

This pipeline automates the entire setup process:

1. **Demo call comes in** → pipeline extracts what the client said → generates a preliminary Clara agent (v1)
2. **Onboarding call comes in** → pipeline diffs it against v1 → produces a finalized agent (v2) with a full changelog

No manual data entry. No hallucinated config. Just clean, versioned, deployable agent specs.

---

## System Architecture

```
Audio File (.m4a / .mp3)
        │
        ▼
┌───────────────────┐
│   transcribe.py   │  ← Pyannote detects WHO spoke (diarization)
│                   │    Groq Whisper converts speech → text
└────────┬──────────┘
         │
         ▼
  inputs/<account>_demo.txt
         │
         ▼
┌───────────────────┐
│  extract_memo.py  │  ← Groq LLM reads transcript
│                   │    Extracts structured business info
└────────┬──────────┘    (hours, routing, emergency rules, etc.)
         │
         ▼
  outputs/<account>/v1/account_memo.json
         │
         ▼
┌──────────────────────────┐
│  generate_agent_spec.py  │  ← Groq LLM generates Clara's full phone script
│                          │    Business hours flow + after hours flow
└────────┬─────────────────┘    Transfer + fallback protocols
         │
         ▼
  outputs/<account>/v1/agent_spec.json
         │
    [onboarding call arrives]
         │
         ▼
┌───────────────────┐
│   update_memo.py  │  ← Diffs onboarding input against v1
│                   │    Patches only changed fields
└────────┬──────────┘    Produces changelog
         │
         ▼
  outputs/<account>/v2/  +  changelog/<account>_changes.json
         │
         ▼
  Paste agent_spec.json → Retell UI → Clara is live ✅
```

---

## Design Principles

| Principle | How It's Applied |
|---|---|
| **No hallucination** | Missing fields are flagged under `questions_or_unknowns`, never invented |
| **Versioned** | v1 from demo, v2 from onboarding — history always preserved |
| **Idempotent** | Running the pipeline twice produces the same output safely |
| **Modular** | Each script does one job — easy to swap, test, or extend |
| **Zero cost** | Groq free tier (LLM + Whisper), HuggingFace free tier (Pyannote) |
| **Batch capable** | Processes all 10 accounts in one command |

---

## Project Structure

```
clara-pipeline/
├── .env                          ← API keys (never committed)
├── .gitignore
├── README.md
├── setup.py                      ← run this first to verify everything works
│
├── raw_audio/                    ← drop .m4a / .mp3 files here
├── inputs/                       ← transcripts auto-generated here
│
├── outputs/
│   └── accounts/
│       └── <account_id>/
│           ├── v1/
│           │   ├── account_memo.json    ← extracted from demo call
│           │   └── agent_spec.json      ← Clara's phone script (preliminary)
│           └── v2/
│               ├── account_memo.json    ← updated after onboarding
│               └── agent_spec.json      ← final production script
│
├── changelog/
│   └── <account_id>_changes.json       ← what changed from v1 → v2 and why
│
├── scripts/
│   ├── transcribe.py             ← audio → speaker-labeled transcript
│   ├── llm.py                    ← Groq LLM helper (single entry point for all AI calls)
│   ├── extract_memo.py           ← transcript → account memo JSON
│   ├── generate_agent_spec.py    ← memo → Retell agent spec JSON
│   ├── update_memo.py            ← onboarding input → v2 patch + changelog
│   └── run_pipeline.py           ← orchestrates everything end-to-end
│
└── workflows/
    └── n8n_workflow.json         ← n8n automation blueprint (optional)
```

---

## Output Formats

### Account Memo JSON (`account_memo.json`)
Structured business config extracted from the call:
```json
{
  "account_id": "bens-electric",
  "company_name": "Ben's Electric Solutions",
  "business_hours": { "days": "Mon-Fri", "start": "8:00 AM", "end": "5:00 PM", "timezone": "MST" },
  "emergency_definition": ["power outage", "electrical fire", "sparking panel"],
  "emergency_routing_rules": { "primary": "+1-403-555-0101", "fallback": "voicemail dispatch" },
  "after_hours_flow_summary": "Greet, confirm emergency, collect name/number/address, attempt transfer",
  "questions_or_unknowns": ["Transfer timeout not confirmed"],
  "version": "v1"
}
```

### Retell Agent Spec (`agent_spec.json`)
Full Clara phone script + configuration:
```json
{
  "agent_name": "Ben's Electric - Clara Agent",
  "version": "v2",
  "voice_style": "professional, warm, concise",
  "system_prompt": "...",
  "call_transfer_protocol": { "transfer_timeout_seconds": 30, "on_transfer_fail": "..." },
  "fallback_protocol": "...",
  "retell_manual_setup": { "step1": "...", "step2": "..." }
}
```

### Changelog (`_changes.json`)
Clear diff between v1 and v2:
```json
{
  "account_id": "bens-electric",
  "changes": [
    { "field": "business_hours.end", "old": "5:00 PM", "new": "6:00 PM", "reason": "Confirmed in onboarding call" },
    { "field": "emergency_routing_rules.primary", "old": null, "new": "+1-403-555-0101", "reason": "Provided during onboarding" }
  ]
}
```

---

## Setup (One Time)

### 1. Python 3.11 or 3.12 (recommended)
> ⚠️ Python 3.13 has known issues with pyannote + torchvision. Use 3.11 or 3.12.

Download: https://python.org/downloads

### 2. Install packages
```bash
pip install groq pyannote.audio pydub openai-whisper torch==2.2.2 torchvision==0.17.2 torchaudio==2.2.2 python-dotenv
```

### 3. Install ffmpeg

```bash
# Mac:
brew install ffmpeg

# Windows:
winget install ffmpeg

# Linux:
sudo apt install ffmpeg
```

### 4. Get free API keys

**Groq** (free LLM + Whisper):
1. Go to https://console.groq.com → Sign up
2. API Keys → Create Key → Copy

**HuggingFace** (free speaker diarization):
1. Go to https://huggingface.co → Sign up
2. Settings → Tokens → New Token → Copy
3. Accept model terms at: https://hf.co/pyannote/speaker-diarization-3.1

### 5. Fill in `.env`
```bash
export GROQ_API_KEY=gsk_your_key_here
export HUGGINGFACE_TOKEN=hf_your_token_here
```

### 6. Verify setup
```bash
source .env
python scripts/setup.py
```
All green ✅ = ready to go.

---

## Running the Pipeline

### Step 1 — Name and place your audio files
```
raw_audio/
├── bens_electric_demo.m4a
├── bens_electric_onboarding.m4a
├── acme_fire_demo.m4a
├── acme_fire_onboarding.m4a
└── ...
```
> Rule: files must end in `_demo` or `_onboarding`

### Step 2 — Load keys
```bash
source .env
```

### Step 3 — Transcribe all audio
```bash
python scripts/transcribe.py --folder raw_audio
```

### Step 4 — Run full pipeline
```bash
python scripts/run_pipeline.py
```

That's it. All 10 accounts processed automatically.

---

## Retell Setup (Manual — Free Tier)

Retell's API requires a paid plan. The pipeline generates complete agent specs locally. To deploy:

1. Open `outputs/accounts/<account>/v2/agent_spec.json`
2. Copy the `"system_prompt"` value
3. Go to https://retell.ai → **Create New Agent**
4. Paste into **System Prompt**
5. Set voice and language from `"key_variables"`
6. Set transfer number from `"call_transfer_protocol"`
7. **Test → Go Live** ✅

> With production API access, this step becomes fully automated via Retell's `/agents` endpoint.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `GROQ_API_KEY not set` | Run `source .env` first |
| `ffmpeg not found` | Add ffmpeg to PATH — see Setup step 3 |
| `pyannote import error` | Use Python 3.11 or 3.12, not 3.13 |
| `No audio files found` | Files must end in `_demo.m4a` or `_onboarding.m4a` |
| `JSON parse error` | Re-run — rare LLM formatting glitch |
| No v2 generated | Need both `_demo` AND `_onboarding` files for same account name |

---

## Known Limitations

- Retell free tier requires manual agent import (fully documented above)
- Python 3.13 not yet supported by pyannote/torchvision — use 3.11 or 3.12
- First Pyannote run downloads ~300MB model (one-time only)
- Speaker labels are generic (SPEAKER_00, SPEAKER_01) — not auto-named

---

## What Would Improve With Production Access

- **Direct Retell API** — auto-create and update agents programmatically
- **Jobber webhook** — auto-log calls as jobs after dispatch
- **Speaker name detection** — map SPEAKER_00 → "Ben", SPEAKER_01 → "Sales Rep"
- **Dashboard UI** — view all accounts, versions, and changelogs in one place
- **Slack/email notifications** — alert team when a new v2 agent is ready for review

---

## Tech Stack

| Layer | Tool | Cost |
|---|---|---|
| Transcription | Groq Whisper (`whisper-large-v3`) | Free |
| Speaker Detection | Pyannote 3.1 | Free |
| LLM Extraction | Groq (`llama-3.3-70b-versatile`) | Free |
| Storage | Local JSON files / GitHub | Free |
| Orchestration | Python scripts / n8n (optional) | Free |
| Agent Platform | Retell (manual import) | Free |