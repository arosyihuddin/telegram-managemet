import os
import datetime
from typing import Dict, Any
from app.utils.logger import logger
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired
from pyrogram import filters
from pyrogram.types.messages_and_media.message import Message
from itertools import chain
from app.core.webhook_manager import WebhookManager
from app.utils.serialize_message import serialize_message


class TelegramManager:
    clients: Dict[str, Client] = {}

    @staticmethod
    async def get_client(
        api_id: str, api_hash: str, phone: str, session_string: str = None
    ) -> Client:
        key = f"{api_id}:{phone}"

        if key not in TelegramManager.clients:
            if session_string:
                client = Client(
                    name=key,  # atau bisa None kalau mau, bebas
                    api_id=int(api_id),
                    api_hash=api_hash,
                    session_string=session_string,
                )
            else:
                SESSIONS_DIR = os.path.join(os.getcwd(), "sessions")
                os.makedirs(SESSIONS_DIR, exist_ok=True)
                session_file = os.path.join(SESSIONS_DIR, key)
                client = Client(
                    name=session_file,
                    api_id=int(api_id),
                    api_hash=api_hash,
                )

            await client.start()
            TelegramManager.clients[key] = client

        else:
            client = TelegramManager.clients[key]
            if not client.is_connected:
                await client.start()

        return TelegramManager.clients[key]

    @staticmethod
    async def close_client(api_id: str, phone: str):
        key = f"{api_id}:{phone}"
        client = TelegramManager.clients.pop(key, None)
        if client:
            await client.stop()

    @staticmethod
    async def send_code(api_id: str, api_hash: str, phone: str) -> Dict[str, Any]:
        """Send verification code to phone number"""
        try:
            client = await TelegramManager.get_client(api_id, api_hash, phone)
            sent_code = await client.send_code(phone)
            return {
                "success": True,
                "phone_code_hash": sent_code.phone_code_hash,
                "message": f"Kode verifikasi telah dikirim ke {phone}",
            }
        except Exception as e:
            logger.error(f"Error sending code: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def verify_code(
        api_id: str, api_hash: str, phone: str, code: str, phone_code_hash: str
    ) -> Dict[str, Any]:
        """Verify phone code and get session string"""
        try:
            client = await TelegramManager.get_client(api_id, api_hash, phone)

            try:
                await client.sign_in(phone, phone_code_hash, code)
            except SessionPasswordNeeded:
                await TelegramManager.close_client(api_id, phone)
                return {
                    "success": False,
                    "error": "2FA password required",
                    "requires_2fa": True,
                }

            session_string = await client.export_session_string()
            user = await client.get_me()

            return {
                "success": True,
                "session_string": session_string,
                "user_info": {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "username": user.username,
                },
            }
        except (PhoneCodeInvalid, PhoneCodeExpired) as e:
            return {
                "success": False,
                "error": "Kode verifikasi tidak valid atau sudah kadaluarsa",
            }
        except Exception as e:
            logger.error(f"Error verifying code: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def test_connection(account: Dict[str, Any]) -> bool:
        """Test Telegram account connection"""
        try:
            await TelegramManager.start_event_listener(account)
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    @staticmethod
    async def start_event_listener(account: Dict[str, Any]):
        try:
            client = await TelegramManager.get_client(
                account["api_id"],
                account["api_hash"],
                account["phone"],
                account.get("session_string"),
            )

            # Gabungkan semua targets dari semua event
            all_targets = list(
                chain.from_iterable(
                    event.get("targets", []) for event in account.get("events", [])
                )
            )

            # Kalau tidak ada target sama sekali, jangan buat handler
            if not all_targets:
                logger.warning(
                    f"Tidak ada targets untuk akun {account['name']}, handler tidak dibuat."
                )
                return

            logger.debug(f"Targets: {all_targets}")

            @client.on_message(filters.chat(all_targets))
            async def handle_new_message(client, message: Message):
                logger.info(f"Received message: {message.text}")

                # Loop semua event yang ada
                for event in account.get("events", []):
                    if event["event_type"] == "new_message":
                        payload = serialize_message(message)
                        # Kirim ke webhook sesuai environment (test atau production)
                        for webhook_url in account["webhooks"].values():
                            if webhook_url:
                                await WebhookManager.send_webhook(webhook_url, payload)

        except Exception as e:
            logger.error(f"Error starting event listener: {e}")
