"""
AI-Powered Checker
Sends the record to Google Gemini and asks it to flag anything suspicious.
"""

import os
import json
import logging
import httpx
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("AIChecker")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

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
        if not GEMINI_API_KEY:
            log.warning("GEMINI_API_KEY not set — AI checker disabled.")

    def check(self, record: dict) -> list[str]:
        if not GEMINI_API_KEY:
            return []

        prompt = f"{SYSTEM_PROMPT}\n\nInspect this database record and report issues:\n\n{json.dumps(record, indent=2)}"

        try:
            response = httpx.post(
                f"{GEMINI_URL}?key={GEMINI_API_KEY}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [
                        {"parts": [{"text": prompt}]}
                    ]
                },
                timeout=15,
            )
            response.raise_for_status()

            text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

            # Strip markdown code fences if Gemini wraps in ```json
            text = text.replace("```json", "").replace("```", "").strip()

            issues = json.loads(text)
            return issues if isinstance(issues, list) else []

        except json.JSONDecodeError:
            log.error("AI checker: could not parse Gemini response as JSON.")
            return []
        except Exception as exc:
            log.error(f"AI checker error: {exc}")
            return []