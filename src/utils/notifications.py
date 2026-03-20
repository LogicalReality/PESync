"""PESync - Sistema de notificaciones via Telegram."""

from __future__ import annotations
import os
import logging
import time
from typing import Any
import requests # type: ignore

logger = logging.getLogger("pesync.notifications")

MAX_RETRIES = 3
RETRY_DELAY = 2


class TelegramNotifier:
    def __init__(self, bot_token: str | None = None, chat_id: str | None = None):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.enabled = (
            os.environ.get("TELEGRAM_NOTIFICATIONS", "true").lower() == "true"
        )
        self.api_url = (
            f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else ""
        )

    def _send_request(self, endpoint: str, data: dict[str, Any]) -> bool:
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False

        url = f"{self.api_url}/{endpoint}"
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(url, data=data, timeout=10)
                if response.status_code == 200:
                    return True
                logger.warning(
                    f"[Telegram] Intento {attempt + 1} fallido: {response.status_code}"
                )
            except requests.RequestException as e:
                logger.warning(f"[Telegram] Error de red en intento {attempt + 1}: {e}")

            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

        logger.error(f"[Telegram] Fallo total al enviar tras {MAX_RETRIES} intentos")
        return False

    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        return self._send_request(
            "sendMessage",
            {"chat_id": self.chat_id, "text": text, "parse_mode": parse_mode},
        )

    def send_sync_summary(
        self,
        uploaded_files: list[tuple[str, str]],
        deleted_files: list[str],
        provider_name: str,
    ) -> bool:
        if not uploaded_files and not deleted_files:
            return False

        lines = ["✅ *PESync - Sync Completada*\n"]

        from datetime import datetime

        lines.append(f"📅 *Fecha:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        if uploaded_files:
            lines.append(f"📦 *Subidos:* {len(uploaded_files)} archivo(s)\n")
            for filename, category in uploaded_files:
                lines.append(f"   • `{filename}` ({category})")

        if deleted_files:
            lines.append(f"\n🗑️ *Eliminados:* {len(deleted_files)} archivo(s)\n")
            for filename in deleted_files:
                lines.append(f"   • `{filename}`")

        lines.append(f"\n☁️ *Provider:* {provider_name}")

        text = "\n".join(lines)
        return self.send_message(text)
