import uuid
from datetime import datetime
from fastapi import Request, Form, HTTPException, Depends, APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.core.config_manager import ConfigManager
from app.core.telegram_manager import TelegramManager
from app.core.webhook_manager import WebhookManager
from app.routes.auth import get_current_user
from app.utils.logger import logger

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, current_user: str = Depends(get_current_user)):
    config = await ConfigManager.load_config()

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "accounts": config["accounts"], "user": current_user},
    )


@router.get("/account/add", response_class=HTMLResponse)
async def add_account_page(
    request: Request, current_user: str = Depends(get_current_user)
):
    # logger.info(f"add_account_page{await request.body()}, {current_user}")
    return templates.TemplateResponse("add_account.html", {"request": request})


@router.post("/account/add")
async def add_account(
    request: Request,
    name: str = Form(...),
    phone: str = Form(...),
    api_id: str = Form(...),
    api_hash: str = Form(...),
    current_user: str = Depends(get_current_user),
):
    # Send verification code
    result = await TelegramManager.send_code(api_id, api_hash, phone)
    if result["success"]:
        # Store temporary data in session
        request.session["temp_account"] = {
            "name": name,
            "phone": phone,
            "api_id": api_id,
            "api_hash": api_hash,
            "phone_code_hash": result["phone_code_hash"],
        }
        return templates.TemplateResponse(
            "verify_code.html",
            {"request": request, "phone": phone, "message": result["message"]},
        )
    else:
        return templates.TemplateResponse(
            "add_account.html", {"request": request, "error": result["error"]}
        )


@router.post("/account/verify")
async def verify_account(
    request: Request,
    code: str = Form(...),
    current_user: str = Depends(get_current_user),
):
    temp_account = request.session.get("temp_account")
    if not temp_account:
        return RedirectResponse(url="/account/add", status_code=302)

    result = await TelegramManager.verify_code(
        temp_account["api_id"],
        temp_account["api_hash"],
        temp_account["phone"],
        code,
        temp_account["phone_code_hash"],
    )

    if result["success"]:
        # Save account to config
        account_data = {
            "name": temp_account["name"],
            "phone": temp_account["phone"],
            "api_id": temp_account["api_id"],
            "api_hash": temp_account["api_hash"],
            "session_string": result["session_string"],
            "user_info": result["user_info"],
            "webhooks": {"test": "", "production": ""},
            "events": [],
        }

        await ConfigManager.add_account(account_data)
        request.session.pop("temp_account", None)

        return RedirectResponse(url="/dashboard", status_code=302)
    else:
        return templates.TemplateResponse(
            "verify_code.html",
            {
                "request": request,
                "phone": temp_account["phone"],
                "error": result["error"],
            },
        )


@router.get("/account/{account_id}/edit", response_class=HTMLResponse)
async def edit_account_page(
    request: Request, account_id: str, current_user: str = Depends(get_current_user)
):
    account = await ConfigManager.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    return templates.TemplateResponse(
        "edit_account.html", {"request": request, "account": account}
    )


@router.post("/account/{account_id}/edit")
async def edit_account(
    request: Request,
    account_id: str,
    name: str = Form(...),
    webhook_test: str = Form(""),
    webhook_production: str = Form(""),
    current_user: str = Depends(get_current_user),
):
    account = await ConfigManager.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account["name"] = name
    account["webhooks"]["test"] = webhook_test
    account["webhooks"]["production"] = webhook_production

    success = await ConfigManager.update_account(account_id, account)
    if success:
        return RedirectResponse(url="/dashboard", status_code=302)
    else:
        return templates.TemplateResponse(
            "edit_account.html",
            {
                "request": request,
                "account": account,
                "error": "Failed to update account",
            },
        )


