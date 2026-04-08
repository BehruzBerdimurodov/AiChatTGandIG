"""
FastAPI - Instagram ManyChat webhook + Telegram Bot Integration
Instagram va Telegram dan kelgan xabarlarni birlashtiradi
"""

import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import Optional
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import Update

from app.ai_handler import (
    get_ai_response,
    active_users,
    send_order_to_admins,
    BOOKING_STORE,
)
from app.manychat import format_manychat_response
from config.database import (
    init_db,
    register_user,
    create_order,
    get_hotel,
    get_admins,
    log_activity,
    get_db,
    get_user_count,
    is_room_available,
)
from datetime import datetime
from bot.handlers import user as user_handlers, admin as admin_handlers

log = logging.getLogger(__name__)


def require_internal_token(x_internal_token: str | None):
    expected_token = os.getenv("INTERNAL_API_TOKEN")
    if not expected_token:
        log.error("INTERNAL_API_TOKEN is not configured")
        raise HTTPException(status_code=503, detail="Internal API is not configured")
    if x_internal_token != expected_token:
        raise HTTPException(status_code=401, detail="Unauthorized")


bot: Bot | None = None
dp: Dispatcher | None = None


def _build_dispatcher() -> Dispatcher:
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        storage = RedisStorage.from_url(redis_url)
        log.info("Redis orqali ulashilmoqda ✅")
    else:
        storage = MemoryStorage()
        log.info(
            "MemoryStorage orqali ulashilmoqda ⚠️ (Production uchun Redis tavsiya etiladi)"
        )

    dispatcher = Dispatcher(storage=storage)
    dispatcher.include_router(admin_handlers.router)
    dispatcher.include_router(user_handlers.router)
    return dispatcher


