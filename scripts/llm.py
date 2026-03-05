"""
llm.py
======
WHAT THIS DOES:
  Single place that handles all communication with the Groq LLM.
  Every other script imports from here instead of making API calls directly.

  Think of it as a "phone operator" — all scripts go through it
  to talk to the AI, so if you ever need to change anything you
  only change it in one place.
"""

import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
import re
import json
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from groq import Groq

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
MODEL        = "llama-3.3-70b-versatile"


def call_llm(system_prompt: str, user_message: str, max_tokens: int = 3000) -> str:
    """
    Send a message to Groq LLM and get a response back.
    
    system_prompt = the instructions (what role should AI play)
    user_message  = the actual content to process (transcript, memo etc.)
    """
    if not GROQ_API_KEY:
        raise EnvironmentError(
            "\n❌ GROQ_API_KEY not set.\n"
            "   Run: source .env\n"
            "   Get free key at: https://console.groq.com\n"
        )

    client   = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message}
        ]
    )
    return response.choices[0].message.content


def parse_json(raw: str) -> dict:
    """
    Parse JSON from LLM response.
    Safely strips markdown code fences if the model added them by mistake.
    """
    cleaned = re.sub(r"```json|```", "", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"LLM returned invalid JSON.\n"
            f"Error: {e}\n"
            f"Raw response:\n{cleaned[:500]}..."
        )