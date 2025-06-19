from typing import Dict, Any
from app.utils.logger import logger
import httpx


class WebhookManager:
    @staticmethod
    async def send_webhook(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send webhook to specified URL"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    logger.info(f"Webhook sent to {url}")

                return {
                    "success": response.status_code == 200,
                    "status_code": response.status_code,
                    "response": response.text[:500],  # Limit response text
                }
        except Exception as e:
            logger.error(f"Webhook send failed: {e}")
            return {"success": False, "error": str(e)}