def _build_bot() -> Bot:
    return Bot(
        token=os.getenv("TELEGRAM_BOT_TOKEN"),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot, dp
    await init_db()
    log.info("✅ Database initialized")
    log.info("✅ FastAPI server Marco Polo Hotel Bot ishga tushdi")

    if os.getenv("TELEGRAM_BOT_TOKEN"):
        bot = _build_bot()
        dp = _build_dispatcher()

        railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
        webhook_url = os.getenv("WEBHOOK_URL")

        # Railway muhitida bo'lsak va RAILWAY_PUBLIC_DOMAIN berilgan bo'lsa uni ustun qo'yamiz
        if railway_domain:
            webhook_url = f"https://{railway_domain}"

        webhook_path = os.getenv("WEBHOOK_PATH", "/webhook/telegram")
        webhook_secret = os.getenv("WEBHOOK_SECRET")
        run_mode = os.getenv("RUN_MODE", "").lower()
        if webhook_url or run_mode == "webhook":
            full_url = webhook_url.rstrip("/") + webhook_path if webhook_url else None
            if full_url:
                await bot.set_webhook(full_url, secret_token=webhook_secret)
                log.info(f"Telegram webhook set: {full_url}")

    yield

    # Diqqat: Production (Railway/Render) muhitida o'chayotganda Webhook ni uzib ketish (delete_webhook) mumkin emas.
    # Aks holda u yangi ishga tushgan server webhook ini ham uzib yuboradi.
    if bot:
        try:
            await bot.session.close()
        except Exception:
            pass


app = FastAPI(
    title="Marco Polo Hotel Bot API",
    version="4.0.0",
    description="Telegram + Instagram Integration",
    lifespan=lifespan,
)


class ManyChatPayload(BaseModel):
    user_id: str
    first_name: Optional[str] = "Mehmon"
    message: str
    platform: Optional[str] = "instagram"


class MakePayload(BaseModel):
    user_id: str
    first_name: Optional[str] = "Mehmon"
    message: str


class ChatfuelPayload(BaseModel):
    chatfuel_user_id: str
    first_name: Optional[str] = "Mehmon"
    last_user_freeform_input: str


class InstagramDM(BaseModel):
    sender_id: str
    sender_name: Optional[str] = "Mehmon"
    message: str
    timestamp: Optional[str] = ""


async def _confirm_booking(user_id: str, platform: str) -> Optional[str]:
    if user_id not in BOOKING_STORE:
        return None

    booking_data = BOOKING_STORE[user_id]
    order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    booking_data["id"] = order_id
    booking_data["source"] = platform

    try:
        await create_order(booking_data)
        await log_activity(user_id, "booking_confirmed", f"Order: {order_id}")
        log.info(
            f"[{platform.upper()} BOOKING] Saved: {order_id} - {booking_data.get('room_name')}"
        )
        del BOOKING_STORE[user_id]

        admins = await get_admins()
        super_admin = os.getenv("SUPER_ADMIN_ID")
        if super_admin:
            admins.extend([x.strip() for x in super_admin.split(",")])

        unique_admins = list(dict.fromkeys(admins))

        if unique_admins:
            try:
                async with Bot(token=os.getenv("TELEGRAM_BOT_TOKEN")) as notify_bot:
                    price_fmt = f"{booking_data.get('total_price', 0):,}".replace(
                        ",", " "
                    )
                    notify_text = (
                        f"🔔 <b>{platform.upper()}DAN YANGI BRON!</b>\n\n"
                        f"════════════════════════\n"
                        f"🏨 Xona: <b>{booking_data.get('room_name')}</b>\n"
                        f"📅 {booking_data.get('check_in')} → {booking_data.get('check_out')}\n"
                        f"👥 {booking_data.get('guests')} kishi\n"
                        f"💰 <b>{price_fmt} so'm</b>\n\n"
                        f"👤 {booking_data.get('name')}\n"
                        f"📞 {booking_data.get('phone')}\n"
                        f"📱 Platform: {platform.title()}\n"
                        f"════════════════════════"
                    )
                    for admin_id in unique_admins:
                        try:
                            await notify_bot.send_message(int(admin_id), notify_text)
                        except Exception as e:
                            log.error(f"Admin notify error for {admin_id}: {e}")

                    group_id = os.getenv("ORDERS_GROUP_ID")
                    if group_id:
                        try:
                            await notify_bot.send_message(int(group_id), notify_text)
                        except Exception as e:
                            log.error(f"Group notify error: {e}")

                log.info(
                    f"[{platform.upper()}] Admin notified: {len(unique_admins)} admins"
                )
            except Exception as e:
                log.error(f"[{platform.upper()}] Admin notification error: {e}")

        price_fmt = f"{booking_data.get('total_price', 0):,}".replace(",", " ")
        reply = (
            f"✅ <b>Broningiz tasdiqlandi!</b>\n\n"
            f"🏨 Xona: {booking_data.get('room_name')}\n"
            f"📅 Kelish: {booking_data.get('check_in')}\n"
            f"📅 Ketish: {booking_data.get('check_out')}\n"
            f"👥 {booking_data.get('guests')} kishi\n"
            f"💰 Jami: {price_fmt} so'm\n\n"
            f"👤 {booking_data.get('name')}\n"
            f"📞 {booking_data.get('phone')}\n\n"
            f"Tez orada operator siz bilan bog'lanadi!"
        )
        return reply
    except Exception as e:
        log.error(f"[{platform.upper()} BOOKING] Save error: {e}")
        return "❌ Xatolik yuz berdi. Keyinroq qayta urinib ko'ring."


@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
):
    if not bot or not dp:
        return Response(status_code=503)

    webhook_secret = os.getenv("WEBHOOK_SECRET")
    if webhook_secret and x_telegram_bot_api_secret_token != webhook_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")

    update = Update.model_validate(await request.json())
    await dp.feed_update(bot, update)
    return Response(status_code=200)


@app.get("/")
async def root():
    return {
        "status": "ok",
        "bot": "Marco Polo Hotel 🏩",
        "version": "4.0.0",
        "active_users": active_users(),
    }


