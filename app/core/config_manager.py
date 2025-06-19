import os
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from app.utils.logger import logger
import aiofiles

# Configuration file path
CONFIG_DIR = "./config"
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

os.makedirs(CONFIG_DIR, exist_ok=True)


class ConfigManager:
    @staticmethod
    async def load_config() -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            if os.path.exists(CONFIG_FILE):
                async with aiofiles.open(CONFIG_FILE, "r") as f:
                    content = await f.read()
                    return json.loads(content)
            return {"accounts": []}
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {"accounts": []}

    @staticmethod
    async def save_config(config: Dict[str, Any]) -> bool:
        """Save configuration to JSON file"""
        try:
            async with aiofiles.open(CONFIG_FILE, "w") as f:
                await f.write(json.dumps(config, indent=2))
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

    @staticmethod
    async def add_account(account_data: Dict[str, Any]) -> str:
        """Add new account to configuration"""
        config = await ConfigManager.load_config()
        account_id = str(uuid.uuid4())
        account_data["id"] = account_id
        account_data["created_at"] = datetime.now().isoformat()
        config["accounts"].append(account_data)
        print(config)
        await ConfigManager.save_config(config)
        return account_id

    @staticmethod
    async def update_account(account_id: str, account_data: Dict[str, Any]) -> bool:
        """Update existing account in configuration"""
        config = await ConfigManager.load_config()
        for i, account in enumerate(config["accounts"]):
            if account["id"] == account_id:
                account_data["id"] = account_id
                account_data["updated_at"] = datetime.now().isoformat()
                config["accounts"][i] = account_data
                await ConfigManager.save_config(config)
                return True
        return False

    @staticmethod
    async def delete_account(account_id: str) -> bool:
        """Delete account from configuration"""
        config = await ConfigManager.load_config()
        original_count = len(config["accounts"])
        config["accounts"] = [
            acc for acc in config["accounts"] if acc["id"] != account_id
        ]
        if len(config["accounts"]) < original_count:
            await ConfigManager.save_config(config)
            return True
        return False

    @staticmethod
    async def get_account(account_id: str) -> Optional[Dict[str, Any]]:
        """Get specific account by ID"""
        config = await ConfigManager.load_config()
        for account in config["accounts"]:
            if account["id"] == account_id:
                return account
        return None
