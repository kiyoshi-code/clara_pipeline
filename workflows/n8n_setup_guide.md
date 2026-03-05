# n8n Workflow — Setup Guide

This guide explains how to import and run the Clara Answers automation pipeline in n8n.

---

## What This Workflow Does

```
New audio file dropped in raw_audio/
        │
        ▼
Parse filename → detect account_id + call_type
        │
        ├─ demo file ──────────────────────────────────────────────────────────┐
        │                                                                       │
        ▼                                                                       │
Transcribe (Groq Whisper)                                                      │
        │                                                                       │
        ▼                                                                       │
Extract Account Memo (Groq LLM) → v1/account_memo.json                        │
        │                                                                       │
        ▼                                                                       │
Generate Agent Spec (Groq LLM) → v1/agent_spec.json                           │
        │                                                                       │
        ▼                                                                       │
Create task in tracker                                                          │
                                                                               │
        ├─ onboarding file ◄────────────────────────────────────────────────────┘
        │
        ▼
Transcribe (Groq Whisper)
        │
        ▼
Check v1 memo exists (safety gate)
        │
        ▼
Update Memo → v2/account_memo.json + changelog/
        │
        ▼
Generate Agent Spec → v2/agent_spec.json
        │
        ▼
Notify: agent spec ready for Retell import
```

---

## Option A — Run Without n8n (Recommended for Free Tier)

You do not need n8n to run this pipeline. The Python scripts handle everything:

```bash
# Load keys
source .env

# Transcribe all audio
python scripts/transcribe.py --folder raw_audio

# Run full pipeline (Pipeline A + B for all accounts)
python scripts/run_pipeline.py
```

The `n8n_workflow.json` file is provided as an architecture blueprint showing how the pipeline would be wired as a production automation.

---

## Option B — Run With n8n Locally (Docker)

### Step 1 — Install Docker
https://www.docker.com/products/docker-desktop

### Step 2 — Start n8n
```bash
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  -v $(pwd):/home/node/clara-pipeline \
  n8nio/n8n
```

### Step 3 — Open n8n
Go to: **http://localhost:5678**

### Step 4 — Import the workflow
1. Click **Workflows** in the left sidebar
2. Click **Import from File**
3. Select `workflows/n8n_workflow.json`
4. Click **Import**

### Step 5 — Set environment variables in n8n
1. Go to **Settings → Environment Variables**
2. Add:
   - `GROQ_API_KEY` = your Groq key
   - `HUGGINGFACE_TOKEN` = your HuggingFace token

### Step 6 — Activate the workflow
1. Open the imported workflow
2. Toggle **Active** in the top right
3. Drop an audio file into `raw_audio/` — the pipeline triggers automatically

---

## Node Reference

| Node | What It Does |
|---|---|
| Watch raw_audio Folder | Triggers when a new audio file is added |
| Parse Filename | Extracts account_id and call_type from filename |
| Route: Demo or Onboarding? | Sends to Pipeline A or Pipeline B |
| Transcribe Audio | Runs transcribe.py via Groq Whisper + Pyannote |
| Extract Account Memo | Runs extract_memo.py via Groq LLM |
| Generate Agent Spec v1 | Runs generate_agent_spec.py via Groq LLM |
| Save v1 Outputs | Logs completion, ready for Supabase/Airtable in production |
| Create Task in Tracker | Mock task creation (Asana/Notion in production) |
| Check v1 Memo Exists | Safety gate before running Pipeline B |
| Update Memo to v2 | Runs update_memo.py — diffs and patches v1 → v2 |
| Generate Agent Spec v2 | Regenerates full agent spec from v2 memo |
| Save v2 Outputs + Changelog | Logs completion with changelog path |
| Notify: Agent Ready | Mock Retell notification (API auto-create in production) |
| Error Handler | Catches failures, logs cleanly |

---

## Mocked Nodes (Free Tier Limitations)

These nodes are implemented as function nodes with console logs instead of live API calls:

| Node | Why Mocked | Production Replacement |
|---|---|---|
| Create Task in Tracker | Asana API requires paid plan for some features | n8n Asana node with API key |
| Notify: Agent Ready for Retell | Retell API requires paid plan | n8n HTTP Request → POST /agents |
| Save v1/v2 Outputs to Storage | Local files used instead of DB | n8n Supabase or Airtable node |

---

## Batch Processing All 10 Files

To process all 10 accounts at once without n8n:

```bash
source .env
python scripts/run_pipeline.py
```

Or drop all 10 audio files into `raw_audio/` at once — if n8n is active, it will process each file as it appears.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| n8n can't find Python | Set full path in Execute Command nodes: `/usr/bin/python3` |
| Workflow doesn't trigger | Make sure the workflow is toggled **Active** |
| `v1 memo not found` error | Run demo file before onboarding file for the same account |
| Port 5678 already in use | Change port: `-p 5679:5678` and open `localhost:5679` |