@router.post("/account/{account_id}/delete")
async def delete_account(
    account_id: str, current_user: str = Depends(get_current_user)
):
    # 1. Cek akun dulu → ambil semua data yang diperlukan sebelum mulai operasi
    config = await ConfigManager.load_config()
    account = next((acc for acc in config["accounts"] if acc["id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # 2. Simpan snapshot config sebelum dihapus → untuk rollback jika gagal hapus session
    original_config = config.copy()

    try:
        success_config = await ConfigManager.delete_account(account_id)
        if not success_config:
            raise Exception("Failed to delete account config")

        success_session = await TelegramManager.delete_session(
            account["api_id"], account["phone"]
        )
        if not success_session:
            # Rollback config → akun dikembalikan
            await ConfigManager.save_config(original_config)
            raise Exception("Failed to delete session file")

        return RedirectResponse(url="/dashboard", status_code=302)

    except Exception as e:
        logger.error(f"Delete account failed: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")


@router.get("/account/{account_id}/events", response_class=HTMLResponse)
async def account_events(
    request: Request, account_id: str, current_user: str = Depends(get_current_user)
):
    account = await ConfigManager.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    return templates.TemplateResponse(
        "events.html", {"request": request, "account": account}
    )


@router.post("/account/{account_id}/events/add")
async def add_event(
    request: Request,
    account_id: str,
    event_type: str = Form(...),
    targets: str = Form(...),
    current_user: str = Depends(get_current_user),
):
    account = await ConfigManager.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Parse targets (comma-separated)
    target_list = [target.strip() for target in targets.split(",") if target.strip()]

    event_data = {
        "id": str(uuid.uuid4()),
        "event_type": event_type,
        "targets": target_list,
        "created_at": datetime.now().isoformat(),
    }

    account["events"].append(event_data)
    await ConfigManager.update_account(account_id, account)

    return RedirectResponse(url=f"/account/{account_id}/events", status_code=302)


@router.post("/account/{account_id}/events/{event_id}/delete")
async def delete_event(
    account_id: str, event_id: str, current_user: str = Depends(get_current_user)
):
    account = await ConfigManager.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account["events"] = [
        event for event in account["events"] if event["id"] != event_id
    ]
    await ConfigManager.update_account(account_id, account)

    return RedirectResponse(url=f"/account/{account_id}/events", status_code=302)


@router.post("/webhook/test")
async def test_webhook(
    webhook_url: str = Form(...), current_user: str = Depends(get_current_user)
):
    test_payload = {
        "event_type": "test",
        "timestamp": datetime.now().isoformat(),
        "data": {"message": "This is a test webhook", "test": True},
    }

    result = await WebhookManager.send_webhook(webhook_url, test_payload)
    return JSONResponse(content=result)


# API Endpoints for AJAX requests
@router.get("/api/accounts")
async def api_get_accounts(current_user: str = Depends(get_current_user)):
    config = await ConfigManager.load_config()
    return {"accounts": config["accounts"]}


@router.get("/account/{account_id}/status")
async def api_account_status(
    account_id: str, current_user: str = Depends(get_current_user)
):
    config = await ConfigManager.load_config()
    account = next((acc for acc in config["accounts"] if acc["id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    connected = await TelegramManager.refresh(account)
    account["connected"] = True
    await ConfigManager.save_config(config)
    return RedirectResponse("/dashboard", status_code=303)


@router.post("/account/{account_id}/connect")
async def connect_account(account_id: str):
    config = await ConfigManager.load_config()
    account = next((acc for acc in config["accounts"] if acc["id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")

    await TelegramManager.start_event_listener(account)
    account["connected"] = True
    await ConfigManager.save_config(config)
    return RedirectResponse("/dashboard", status_code=303)


@router.post("/account/{account_id}/disconnect")
async def disconnect_account(account_id: str):
    config = await ConfigManager.load_config()
    account = next((acc for acc in config["accounts"] if acc["id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")

    await TelegramManager.close_client(
        account["api_id"], account["api_hash"], account["phone"]
    )
    # await TelegramManager.close_client(account["api_id"], account["phone"])
    account["connected"] = False
    await ConfigManager.save_config(config)
    return RedirectResponse("/dashboard", status_code=303)