@app.get("/health")
async def health():
    checks = {
        "database": "ok",
        "telegram_token": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "openai_key": bool(os.getenv("OPENAI_API_KEY")),
        "instagram_verify_token": bool(os.getenv("INSTAGRAM_VERIFY_TOKEN")),
        "internal_api_token": bool(os.getenv("INTERNAL_API_TOKEN")),
    }

    try:
        async with get_db() as db:
            await db.execute("SELECT 1")
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    is_healthy = (
        checks["database"] == "ok"
        and checks["telegram_token"]
        and checks["openai_key"]
        and checks["instagram_verify_token"]
        and checks["internal_api_token"]
    )

    return {
        "status": "healthy" if is_healthy else "degraded",
        "bot": "Marco Polo Hotel",
        "active_users": active_users(),
        "checks": checks,
    }


@app.post("/webhook/manychat")
async def manychat_webhook(payload: ManyChatPayload):
    """Instagram ManyChat webhook"""
    user_id = f"ig_{payload.user_id}"
    message_raw = payload.message.strip()
    message = message_raw.lower()

    log.info(f"[Instagram] {payload.user_id}: {payload.message[:60]}")

    await register_user(
        user_id=user_id,
        user_type="instagram",
        first_name=payload.first_name or "Mehmon",
    )

    if user_id in BOOKING_STORE and message in [
        "tasdiqlayman",
        "tasdiq",
        "ha",
        "buyurtma tasdiqlayman",
        "bron tasdiqlayman",
    ]:
        reply = await _confirm_booking(user_id, "instagram")
        return format_manychat_response(reply or "")

    ai_response = await get_ai_response(
        user_id, message_raw, payload.first_name or "Mehmon", platform="instagram"
    )
    return format_manychat_response(ai_response)


@app.post("/webhook/chatfuel")
async def chatfuel_webhook(request: Request):
    payload = await request.json()
    chatfuel_user_id = payload.get("chatfuel_user_id") or payload.get("user_id")
    message_raw = (
        payload.get("last_user_freeform_input") or payload.get("message") or ""
    )
    first_name = payload.get("first_name") or "Mehmon"

    if not chatfuel_user_id or not message_raw:
        return JSONResponse(
            {"messages": [{"text": "Xatolik: user_id yoki message yo'q."}]}
        )

    user_id = f"ig_{chatfuel_user_id}"
    msg_lower = message_raw.strip().lower()

    await register_user(
        user_id=user_id,
        user_type="instagram",
        first_name=first_name,
    )

    if user_id in BOOKING_STORE and msg_lower in [
        "tasdiqlayman",
        "tasdiq",
        "ha",
        "buyurtma tasdiqlayman",
        "bron tasdiqlayman",
    ]:
        reply = await _confirm_booking(user_id, "instagram")
        return JSONResponse({"messages": [{"text": reply or ""}]})

    ai_response = await get_ai_response(
        user_id, message_raw, first_name, platform="instagram"
    )
    return JSONResponse({"messages": [{"text": ai_response}]})


@app.post("/webhook/instagram")
async def instagram_webhook(request: Request):
    """Instagram Direct API webhook"""
    try:
        body = await request.json()

        if body.get("object") == "instagram":
            for entry in body.get("entry", []):
                for messaging in entry.get("messaging", []):
                    sender_id = messaging.get("sender", {}).get("id")
                    message_text = messaging.get("message", {}).get("text", "")

                    if message_text and sender_id:
                        log.info(f"[Instagram DM] {sender_id}: {message_text[:60]}")

                        await register_user(
                            user_id=f"ig_{sender_id}",
                            user_type="instagram",
                            first_name="Instagram User",
                        )

                        reply = await get_ai_response(
                            user_id=f"ig_{sender_id}",
                            user_message=message_text,
                            user_name="Instagram foydalanuvchisi",
                            platform="instagram",
                        )

                        ig_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
                        if ig_token:
                            import httpx

                            url = f"https://graph.instagram.com/v18.0/me/messages?access_token={ig_token}"
                            payload = {
                                "recipient": {"id": sender_id},
                                "message": {"text": reply},
                            }
                            async with httpx.AsyncClient() as client:
                                await client.post(url, json=payload)
                            log.info(f"[Instagram Reply] Sent to {sender_id}")
                        else:
                            log.warning("INSTAGRAM_ACCESS_TOKEN not set!")

                        await log_activity(
                            f"ig_{sender_id}", "instagram_dm", message_text[:50]
                        )

        return {"status": "ok"}
    except Exception as e:
        log.error(f"Instagram webhook error: {e}")
        return {"status": "error"}


