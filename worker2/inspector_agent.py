"""
Worker 2 — The Inspector (Anomaly Detection Agent)
Consumes CDC events from Kafka and runs:
  - Rule-based checks  (regex, Pandera, Great Expectations)
  - AI-powered checks  (Claude API)
  - Duplicate detection (FuzzyWuzzy / Soundex)
"""

import json
import logging
import os
from kafka import KafkaConsumer
from dotenv import load_dotenv

from checks.rule_based   import RuleBasedChecker
from checks.ai_checker   import AIChecker
from checks.duplicate    import DuplicateChecker

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("InspectorAgent")

KAFKA_BROKER   = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC    = os.getenv("KAFKA_TOPIC",  "dbserver1.watchman.customers")
KAFKA_GROUP    = os.getenv("KAFKA_GROUP",  "inspector-group")


def parse_event(raw_value: bytes) -> dict | None:
    """Extract the 'after' payload from a Debezium CDC envelope."""
    try:
        msg = json.loads(raw_value)
        payload = msg.get("payload", msg)
        after = payload.get("after")
        op    = payload.get("op", "?")       # c=create, u=update, d=delete, r=read
        return {"op": op, "record": after} if after else None
    except (json.JSONDecodeError, AttributeError):
        return None


def run():
    log.info("🔍 Inspector Agent starting — connecting to Kafka …")

    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        group_id=KAFKA_GROUP,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: v,   # raw bytes; we parse manually
    )

    rule_checker  = RuleBasedChecker()
    ai_checker    = AIChecker()
    dup_checker   = DuplicateChecker()

    log.info(f"✅ Listening on topic: {KAFKA_TOPIC}")

    for msg in consumer:
        event = parse_event(msg.value)
        if not event:
            continue

        op     = event["op"]
        record = event["record"]

        log.info(f"📥 Event [{op.upper()}] — {record}")

        issues = []

        # ── 1. Rule-based checks ──────────────────────────────────────
        rule_issues = rule_checker.check(record)
        if rule_issues:
            issues.extend(rule_issues)
            log.warning(f"  ⚠️  Rule issues: {rule_issues}")

        # ── 2. AI-powered check ───────────────────────────────────────
        ai_issues = ai_checker.check(record)
        if ai_issues:
            issues.extend(ai_issues)
            log.warning(f"  🤖 AI issues : {ai_issues}")

        # ── 3. Duplicate detection ────────────────────────────────────
        dup_issues = dup_checker.check(record)
        if dup_issues:
            issues.extend(dup_issues)
            log.warning(f"  🔁 Dup issues: {dup_issues}")

        # ── Summary ───────────────────────────────────────────────────
        if issues:
            log.error(f"❌ ANOMALY DETECTED — {len(issues)} issue(s): {issues}")
        else:
            log.info("  ✅ Record looks clean.")


if __name__ == "__main__":
    run()