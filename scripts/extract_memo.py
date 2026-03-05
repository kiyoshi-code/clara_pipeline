"""
extract_memo.py
===============
WHAT THIS DOES:
  Reads a transcript and extracts all business information into a
  structured JSON "account memo" — like filling out a form automatically.

  The AI is given very strict instructions:
  - Only extract what is EXPLICITLY said
  - Never guess or invent missing info
  - Flag anything unclear in questions_or_unknowns

HOW TO RUN:
  python3 extract_memo.py ../inputs/bens_electric_demo.txt
"""

import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from llm import call_llm, parse_json


SYSTEM_PROMPT = """
You are a data extraction specialist for Clara Answers, an AI voice agent
platform for trade businesses (electrical, HVAC, fire protection, plumbing etc.)

Your job: read a call transcript and extract structured business information
into a JSON account memo.

STRICT RULES:
1. Only extract what is EXPLICITLY stated in the transcript.
2. NEVER invent, assume, or guess missing information.
3. If a field cannot be determined → use null.
4. If something is vague or unclear → add it to questions_or_unknowns.
5. Ignore anything said by a Clara AI demo agent (it's not real business data).
6. Focus only on what the CUSTOMER says about THEIR OWN business.
7. Speaker labels like SPEAKER_00 / SPEAKER_01 in the transcript are fine —
   figure out from context which speaker is the client.

Return ONLY a valid JSON object. No explanation. No markdown fences.

{
  "account_id": "<slug: company name lowercase with hyphens, e.g. bens-electric>",
  "version": "v1",
  "source": "demo_call",
  "created_at": null,
  "updated_at": null,

  "company_name": "<full company name or null>",
  "primary_contact_name": "<name or null>",
  "primary_contact_email": "<email or null>",
  "primary_contact_phone": "<phone or null>",
  "office_address": "<address or null>",
  "service_locations": ["<city/region if mentioned>"],
  "industry": "<e.g. Electrical Contractor, HVAC, Fire Protection>",
  "crm_system": "<e.g. Jobber, ServiceTitan, or null>",

  "business_hours": {
    "timezone": "<timezone or null>",
    "days": ["<e.g. Monday-Friday or null>"],
    "start": "<e.g. 8:00 AM or null>",
    "end": "<e.g. 5:00 PM or null>"
  },

  "services_supported": ["<every service explicitly mentioned>"],
  "services_not_supported": ["<services explicitly said they do NOT offer>"],

  "call_volume_estimate": "<rough weekly/monthly call volume if mentioned>",

  "team_size": "<number of employees/technicians if mentioned>",

  "emergency_definition": ["<what counts as an emergency for this client>"],

  "emergency_routing_rules": {
    "primary_contact": "<who gets emergency calls first>",
    "fallback_1": "<first fallback person/number or null>",
    "fallback_2": "<second fallback or null>",
    "after_hours_emergency": "<what happens for emergencies after hours>"
  },

  "non_emergency_routing_rules": {
    "during_hours": "<what happens to normal calls during business hours>",
    "after_hours": "<what happens to non-emergency calls after hours>"
  },

  "call_transfer_rules": {
    "transfer_timeout_seconds": null,
    "retries": null,
    "on_transfer_fail": "<what to tell caller if transfer fails>"
  },

  "vip_numbers": ["<phone numbers or contacts that should bypass AI screening>"],

  "integration_constraints": ["<any system rules e.g. never create sprinkler jobs in ServiceTrade>"],

  "after_hours_flow_summary": "<1-2 sentence summary of after hours call handling>",
  "office_hours_flow_summary": "<1-2 sentence summary of office hours call handling>",

  "questions_or_unknowns": ["<anything unclear or missing that onboarding must confirm>"],

  "notes": "<any other useful observations about this client>"
}
"""


def load_transcript(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def save_memo(memo: dict, output_dir: str) -> str:
    account_id = memo["account_id"]
    version    = memo["version"]
    folder     = os.path.join(output_dir, account_id, version)
    os.makedirs(folder, exist_ok=True)

    path = os.path.join(folder, "account_memo.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(memo, f, indent=2)
    return path


def run(transcript_path: str, output_dir: str = "../outputs/accounts") -> dict:
    print(f"\n📄 Reading transcript: {Path(transcript_path).name}")
    transcript = load_transcript(transcript_path)

    print("🤖 Extracting business info with Groq LLM...")
    raw = call_llm(
        system_prompt=SYSTEM_PROMPT,
        user_message=f"Extract the account memo from this transcript:\n\n{transcript}"
    )

    print("🔍 Parsing response...")
    memo = parse_json(raw)

    now = datetime.now(timezone.utc).isoformat()
    memo["created_at"] = now
    memo["updated_at"] = now

    path = save_memo(memo, output_dir)
    print(f"✅ Memo saved: {path}")

    # Show a quick summary
    print(f"\n📋 Extracted:")
    print(f"   Company:  {memo.get('company_name')}")
    print(f"   Contact:  {memo.get('primary_contact_name')}")
    print(f"   Industry: {memo.get('industry')}")
    print(f"   Services: {len(memo.get('services_supported', []))} services found")
    print(f"   Unknowns: {len(memo.get('questions_or_unknowns', []))} items flagged")

    return memo


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 extract_memo.py <transcript.txt>")
        sys.exit(1)
    run(sys.argv[1])
