"""
generate_agent_spec.py
======================
WHAT THIS DOES:
  Takes the account memo JSON and generates a complete Retell Agent Spec —
  the full set of instructions for how Clara should behave on the phone
  for THIS specific client.

  Think of it as writing a personalized training manual for a receptionist,
  but based entirely on what the client told us in their calls.

HOW TO RUN:
  python3 generate_agent_spec.py ../outputs/accounts/bens-electric/v1/account_memo.json
"""

import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from llm import call_llm, parse_json


SYSTEM_PROMPT = """
You are an AI voice agent configurator for Clara Answers.

Given an account memo JSON, generate a complete Retell Agent Spec JSON.

The spec must contain a system_prompt that covers TWO flows:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BUSINESS HOURS FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. GREETING — warm, professional, state company name
2. ASK PURPOSE — why are they calling?
3. COLLECT NAME + CALLBACK NUMBER — confirm number by reading it back
4. ROUTE / TRANSFER — attempt live transfer to appropriate person
5. IF TRANSFER FAILS — apologize, take message, assure callback
6. WRAP UP — "Is there anything else I can help you with?"
7. CLOSE — warm goodbye

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AFTER HOURS FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. GREETING — note office is closed
2. ASK PURPOSE
3. CONFIRM EMERGENCY — "Is this an emergency?"
4a. IF EMERGENCY:
    - Collect name, number, address immediately
    - Attempt transfer to on-call person
    - If transfer fails: apologize, assure urgent callback
4b. IF NOT EMERGENCY:
    - Collect details
    - Confirm follow-up next business day
5. WRAP UP — "Is there anything else?"
6. CLOSE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRICT RULES FOR THE PROMPT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Never ask more than 2 questions at a time
- Never mention "function calls", "tools", or any backend tech to caller
- Always confirm phone numbers by reading them back
- Use the EXACT hours, services, routing rules from the memo
- If a value is null in the memo, handle it gracefully (don't say "null")
- Sound natural and human at all times

Return ONLY a valid JSON object. No explanation. No markdown fences.

{
  "agent_name": "<Company Name> - Clara Agent",
  "version": "<v1 or v2>",
  "voice_style": "professional, warm, concise",
  "language": "en-US",
  "key_variables": {
    "company_name": "",
    "timezone": "",
    "business_hours": "",
    "office_address": "",
    "primary_transfer_number": "",
    "fallback_transfer_number": "",
    "emergency_triggers": "",
    "services_offered": ""
  },
  "system_prompt": "<full detailed prompt here covering both flows>",
  "call_transfer_protocol": {
    "how_to_transfer": "<step by step instructions>",
    "transfer_timeout_seconds": null,
    "on_transfer_fail": "<exact words to say>"
  },
  "fallback_protocol": "<what Clara does if ALL transfer attempts fail>",
  "tool_invocation_placeholders": [
    "transfer_call",
    "send_summary_email",
    "log_call_to_crm",
    "send_sms_notification"
  ],
  "retell_manual_setup": {
    "step1": "Go to retell.ai and create a new Agent",
    "step2": "Paste system_prompt into the System Prompt field",
    "step3": "Set voice to: en-US, professional female or male",
    "step4": "Configure call transfer using call_transfer_protocol",
    "step5": "Test by calling the Retell-provided number",
    "step6": "Go live once testing passes"
  },
  "notes": "<any config warnings or things to confirm at onboarding>"
}
"""


def load_memo(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_spec(spec: dict, account_id: str, version: str, output_dir: str) -> str:
    folder = os.path.join(output_dir, account_id, version)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "agent_spec.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)
    return path


def run(memo_path: str, output_dir: str = "../outputs/accounts") -> dict:
    print(f"\n📋 Loading memo: {Path(memo_path).name}")
    memo       = load_memo(memo_path)
    account_id = memo["account_id"]
    version    = memo["version"]

    print("🤖 Generating agent prompt with Groq LLM...")
    raw = call_llm(
        system_prompt=SYSTEM_PROMPT,
        user_message=f"Generate the Retell Agent Spec for this account memo:\n\n{json.dumps(memo, indent=2)}",
        max_tokens=3000
    )

    print("🔍 Parsing response...")
    spec = parse_json(raw)
    spec["version"]      = version
    spec["generated_at"] = datetime.now(timezone.utc).isoformat()

    path = save_spec(spec, account_id, version, output_dir)
    print(f"✅ Agent spec saved: {path}")
    print(f"\n🤖 Agent: {spec.get('agent_name')}")

    return spec


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 generate_agent_spec.py <account_memo.json>")
        sys.exit(1)
    run(sys.argv[1])
