"""
Worker 2 — AI Checker
Uses Grok API (OpenAI-compatible) to flag suspicious records.
"""

import os
import json
import logging
import httpx
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("AIChecker")

GROK_API_KEY = os.getenv("GROK_API_KEY", "")
# fixer.py and ai_checker.py
GROK_URL   = "https://api.groq.com/openai/v1/chat/completions"  # ← change this
GROK_MODEL = "llama-3.3-70b-versatile"                          # ← change this

SYSTEM_PROMPT = """
You are a strict data-quality inspector for a database monitoring system.

Given a JSON record from a database, you must identify:
1. Typos or garbled text in name / address / description fields.
2. Values that look clearly wrong (e.g. age=999, negative prices, future birthdates).
3. Inconsistencies between related fields.
4. Anything else that looks suspicious or anomalous.

Respond ONLY with a JSON array of short issue strings.
If no issues are found, respond with an empty array: [].
Do NOT include any explanation outside the JSON array.
""".strip()


class AIChecker:
    def __init__(self):
        if not GROK_API_KEY:
            log.warning("GROK_API_KEY not set — AI checker disabled.")

    def check(self, record: dict) -> list:
        if not GROK_API_KEY:
            return []

        try:
            response = httpx.post(
                GROK_URL,
                headers={
                    "Content-Type":  "application/json",
                    "Authorization": f"Bearer {GROK_API_KEY}",
                },
                json={
                    "model": GROK_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": f"Inspect this record:\n\n{json.dumps(record, indent=2)}"},
                    ],
                    "temperature": 0,
                },
                timeout=15,
            )
            response.raise_for_status()

            text = response.json()["choices"][0]["message"]["content"].strip()
            text = text.replace("```json", "").replace("```", "").strip()

            issues = json.loads(text)
            return issues if isinstance(issues, list) else []

        except json.JSONDecodeError:
            log.error("AI checker: could not parse Grok response as JSON.")
            return []
        except Exception as exc:
            log.error(f"AI checker error: {exc}")
            return []