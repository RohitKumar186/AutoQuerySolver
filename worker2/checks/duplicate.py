"""
Duplicate Detector
Uses FuzzyWuzzy (near-duplicate names) and Soundex/Metaphone (phonetic matching).
Maintains an in-memory seen-records cache; swap for Redis in production.
"""

import logging
from collections import defaultdict

try:
    from fuzzywuzzy import fuzz
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False

try:
    from metaphone import doublemetaphone
    METAPHONE_AVAILABLE = True
except ImportError:
    METAPHONE_AVAILABLE = False

log = logging.getLogger("DuplicateChecker")

# ── Config ─────────────────────────────────────────────────────────────────────
FUZZY_THRESHOLD   = 85   # 0-100; higher = stricter
NAME_FIELDS       = ["name", "full_name", "first_name", "last_name", "customer_name"]
EMAIL_FIELDS      = ["email"]
PHONE_FIELDS      = ["phone", "mobile", "contact"]


class DuplicateChecker:
    def __init__(self):
        # Simple in-memory stores — replace with Redis for multi-worker deployments
        self._seen_names:   list[str]       = []
        self._seen_emails:  set[str]        = set()
        self._seen_phones:  set[str]        = set()
        self._phonetic_map: dict[str, list] = defaultdict(list)

        if not FUZZY_AVAILABLE:
            log.warning("fuzzywuzzy not installed — fuzzy name matching disabled.")
        if not METAPHONE_AVAILABLE:
            log.warning("metaphone not installed — phonetic matching disabled.")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _normalize(self, value: str) -> str:
        return str(value).strip().lower()

    def _get_field(self, record: dict, candidates: list[str]) -> str | None:
        for f in candidates:
            if record.get(f):
                return str(record[f])
        return None

    # ── Main check ─────────────────────────────────────────────────────────────

    def check(self, record: dict) -> list[str]:
        issues = []

        # 1. Exact email duplicate
        email = self._get_field(record, EMAIL_FIELDS)
        if email:
            norm = self._normalize(email)
            if norm in self._seen_emails:
                issues.append(f"[DUPLICATE] Email '{email}' has been seen before.")
            else:
                self._seen_emails.add(norm)

        # 2. Exact phone duplicate
        phone = self._get_field(record, PHONE_FIELDS)
        if phone:
            norm = self._normalize(phone).replace(" ", "").replace("-", "")
            if norm in self._seen_phones:
                issues.append(f"[DUPLICATE] Phone '{phone}' has been seen before.")
            else:
                self._seen_phones.add(norm)

        # 3. Fuzzy name duplicate (FuzzyWuzzy)
        name = self._get_field(record, NAME_FIELDS)
        if name and FUZZY_AVAILABLE:
            norm_name = self._normalize(name)
            for seen in self._seen_names:
                score = fuzz.token_sort_ratio(norm_name, seen)
                if score >= FUZZY_THRESHOLD:
                    issues.append(
                        f"[NEAR-DUPLICATE] Name '{name}' is {score}% similar to '{seen}'."
                    )
                    break
            else:
                self._seen_names.append(norm_name)

        # 4. Phonetic name duplicate (Soundex / Double Metaphone)
        if name and METAPHONE_AVAILABLE:
            primary, secondary = doublemetaphone(name)
            for code in filter(None, [primary, secondary]):
                matches = self._phonetic_map.get(code, [])
                for match in matches:
                    if self._normalize(match) != self._normalize(name):
                        issues.append(
                            f"[PHONETIC-DUPLICATE] '{name}' sounds like '{match}' "
                            f"(code={code})."
                        )
                        break
                self._phonetic_map[code].append(name)

        return issues