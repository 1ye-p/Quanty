"""notification_channel — Notification channel abstraction for alerts.

Provides a pluggable interface for sending alert notifications via different
channels (webhook, email, dingtalk). Channels are registered in the database
and dispatched when alerts fire.
"""

from __future__ import annotations

import abc
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class NotificationChannel(abc.ABC):
    """Abstract base class for notification channels."""

    @abc.abstractmethod
    def send(self, title: str, message: str, severity: str = "warning", **kwargs: Any) -> bool:
        """Send a notification.

        Args:
            title: Short alert title.
            message: Full alert message body.
            severity: Alert severity level (warning, critical, info).
            **kwargs: Channel-specific parameters.

        Returns:
            True if sent successfully, False otherwise.
        """

    @property
    @abc.abstractmethod
    def channel_type(self) -> str:
        """Unique channel type identifier."""


class WebhookChannel(NotificationChannel):
    """Send notifications via HTTP webhook (POST JSON)."""

    def __init__(self, url: str, headers: dict[str, str] | None = None) -> None:
        self.url = url
        self.headers = headers or {}

    @property
    def channel_type(self) -> str:
        return "webhook"

    def send(self, title: str, message: str, severity: str = "warning", **kwargs: Any) -> bool:
        try:
            import urllib.request

            payload = json.dumps({
                "title": title,
                "message": message,
                "severity": severity,
                **kwargs,
            }).encode()
            req = urllib.request.Request(
                self.url,
                data=payload,
                headers={"Content-Type": "application/json", **self.headers},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return 200 <= resp.status < 300
        except Exception as exc:
            logger.warning("WebhookChannel.send failed: %s", exc)
            return False


class EmailChannel(NotificationChannel):
    """Send notifications via SMTP email."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        from_addr: str = "",
        to_addrs: list[str] | None = None,
        use_tls: bool = True,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs or []
        self.use_tls = use_tls

    @property
    def channel_type(self) -> str:
        return "email"

    def send(self, title: str, message: str, severity: str = "warning", **kwargs: Any) -> bool:
        try:
            import smtplib
            from email.mime.text import MIMEText

            msg = MIMEText(message, "plain", "utf-8")
            msg["Subject"] = f"[cQuant {severity.upper()}] {title}"
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.username:
                    server.login(self.username, self.password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
            return True
        except Exception as exc:
            logger.warning("EmailChannel.send failed: %s", exc)
            return False


class DingTalkChannel(NotificationChannel):
    """Send notifications via DingTalk robot webhook."""

    def __init__(self, webhook_url: str, secret: str = "") -> None:
        self.webhook_url = webhook_url
        self.secret = secret

    @property
    def channel_type(self) -> str:
        return "dingtalk"

    def send(self, title: str, message: str, severity: str = "warning", **kwargs: Any) -> bool:
        try:
            import urllib.request

            url = self.webhook_url
            if self.secret:
                import hashlib
                import hmac
                import time
                from base64 import b64encode
                from urllib.parse import quote

                timestamp = str(int(time.time() * 1000))
                string_to_sign = f"{timestamp}\n{self.secret}"
                hmac_code = hmac.new(
                    self.secret.encode(), string_to_sign.encode(), hashlib.sha256
                ).digest()
                sign = quote(b64encode(hmac_code))
                url = f"{url}&timestamp={timestamp}&sign={sign}"

            severity_emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(severity, "⚪")
            payload = json.dumps({
                "msgtype": "markdown",
                "markdown": {
                    "title": f"{severity_emoji} {title}",
                    "text": f"## {severity_emoji} {title}\n\n{message}",
                },
            }).encode()
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return 200 <= resp.status < 300
        except Exception as exc:
            logger.warning("DingTalkChannel.send failed: %s", exc)
            return False


# ── Channel registry ──────────────────────────────────────────────────────────

CHANNELS: dict[str, type[NotificationChannel]] = {
    "webhook": WebhookChannel,
    "email": EmailChannel,
    "dingtalk": DingTalkChannel,
}


def get_channel(channel_type: str, config: dict[str, Any]) -> NotificationChannel | None:
    """Factory: create a channel instance from type + config dict.

    Args:
        channel_type: One of 'webhook', 'email', 'dingtalk'.
        config: Channel-specific configuration parameters.

    Returns:
        Channel instance, or None if type is unknown.
    """
    cls = CHANNELS.get(channel_type)
    if cls is None:
        logger.warning("Unknown channel type: %s", channel_type)
        return None
    try:
        return cls(**config)
    except Exception as exc:
        logger.warning("Failed to create %s channel: %s", channel_type, exc)
        return None