@app.get("/webhook/instagram/verify")
async def verify_instagram(request: Request):
    """Instagram webhook verification"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    verify_token = os.getenv("INSTAGRAM_VERIFY_TOKEN")

    if not verify_token:
        log.error("INSTAGRAM_VERIFY_TOKEN is not configured")
        raise HTTPException(
            status_code=503, detail="Instagram verification is not configured"
        )

    if mode == "subscribe" and token == verify_token:
        log.info("Instagram webhook verified successfully")
        return Response(content=challenge, media_type="text/plain")
    else:
        raise HTTPException(status_code=403, detail="Verification failed")


class OrderPayload(BaseModel):
    user_id: str
    room_id: str
    room_name: str
    check_in: str
    check_out: str
    guests: int
    total_price: int
    name: str
    phone: str
    notes: Optional[str] = ""


@app.post("/api/order/create")
async def create_order_api(
    order: OrderPayload, x_internal_token: str | None = Header(default=None)
):
    """Bron qilish API"""
    require_internal_token(x_internal_token)

    import uuid

    order_id = f"ORD-{uuid.uuid4().hex[:10].upper()}"

    order_data = {
        "id": order_id,
        "user_id": order.user_id,
        "room_id": order.room_id,
        "room_name": order.room_name,
        "check_in": order.check_in,
        "check_out": order.check_out,
        "guests": order.guests,
        "total_price": order.total_price,
        "name": order.name,
        "phone": order.phone,
        "notes": order.notes or "",
        "source": "api",
    }

    try:
        available = await is_room_available(
            order.room_id, order.check_in, order.check_out
        )
        if not available:
            raise HTTPException(
                status_code=409, detail="Room is not available for the selected dates"
            )

        await register_user(
            user_id=order.user_id,
            user_type="api",
            first_name=order.name,
            phone=order.phone,
        )
        await create_order(order_data)
        await log_activity(
            order.user_id, "api_order", f"Order {order_id} created via API"
        )
        return {"status": "success", "order_id": order_id}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Order creation error: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/stats")
async def get_stats(x_internal_token: str | None = Header(default=None)):
    """Statistika API"""
    require_internal_token(x_internal_token)
    from config.database import get_monthly_stats

    monthly = await get_monthly_stats()

    return {
        "total_users": await get_user_count(),
        "total_orders": monthly["total_orders"],
        "monthly_revenue": monthly["revenue"],
        "active_chats": active_users(),
    }


@app.post("/notify/admins")
async def notify_admins(
    request: Request, x_internal_token: str | None = Header(default=None)
):
    """Adminlarni xabardor qilish API"""
    require_internal_token(x_internal_token)

    try:
        body = await request.json()
        message = body.get("message", "")
        if not message.strip():
            raise HTTPException(status_code=400, detail="Message is required")

        admin_ids = await get_admins()
        super_admin = os.getenv("SUPER_ADMIN_ID")
        if super_admin:
            admin_ids.extend([x.strip() for x in super_admin.split(",")])

        unique_admin_ids = list(dict.fromkeys(admin_ids))

        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise HTTPException(
                status_code=503, detail="Telegram bot token is not configured"
            )

        sent = 0
        from aiogram import Bot as AiogramBot

        async with AiogramBot(token=bot_token) as notify_bot:
            for admin_id in unique_admin_ids:
                try:
                    await notify_bot.send_message(int(admin_id), message)
                    sent += 1
                except Exception as exc:
                    log.error(f"Admin notification error for {admin_id}: {exc}")

        return {
            "status": "ok",
            "admins_count": len(unique_admin_ids),
            "sent_count": sent,
            "message_preview": message[:50],
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        log.error(f"Notify admins error: {e}")
        return {"status": "error", "message": str(e)}
