import os
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from app.routes import index
from app.routes import account
from app.core.config_manager import ConfigManager
from app.core.telegram_manager import TelegramManager
from app.utils.logger import logger

app = FastAPI(title="Telegram Management System", version="1.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
# Add session middleware
app.add_middleware(
    SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "your-secret-key-here")
)


app.include_router(index.router, tags=["index"])
app.include_router(account.router, tags=["account"])


# @app.on_event("shutdown")
# async def shutdown_event():
#     config = await ConfigManager.load_config()
#     for account in config["accounts"]:
#         try:
#             await TelegramManager.close_client(account["api_id"], account["phone"])
#         except Exception as e:
#             logger.error(f"Error during shutdown disconnect: {e}")
