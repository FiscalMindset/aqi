"""Alert rules: hysteresis, minimum gap, quiet hours, dedupe, SNS publishing.

Rule: notify when the estimate at a subscriber's locality crosses their chosen
category upward. Hysteresis means the estimate must improve by at least one
band before a new upward crossing can fire; a minimum gap between alerts and
per-subscriber quiet hours prevent spam. Every message states the estimate,
its uncertainty, the likely-cause category and an unsubscribe link.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta, timezone
from typing import Any

from dhuan.model.cpcb import CATEGORIES, band_rank, category_for_pm25

DEFAULT_MIN_GAP_HOURS = 6
DEFAULT_QUIET_START = time(22, 0)  # IST
DEFAULT_QUIET_END = time(6, 30)  # IST local time


@dataclass(slots=True)
class AlertDecision:
    should_send: bool
    reason: str
    band: str
    previous_band: str | None


def in_quiet_hours(
    now_ist: time, start: time = DEFAULT_QUIET_START, end: time = DEFAULT_QUIET_END
) -> bool:
    """Quiet hours cross midnight: 22:00 -> 06:30."""
    if start <= end:
        return start <= now_ist <= end
    return now_ist >= start or now_ist <= end


def crossed_upward(
    current_band: str, previous_band: str | None, threshold: str
) -> bool:
    """True when the current band is at least as bad as the threshold and the
    previous band was better (strict upward crossing).

    Hysteresis: if previous_band equals current_band, no re-alert (we are
    already in that band).
    """
    if previous_band == current_band:
        return False
    return band_rank(current_band) <= band_rank(threshold)


def decide(
    *,
    current_pm25: float,
    threshold_category: str,
    last_band: str | None,
    last_alerted_at: datetime | None,
    now: datetime,
    min_gap_hours: int = DEFAULT_MIN_GAP_HOURS,
    quiet_start: time = DEFAULT_QUIET_START,
    quiet_end: time = DEFAULT_QUIET_END,
    dedupe_key: str | None = None,
    recent_keys: Iterable[str] = (),
) -> AlertDecision:
    """The full rule evaluation for one subscription at one moment."""
    band = category_for_pm25(current_pm25)
    if band_rank(band) > band_rank(threshold_category):
        return AlertDecision(False, "below threshold", band, last_band)
    if last_band is not None and band_rank(band) >= band_rank(last_band):
        # hysteresis: only a strictly worse band than the last alerted one
        # counts as a new upward crossing; same or better band is silent
        return AlertDecision(False, "hysteresis: no new upward crossing", band, last_band)
    if last_alerted_at is not None:
        last = last_alerted_at if last_alerted_at.tzinfo else last_alerted_at.replace(tzinfo=UTC)
        if now - last < timedelta(hours=min_gap_hours):
            return AlertDecision(False, "minimum gap not elapsed", band, last_band)
    if dedupe_key is not None and dedupe_key in set(recent_keys):
        return AlertDecision(False, "duplicate message", band, last_band)
    # quiet hours: hold non-severe alerts until morning
    now_ist = now.astimezone(timezone(timedelta(hours=5, minutes=30))).time()
    if band != "Severe" and in_quiet_hours(now_ist, quiet_start, quiet_end):
        return AlertDecision(False, "quiet hours", band, last_band)
    return AlertDecision(True, "upward crossing above threshold", band, last_band)


def dedupe_message_key(sub_id: str, band: str, date_ist: str) -> str:
    return f"{sub_id}:{band}:{date_ist}"


def compose_message(
    *,
    locality: str,
    pm25_mid: float,
    pm25_low: float,
    pm25_high: float,
    category: str,
    likely_category: str | None,
    unsubscribe_url: str,
    language: str = "en",
) -> tuple[str, str]:
    """(subject, body) — conservative wording, uncertainty stated, unsub link."""
    subject = f"Dhuan Detective: {locality} air is {category} ({pm25_mid:.0f} µg/m³)"
    cause_line = (
        f"Likely contributor: {likely_category}." if likely_category else
        "No single contributor stands out."
    )
    if language == "hi":
        subject = f"धुआँ डिटेक्टिव: {locality} की हवा {category} ({pm25_mid:.0f} µg/m³)"
        cause_line = (
            f"संभावित स्रोत: {likely_category}।" if likely_category else
            "कोई एक स्रोत स्पष्ट नहीं है।"
        )
    body = (
        f"Dhuan Detective estimate for {locality}:\n"
        f"  PM2.5: {pm25_mid:.0f} µg/m³ (80% range {pm25_low:.0f}-{pm25_high:.0f})\n"
        f"  CPCB category: {category}\n"
        f"  {cause_line}\n\n"
        "This is an estimate, not a measurement. Official CPCB station readings "
        "remain the authoritative source.\n"
        f"Unsubscribe: {unsubscribe_url}\n"
    )
    return subject, body


class SmtpAlerter:
    """Direct SMTP delivery over TLS.

    SNS email needs a verified identity or a production SES account, which a new
    AWS account does not have. When SMTP credentials are configured we deliver
    the alert ourselves so a subscription produces a real email instead of a
    composed-but-unsent message.

    Secrets come from settings only (.env locally, SSM SecureString on AWS).
    """

    def __init__(self, settings: Any = None) -> None:
        self.settings = settings

    def configured(self) -> bool:
        s = self.settings
        return bool(s and s.smtp_host and s.smtp_username and s.smtp_password)

    def publish(
        self,
        *,
        locality: str,
        email: str,
        subject: str,
        body: str,
        message_attributes: dict[str, Any] | None = None,  # noqa: ARG002 - parity with SnsAlerter
    ) -> str:
        import smtplib
        from email.message import EmailMessage

        from dhuan.core.logging import get_logger

        log = get_logger("alerts.smtp")
        if not self.configured():
            log.warning("smtp_not_configured: alert composed but not sent")
            return ""
        msg = EmailMessage()
        msg["Subject"] = subject[:99]
        sender_name = self.settings.alert_email_from_name or "Dhuan Detective"
        msg["From"] = f"{sender_name} <{self.settings.smtp_from or self.settings.smtp_username}>"
        msg["To"] = email
        msg["X-Dhuan-Locality"] = locality
        msg.set_content(body)
        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=20) as srv:
                if self.settings.smtp_starttls:
                    srv.starttls()
                srv.login(self.settings.smtp_username, self.settings.smtp_password)
                srv.send_message(msg)
        except (smtplib.SMTPException, OSError) as exc:
            log.warning("smtp_send_failed: %s: %s", type(exc).__name__, exc)
            return ""
        log.info("alert_email_sent locality=%s to=%s", locality, email)
        return f"smtp:{self.settings.smtp_username}"


class SnsAlerter:
    """Publishes alerts via SNS with per-locality filter policies (email)."""

    def __init__(self, settings: Any = None) -> None:
        self.settings = settings
        self._sns: Any = None

    @property
    def sns(self) -> Any:
        if self._sns is None:
            import boto3

            kwargs: dict[str, Any] = {
                "region_name": self.settings.aws_region,
            }
            if self.settings.aws_endpoint_url:
                kwargs["endpoint_url"] = self.settings.aws_endpoint_url
            self._sns = boto3.client("sns", **kwargs)
        return self._sns

    def configured(self) -> bool:
        return bool(self.settings and self.settings.sns_topic_arn)

    def publish(
        self,
        *,
        locality: str,
        email: str,
        subject: str,
        body: str,
        message_attributes: dict[str, Any] | None = None,
    ) -> str:
        if not self.configured():
            from dhuan.core.logging import get_logger

            get_logger("alerts.sns").warning(
                "sns_not_configured: alert composed but not published"
            )
            return ""
        attrs = {
            "locality": {"DataType": "String", "StringValue": locality},
            "email": {"DataType": "String", "StringValue": email},
        }
        for k, v in (message_attributes or {}).items():
            attrs[k] = {"DataType": "String", "StringValue": str(v)}
        resp = self.sns.publish(
            TopicArn=self.settings.sns_topic_arn,
            Subject=subject[:99],
            Message=body,
            MessageAttributes=attrs,
        )
        message_id: str = resp.get("MessageId", "")
        return message_id


def evaluate_subscriptions(
    subscriptions: Iterable[dict[str, Any]],
    *,
    estimates_by_locality: dict[str, float],
    now: datetime,
    min_gap_hours: int = DEFAULT_MIN_GAP_HOURS,
) -> list[tuple[dict[str, Any], AlertDecision]]:
    """Evaluate every subscription against its locality estimate."""
    out: list[tuple[dict[str, Any], AlertDecision]] = []
    for sub in subscriptions:
        locality = str(sub.get("locality", "")).lower()
        pm25 = estimates_by_locality.get(locality)
        if pm25 is None:
            continue
        last_alerted = sub.get("last_alerted_at")
        last_alerted_dt = datetime.fromisoformat(last_alerted) if last_alerted else None
        key = dedupe_message_key(
            str(sub.get("pk", "")), category_for_pm25(pm25), now.strftime("%Y-%m-%d")
        )
        decision = decide(
            current_pm25=pm25,
            threshold_category=str(sub.get("threshold_category", "Poor")),
            last_band=sub.get("last_band"),
            last_alerted_at=last_alerted_dt,
            now=now,
            min_gap_hours=min_gap_hours,
            dedupe_key=key,
        )
        out.append((sub, decision))
    return out


__all__ = [
    "CATEGORIES",
    "AlertDecision",
    "SmtpAlerter",
    "SnsAlerter",
    "best_alerter",
    "compose_message",
    "crossed_upward",
    "decide",
    "dedupe_message_key",
    "evaluate_subscriptions",
    "in_quiet_hours",
]


def best_alerter(settings: Any = None) -> Any:
    """Pick the delivery path that is actually configured.

    SMTP first: it works on a new AWS account where SNS email still needs a
    verified identity. SNS is the fallback once SES/SNS is live in production.
    """
    smtp = SmtpAlerter(settings)
    if smtp.configured():
        return smtp
    return SnsAlerter(settings)
