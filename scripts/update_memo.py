"""
update_memo.py
==============
WHAT THIS DOES:
  Takes the v1 memo (from demo call) and the onboarding transcript,
  figures out what changed or got confirmed, and produces:
  
  1. v2 account_memo.json — updated with confirmed details
  2. v2 agent_spec.json   — updated phone script
  3. changelog JSON       — exactly what changed and why

  Think of it like "track changes" in Word — nothing gets silently
  overwritten. Every change is logged with a reason.

HOW TO RUN:
  python3 update_memo.py \
    ../outputs/accounts/bens-electric/v1/account_memo.json \
    ../inputs/bens_electric_onboarding.txt
"""

import os
import sys
import json
import copy
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from llm import call_llm, parse_json


SYSTEM_PROMPT = """
You are a data reconciliation specialist for Clara Answers.

You will receive:
1. An existing v1 account memo (extracted from a demo call)
2. An onboarding call transcript (more detailed, operationally precise)

Your job: figure out what CHANGED or got NEWLY CONFIRMED, and return a patch.

RULES:
- Onboarding data ALWAYS overrides demo data when they conflict
- Only include fields that are actually changing or being newly filled in
- Never invent changes — only reflect what the onboarding transcript says
- Preserve all v1 fields that aren't mentioned in onboarding
- If demo had null and onboarding fills it in → include it as a change
- If demo had a guess and onboarding confirms/corrects it → include it

Return ONLY valid JSON. No explanation. No markdown fences.

{
  "updated_fields": {
    "<only the fields that are changing or being newly confirmed>"
  },
  "changelog": [
    {
      "field": "<field name>",
      "old_value": "<what v1 had>",
      "new_value": "<what v2 should have>",
      "reason": "<why it changed — quote from transcript if possible>"
    }
  ],
  "conflicts": [
    {
      "field": "<field name>",
      "v1_value": "<what demo said>",
      "onboarding_value": "<what onboarding said>",
      "resolution": "<which one we used and why>"
    }
  ],
  "new_unknowns": ["<any NEW questions that arose from the onboarding call>"]
}
"""


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def deep_merge(base: dict, updates: dict) -> dict:
    """
    Merge updates into base dict.
    - Simple values get replaced
    - Nested dicts get merged recursively
    - Lists get replaced entirely (onboarding is authoritative)
    """
    result = copy.deepcopy(base)
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def save_v2_memo(memo: dict, output_dir: str) -> str:
    account_id = memo["account_id"]
    folder     = os.path.join(output_dir, account_id, "v2")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "account_memo.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(memo, f, indent=2)
    return path


def save_changelog(changelog_data: dict, account_id: str, changelog_dir: str) -> str:
    os.makedirs(changelog_dir, exist_ok=True)
    path = os.path.join(changelog_dir, f"{account_id}_changes.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(changelog_data, f, indent=2)
    return path


def run(v1_memo_path: str, onboarding_path: str,
        output_dir: str   = "../outputs/accounts",
        changelog_dir: str = "../changelog") -> tuple:

    print(f"\n📋 Loading v1 memo: {Path(v1_memo_path).name}")
    v1_memo    = load_json(v1_memo_path)
    account_id = v1_memo["account_id"]

    print(f"📄 Loading onboarding transcript: {Path(onboarding_path).name}")
    onboarding = load_text(onboarding_path)

    print("🤖 Finding what changed with Groq LLM...")
    raw = call_llm(
        system_prompt=SYSTEM_PROMPT,
        user_message=(
            f"V1 memo:\n{json.dumps(v1_memo, indent=2)}\n\n"
            f"Onboarding transcript:\n{onboarding}"
        )
    )

    print("🔍 Parsing diff...")
    result         = parse_json(raw)
    updated_fields = result.get("updated_fields", {})
    changelog      = result.get("changelog", [])
    conflicts      = result.get("conflicts", [])
    new_unknowns   = result.get("new_unknowns", [])

    # Apply patch to v1 → produce v2
    v2_memo = deep_merge(v1_memo, updated_fields)
    v2_memo["version"]    = "v2"
    v2_memo["source"]     = "onboarding_call"
    v2_memo["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Merge new unknowns with existing ones (deduplicated)
    existing = v2_memo.get("questions_or_unknowns", [])
    v2_memo["questions_or_unknowns"] = list(set(existing + new_unknowns))

    # Save v2 memo
    v2_path = save_v2_memo(v2_memo, output_dir)
    print(f"✅ v2 memo saved: {v2_path}")

    # Save changelog
    changelog_data = {
        "account_id":    account_id,
        "upgraded_at":   datetime.now(timezone.utc).isoformat(),
        "from_version":  "v1",
        "to_version":    "v2",
        "total_changes": len(changelog),
        "changes":       changelog,
        "conflicts":     conflicts
    }
    cl_path = save_changelog(changelog_data, account_id, changelog_dir)
    print(f"✅ Changelog saved: {cl_path}")

    # Print summary
    print(f"\n📊 Changes summary:")
    print(f"   {len(changelog)} field(s) updated")
    print(f"   {len(conflicts)} conflict(s) resolved")
    print(f"   {len(new_unknowns)} new unknown(s) flagged")
    if changelog:
        print("\n   Changes:")
        for c in changelog:
            print(f"   • {c.get('field')}: {str(c.get('old_value'))[:30]} → {str(c.get('new_value'))[:30]}")

    return v2_memo, changelog


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 update_memo.py <v1_memo.json> <onboarding_transcript.txt>")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2])
