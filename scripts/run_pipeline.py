"""
run_pipeline.py
===============
WHAT THIS DOES:
  This is the ONE script you run to process everything.

  It automatically:
  1. Finds all transcript files in /inputs
  2. For each demo transcript → extracts memo → generates v1 agent spec
  3. If matching onboarding transcript exists → updates to v2 + changelog
  4. Prints a summary at the end

  IDEMPOTENT: Running it twice produces the same result. Safe to re-run.

HOW TO RUN:
  cd scripts
  python3 run_pipeline.py

FILE NAMING CONVENTION (files must be in /inputs folder):
  bens_electric_demo.txt          ← triggers Pipeline A (v1)
  bens_electric_onboarding.txt    ← triggers Pipeline B (v2)
  acme_fire_demo.txt
  acme_fire_onboarding.txt
  ...
"""

import os
import sys
import glob
from pathlib import Path

# Add scripts dir to path so we can import our modules
sys.path.insert(0, os.path.dirname(__file__))

from extract_memo        import run as extract_memo
from generate_agent_spec import run as generate_spec
from update_memo         import run as update_memo

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent.parent
INPUT_DIR      = BASE_DIR / "inputs"
OUTPUT_DIR     = BASE_DIR / "outputs" / "accounts"
CHANGELOG_DIR  = BASE_DIR / "changelog"


def check_env():
    """Make sure API key is set before starting."""
    if not os.environ.get("GROQ_API_KEY"):
        print("\n❌ GROQ_API_KEY not set.")
        print("   Run: source .env")
        print("   Get a free key at: https://console.groq.com\n")
        sys.exit(1)


def find_accounts(input_dir: Path) -> list:
    """
    Scan inputs folder and group demo + onboarding files by account.
    
    Returns list like:
    [
      {
        "account_key":    "bens_electric",
        "demo_path":      "inputs/bens_electric_demo.txt",
        "onboarding_path": "inputs/bens_electric_onboarding.txt"  # or None
      },
      ...
    ]
    """
    demo_files = sorted(input_dir.glob("*_demo.txt"))

    if not demo_files:
        return []

    accounts = []
    for demo_file in demo_files:
        account_key      = demo_file.stem.replace("_demo", "")
        onboarding_file  = input_dir / f"{account_key}_onboarding.txt"

        accounts.append({
            "account_key":     account_key,
            "demo_path":       str(demo_file),
            "onboarding_path": str(onboarding_file) if onboarding_file.exists() else None
        })

    return accounts


