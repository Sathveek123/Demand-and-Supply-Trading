import requests
import logging
from config import settings

logger = logging.getLogger(__name__)

class TelegramSignalBot:
    """
    Telegram Bot helper to send signal notifications to Telegram Channels or Groups.
    """

    def __init__(self, token: str = None, chat_ids: list[str] = None):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        
        # Parse comma-separated list if settings config returns string
        raw_ids = chat_ids or settings.TELEGRAM_CHAT_IDS
        if isinstance(raw_ids, str):
            self.chat_ids = [cid.strip() for cid in raw_ids.split(",") if cid.strip()]
        else:
            self.chat_ids = raw_ids or []

    def send_message_to(self, chat_id: str, text: str) -> bool:
        """
        Sends formatted message to a specific Telegram chat_id.
        """
        if not self.token or not chat_id:
            print(f"[Telegram Bot Mock Output to {chat_id}]:\n{text}\n")
            return False

        base_url = settings.TELEGRAM_BASE_URL.rstrip("/")
        if not (base_url.endswith("/bot") or "/bot" in base_url):
            url = f"{base_url}/bot{self.token}/sendMessage"
        else:
            url = f"{base_url}{self.token}/sendMessage" if base_url.endswith("bot") else f"{base_url}/{self.token}/sendMessage"

        proxies = None
        if settings.TELEGRAM_PROXY:
            proxies = {
                "http": settings.TELEGRAM_PROXY,
                "https": settings.TELEGRAM_PROXY
            }

        main_keyboard = {
            "keyboard": [
                [{"text": "📊 BTC/USDT"}, {"text": "📊 ETH/USDT"}],
                [{"text": "📊 GOLD"}, {"text": "📊 EUR/USD"}],
                [{"text": "⚙️ STATUS"}, {"text": "🧪 DEBUG ALL"}]
            ],
            "resize_keyboard": True,
            "is_persistent": True
        }

        payload = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": main_keyboard
        }

        try:
            resp = requests.post(url, json=payload, timeout=10, proxies=proxies)
            if resp.status_code == 200:
                print(f"[Telegram Bot]: Message sent successfully to {chat_id}.")
                return True
            else:
                print(f"[Telegram Bot]: API Error ({resp.status_code}) for {chat_id}: {resp.text}")
                return False
        except Exception as e:
            print(f"[Telegram Bot]: Exception sending message to {chat_id}: {e}")
            return False

    def send_message_to_users(self, user_ids: list[str], text: str) -> bool:
        """
        Broadcasts formatted message to a list of active user chat_ids with rate limiting & load balancing.
        """
        import time
        if not user_ids:
            user_ids = self.chat_ids

        # Merge statically configured chat_ids and dynamic user_ids so NO ONE is missed
        all_recipients = list(set([str(cid).strip() for cid in (user_ids + self.chat_ids) if str(cid).strip()]))

        success = True
        for idx, cid in enumerate(all_recipients):
            res = self.send_message_to(str(cid), text)
            if not res:
                success = False
            # Rate limiting delay (0.05s between sends to stay well under Telegram 30 msg/sec limit)
            if idx < len(all_recipients) - 1:
                time.sleep(0.05)
        return success

    def send_message(self, text: str) -> bool:
        """
        Sends formatted message to all configured Telegram channels and registered active users.
        """
        from app import get_all_subscribed_users, is_user_active
        active_users = [cid for cid in get_all_subscribed_users() if is_user_active(cid)]
        
        # Merge active registered users with statically configured chat_ids
        target_ids = list(set(active_users + self.chat_ids))

        if not self.token or not target_ids:
            print(f"[Telegram Bot Mock Output - No API Key or Chat IDs Set]:\n{text}\n")
            return False

        return self.send_message_to_users(target_ids, text)
