"""
issues/fixer.py
Step 3 — Ask Groq API to generate the corrected record.
"""

import json
import logging
import os
import time
import httpx
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("FixerNode")

GROK_API_KEY = os.getenv("GROK_API_KEY", "")
GROK_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROK_MODEL   = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """
You are a data correction specialist for a database monitoring system.

You will receive a bad database record and a list of issues found in it.

=== YOUR MOST IMPORTANT JOB: NAME CORRECTION ===

You MUST distinguish between two types of bad names:

TYPE 1 — REAL NAME WITH TYPO → FIX IT
A real human name where letters are missing, wrong, or have digits mixed in.
You MUST correct these intelligently. Do NOT set to UNKNOWN.

Examples you MUST fix:
  "Rohit Sin11"    → "Rohit Singh"      (11 is clearly 'gh' typo)
  "Jon Smth"       → "John Smith"       (missing letters)
  "rahul shrma"    → "Rahul Sharma"     (lowercase + missing letter)
  "Priya Patl"     → "Priya Patel"      (missing letter)
  "Amit Kumr"      → "Amit Kumar"       (missing letter)
  "Alice Wndrland" → "Alice Wonderland" (missing letters)
  "Ravi Sngh"      → "Ravi Singh"       (missing letter)

TYPE 2 — PURE GARBAGE → set to "UNKNOWN"
No real name can be extracted. Only garbage, symbols, or random characters.

Examples that ARE garbage:
  "B@d Us3r!"  → "UNKNOWN"   (special characters replace letters meaningfully)
  "J0hn!!"     → "UNKNOWN"   (exclamation marks, not a real name attempt)
  "R@hul$"     → "UNKNOWN"   ($ and @ are not typos)
  "xxxxx"      → "UNKNOWN"
  "12345"      → "UNKNOWN"

THE RULE: If you can read a real name underneath the typos → FIX IT.
If it is just symbols and garbage → UNKNOWN.

=== PHONE NUMBER RULES ===

- Real number with formatting issues → normalize to international format
- Clearly garbage or contains letters/symbols → set to "NEEDS_CORRECTION"
  (the user must provide their real number themselves)
- NEVER guess or invent a phone number

Examples:
  "9356-84243"   → "+91-9356842430"  (formatting fix, real number)
  "935684243A"   → "NEEDS_CORRECTION" (contains letter A, cannot fix)
  "not-a-phone"  → "NEEDS_CORRECTION"
  "99999abc"     → "NEEDS_CORRECTION"

=== GENERAL RULES ===

- Fix ONLY what is in the issues list
- Keep same field names and data types
- IMPORTANT: past fix examples are for reference only — always follow the rules above
- Confidence: 0.85-0.95 for typo fixes, 0.95-0.99 for obvious garbage

Respond ONLY with this exact JSON, no markdown, no extra text:
{
  "fixed_record": { ...corrected fields only... },
  "explanation": "what was fixed and why",
  "confidence": 0.95
}
""".strip()


def _build_prompt(record: dict, issues: list, similar: list) -> str:
    prompt = f"Bad record:\n{json.dumps(record, indent=2)}\n\n"
    prompt += f"Issues found:\n{json.dumps(issues, indent=2)}\n\n"

    if similar:
        prompt += "Similar past fixes for REFERENCE ONLY (rules above take priority):\n"
        for i, s in enumerate(similar, 1):
            prompt += (
                f"\nExample {i} (similarity={s.get('similarity', '?')}):\n"
                f"  Original : {s.get('original')}\n"
                f"  Issues   : {s.get('issues')}\n"
                f"  Fixed    : {s.get('fixed')}\n"
                f"  Reason   : {s.get('explanation')}\n"
            )
    else:
        prompt += "No similar past fixes found.\n"

    prompt += "\nNow apply the rules. If the name looks like a real name with typos, FIX IT — do not set to UNKNOWN."
    return prompt


def _call_groq(prompt: str, retries: int = 3, delay: int = 10):
    for attempt in range(1, retries + 1):
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
                        {"role": "user",   "content": prompt},
                    ],
                    "temperature": 0,
                },
                timeout=20,
            )

            if response.status_code == 429:
                wait = delay * attempt
                log.warning(f"  ⏳ Rate limited (429) — waiting {wait}s before retry {attempt}/{retries}")
                time.sleep(wait)
                continue

            if response.status_code >= 400:
                log.error(f"  ❌ API error {response.status_code}: {response.text}")
                return None

            response.raise_for_status()

            raw_text = response.json()["choices"][0]["message"]["content"].strip()
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(raw_text)

        except json.JSONDecodeError:
            log.error("  ❌ Could not parse Groq response as JSON.")
            return None
        except Exception as exc:
            log.error(f"  ❌ Fixer error (attempt {attempt}): {exc}")
            if attempt < retries:
                time.sleep(delay)

    log.error("  ❌ All retries exhausted.")
    return None


def fixer_node(state: dict) -> dict:
    record  = state.get("record", {})
    issues  = state.get("issues", [])
    similar = state.get("similar", [])

    if not GROK_API_KEY:
        log.warning("  ⚠️  GROK_API_KEY not set — fixer skipped.")
        return {**state, "fix": None}

    prompt = _build_prompt(record, issues, similar)
    log.info(f"  🤖 Asking Groq to fix record id={record.get('id', '?')} ...")

    fix = _call_groq(prompt)

    if not fix:
        return {**state, "fix": None}

    if "fixed_record" not in fix or "explanation" not in fix:
        log.error("  ❌ Groq response missing required fields.")
        return {**state, "fix": None}

    log.info(
        f"  ✅ Fix generated — confidence={fix.get('confidence', '?')} "
        f"explanation='{fix.get('explanation', '')[:80]}'"
    )
    return {**state, "fix": fix}