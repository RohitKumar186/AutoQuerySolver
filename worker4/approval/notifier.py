"""
approval/notifier.py
Sends "please approve this fix" alerts via Slack webhook and/or SMTP email.
Called when a fix is pushed to the human approval queue.
"""

import json
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from typing import Optional

import httpx

log = logging.getLogger("Notifier")

# ── Config from .env ──────────────────────────────────────────────────────────
SLACK_WEBHOOK   = os.getenv("SLACK_WEBHOOK",   "")
SMTP_HOST       = os.getenv("SMTP_HOST",       "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT",   "587"))
SMTP_USER       = os.getenv("SMTP_USER",       "")
SMTP_PASSWORD   = os.getenv("SMTP_PASSWORD",   "")
ALERT_EMAIL_TO  = os.getenv("ALERT_EMAIL_TO",  "")
APPROVAL_URL    = os.getenv("APPROVAL_URL",    "http://localhost:8000")


class Notifier:
    """
    Sends approval-request notifications over Slack and/or Email.
    Gracefully skips if credentials are not configured.
    """

    def __init__(self):
        self._slack_ok = bool(SLACK_WEBHOOK)
        self._email_ok = bool(SMTP_USER and SMTP_PASSWORD and ALERT_EMAIL_TO)

        if self._slack_ok:
            log.info("✅ Slack notifier ready.")
        else:
            log.info("ℹ️  SLACK_WEBHOOK not set — Slack alerts disabled.")

        if self._email_ok:
            log.info("✅ Email notifier ready.")
        else:
            log.info("ℹ️  SMTP credentials not set — email alerts disabled.")

    # ── Public API ────────────────────────────────────────────────────────────

    def notify_pending(self, fix_payload: dict):
        """Send an alert that a fix needs human review."""
        fix_id     = fix_payload.get("fix_id", "unknown")
        confidence = fix_payload.get("confidence", 0)
        issues     = fix_payload.get("issues", [])
        original   = fix_payload.get("original", {})
        fixed      = fix_payload.get("fixed", {})
        explanation = fix_payload.get("explanation", "")

        approve_url = f"{APPROVAL_URL}/approve/{fix_id}"
        reject_url  = f"{APPROVAL_URL}/reject/{fix_id}"

        if self._slack_ok:
            self._send_slack(fix_id, confidence, issues, original, fixed, explanation, approve_url, reject_url)

        if self._email_ok:
            self._send_email(fix_id, confidence, issues, original, fixed, explanation, approve_url, reject_url)

        if not self._slack_ok and not self._email_ok:
            log.warning(f"  ⚠️  No notification channels configured — fix_id={fix_id} queued silently.")

    def notify_applied(self, fix_id: str, record_id: int):
        """Notify that a fix was successfully applied to the DB."""
        if self._slack_ok:
            self._slack_simple(
                text=f"✅ *Fix applied to DB* — fix_id=`{fix_id}` record_id=`{record_id}`",
                color="good"
            )
        log.info(f"  📣 Applied notification sent for fix_id={fix_id}")

    def notify_rejected(self, fix_id: str, reason: str):
        """Notify that a fix was rejected."""
        if self._slack_ok:
            self._slack_simple(
                text=f"❌ *Fix rejected* — fix_id=`{fix_id}` reason: {reason}",
                color="danger"
            )
        log.info(f"  📣 Rejected notification sent for fix_id={fix_id}")

    # ── Slack ─────────────────────────────────────────────────────────────────

    def _send_slack(
        self, fix_id, confidence, issues, original, fixed,
        explanation, approve_url, reject_url
    ):
        issue_list = "\n".join(f"• {i}" for i in issues[:5])
        orig_name  = original.get("name", "?")
        fixed_name = fixed.get("name", "?")
        orig_phone = original.get("phone", "?")
        fixed_phone= fixed.get("phone", "?")

        payload = {
            "text": f"🩺 *Watchman Doctor* — Fix needs your approval",
            "attachments": [
                {
                    "color":  "warning",
                    "fields": [
                        {"title": "Fix ID",      "value": f"`{fix_id}`",                         "short": True},
                        {"title": "Confidence",  "value": f"{confidence:.0%}",                   "short": True},
                        {"title": "Issues",      "value": issue_list or "none",                  "short": False},
                        {"title": "Name",        "value": f"`{orig_name}` → `{fixed_name}`",    "short": True},
                        {"title": "Phone",       "value": f"`{orig_phone}` → `{fixed_phone}`",  "short": True},
                        {"title": "Explanation", "value": explanation[:300],                     "short": False},
                    ],
                    "actions": [
                        {"type": "button", "text": "✅ Approve", "url": approve_url, "style": "primary"},
                        {"type": "button", "text": "❌ Reject",  "url": reject_url,  "style": "danger"},
                    ],
                }
            ],
        }

        try:
            resp = httpx.post(SLACK_WEBHOOK, json=payload, timeout=10)
            resp.raise_for_status()
            log.info(f"  📨 Slack alert sent — fix_id={fix_id}")
        except Exception as exc:
            log.error(f"  ❌ Slack send failed: {exc}")

    def _slack_simple(self, text: str, color: str = "good"):
        try:
            httpx.post(
                SLACK_WEBHOOK,
                json={"attachments": [{"color": color, "text": text}]},
                timeout=10,
            )
        except Exception as exc:
            log.error(f"  ❌ Slack simple send failed: {exc}")

    # ── Email ─────────────────────────────────────────────────────────────────

    def _send_email(
        self, fix_id, confidence, issues, original, fixed,
        explanation, approve_url, reject_url
    ):
        subject = f"[Watchman] Fix needs approval — {fix_id}"

        issue_rows = "".join(f"<li>{i}</li>" for i in issues)
        html = f"""
        <html><body style="font-family:monospace;background:#0d0f12;color:#e2e4ec;padding:24px">
        <h2 style="color:#5b8ef5">🩺 Watchman Doctor — Fix Needs Approval</h2>
        <table style="border-collapse:collapse;width:100%">
            <tr><td style="padding:6px;color:#6b7280">Fix ID</td>
                <td style="padding:6px"><code>{fix_id}</code></td></tr>
            <tr><td style="padding:6px;color:#6b7280">Confidence</td>
                <td style="padding:6px">{confidence:.0%}</td></tr>
            <tr><td style="padding:6px;color:#6b7280">Original Name</td>
                <td style="padding:6px"><code>{original.get('name','?')}</code></td></tr>
            <tr><td style="padding:6px;color:#6b7280">Fixed Name</td>
                <td style="padding:6px"><code>{fixed.get('name','?')}</code></td></tr>
            <tr><td style="padding:6px;color:#6b7280">Original Phone</td>
                <td style="padding:6px"><code>{original.get('phone','?')}</code></td></tr>
            <tr><td style="padding:6px;color:#6b7280">Fixed Phone</td>
                <td style="padding:6px"><code>{fixed.get('phone','?')}</code></td></tr>
            <tr><td style="padding:6px;color:#6b7280">Explanation</td>
                <td style="padding:6px">{explanation}</td></tr>
        </table>
        <h3 style="color:#f59e0b">Issues Found</h3>
        <ul>{issue_rows}</ul>
        <div style="margin-top:24px">
            <a href="{approve_url}" style="background:#22c55e;color:white;padding:10px 20px;border-radius:6px;text-decoration:none;margin-right:12px">✅ Approve Fix</a>
            <a href="{reject_url}"  style="background:#ef4444;color:white;padding:10px 20px;border-radius:6px;text-decoration:none">❌ Reject Fix</a>
        </div>
        </body></html>
        """

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = SMTP_USER
            msg["To"]      = ALERT_EMAIL_TO
            msg.attach(MIMEText(html, "html"))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_USER, ALERT_EMAIL_TO, msg.as_string())

            log.info(f"  📧 Email alert sent to {ALERT_EMAIL_TO} — fix_id={fix_id}")
        except Exception as exc:
            log.error(f"  ❌ Email send failed: {exc}")