def run_account(account: dict) -> dict:
    """
    Run the full pipeline for one account.
    Returns a result dict for the summary report.
    """
    account_key    = account["account_key"]
    demo_path      = account["demo_path"]
    onboarding_path = account["onboarding_path"]

    print(f"\n{'='*60}")
    print(f"🏢  {account_key.replace('_', ' ').title()}")
    print(f"{'='*60}")

    result = {
        "account_key": account_key,
        "status":      "success",
        "v1":          False,
        "v2":          False,
        "changes":     0,
        "errors":      []
    }

    # ── Pipeline A: Demo → v1 ─────────────────────────────────────────────────
    try:
        print(f"\n▶ Pipeline A: demo transcript → v1 memo + agent spec")

        memo       = extract_memo(demo_path, output_dir=str(OUTPUT_DIR))
        account_id = memo["account_id"]
        v1_memo_path = OUTPUT_DIR / account_id / "v1" / "account_memo.json"

        generate_spec(str(v1_memo_path), output_dir=str(OUTPUT_DIR))

        result["v1"]         = True
        result["account_id"] = account_id

    except Exception as e:
        result["status"] = "failed"
        result["errors"].append(f"Pipeline A: {e}")
        print(f"\n❌ Pipeline A failed: {e}")
        return result

    # ── Pipeline B: Onboarding → v2 ───────────────────────────────────────────
    if onboarding_path:
        try:
            print(f"\n▶ Pipeline B: onboarding transcript → v2 memo + agent spec + changelog")

            v2_memo, changelog = update_memo(
                str(v1_memo_path),
                onboarding_path,
                output_dir=str(OUTPUT_DIR),
                changelog_dir=str(CHANGELOG_DIR)
            )

            v2_memo_path = OUTPUT_DIR / account_id / "v2" / "account_memo.json"
            generate_spec(str(v2_memo_path), output_dir=str(OUTPUT_DIR))

            result["v2"]      = True
            result["changes"] = len(changelog)

        except Exception as e:
            result["status"] = "partial"
            result["errors"].append(f"Pipeline B: {e}")
            print(f"\n❌ Pipeline B failed: {e}")
    else:
        print(f"\n⚠️  No onboarding transcript found — skipping v2")
        print(f"   (Add: inputs/{account_key}_onboarding.txt to generate v2)")

    # ── Retell: Skipped (free tier has no API access) ─────────────────────────
    best_version = "v2" if result["v2"] else "v1"
    spec_path = OUTPUT_DIR / account_id / best_version / "agent_spec.json"
    print(f"\n{'─'*60}")
    print(f"🔁  RETELL API SKIPPED — Free tier does not support programmatic agent creation.")
    print(f"📄  Manual import steps for this account:")
    print(f"    1. Open: {spec_path}")
    print(f"    2. Copy the value of \"system_prompt\"")
    print(f"    3. Go to https://retell.ai → Create New Agent")
    print(f"    4. Paste into System Prompt field")
    print(f"    5. Set voice + transfer number from \"key_variables\" in the same file")
    print(f"    6. Save → Test → Go Live ✅")
    print(f"{'─'*60}")

    return result


def print_summary(results: list):
    """Print a clean summary table after all accounts are processed."""
    print(f"\n\n{'='*60}")
    print("📊  PIPELINE SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Account':<28} {'v1':^5} {'v2':^5} {'Changes':^8}  Status")
    print(f"  {'-'*56}")

    for r in results:
        name    = r["account_key"].replace("_", " ").title()[:26]
        v1      = "✅" if r["v1"]  else "❌"
        v2      = "✅" if r["v2"]  else "—"
        changes = str(r["changes"]) if r["v2"] else "—"
        status  = r["status"]
        print(f"  {name:<28} {v1:^5} {v2:^5} {changes:^8}  {status}")

    total   = len(results)
    success = sum(1 for r in results if r["status"] == "success")
    partial = sum(1 for r in results if r["status"] == "partial")
    failed  = sum(1 for r in results if r["status"] == "failed")

    print(f"\n  Total: {total}  ✅ Success: {success}  ⚠️ Partial: {partial}  ❌ Failed: {failed}")
    print(f"\n  Outputs: {OUTPUT_DIR}")
    print(f"  Changelogs: {CHANGELOG_DIR}")
    print(f"\n{'='*60}")
    print(f"🔁  RETELL NOTE:")
    print(f"    Retell API is not available on free tier.")
    print(f"    All agent specs have been saved to outputs/accounts/<id>/v1 and v2.")
    print(f"    Manually paste each agent_spec.json → system_prompt into Retell UI.")
    print(f"    See README.md → 'Upload to Retell' section for full steps.")
    print(f"{'='*60}")


def main():
    check_env()

    print("\n🔍  Scanning for transcripts...")
    accounts = find_accounts(INPUT_DIR)

    if not accounts:
        print(f"\n⚠️  No transcript files found in: {INPUT_DIR}")
        print("\n  Add files named like:")
        print("    inputs/bens_electric_demo.txt")
        print("    inputs/bens_electric_onboarding.txt")
        print("\n  Or run transcribe.py first if you have audio files.")
        sys.exit(0)

    print(f"✅  Found {len(accounts)} account(s) to process")
    for a in accounts:
        has_onboarding = "✅" if a["onboarding_path"] else "⚠️ (no onboarding)"
        print(f"   • {a['account_key']}  {has_onboarding}")

    results = []
    for account in accounts:
        result = run_account(account)
        results.append(result)

    print_summary(results)


if __name__ == "__main__":
    main()
