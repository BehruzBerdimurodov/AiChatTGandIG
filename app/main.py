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

from app.ai_handler import get_ai_response, active_users, send_order_to_admins, BOOKING_STORE
from app.manychat import format_manychat_response
from config.database import (
    init_db, register_user, create_order, get_hotel, get_admins, log_activity, get_db, get_user_count, is_room_available
)
from datetime import datetime

log = logging.getLogger(__name__)


def require_internal_token(x_internal_token: str | None):
    expected_token = os.getenv("INTERNAL_API_TOKEN")
    if not expected_token:
        log.error("INTERNAL_API_TOKEN is not configured")
        raise HTTPException(status_code=503, detail="Internal API is not configured")

    if x_internal_token != expected_token:
        raise HTTPException(status_code=401, detail="Unauthorized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    log.info("✅ Database initialized")
    log.info("✅ FastAPI server Marco Polo Hotel Bot ishga tushdi")
    yield


app = FastAPI(
    title="Marco Polo Hotel Bot API",
    version="4.0.0",
    description="Telegram + Instagram Integration",
    lifespan=lifespan
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


@app.get("/")
async def root():
    return {
        "status": "ok",
        "bot": "Marco Polo Hotel 🏩",
        "version": "4.0.0",
        "active_users": active_users()
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
    message = payload.message.strip().lower()
    
    log.info(f"[Instagram] {payload.user_id}: {payload.message[:60]}")
    
    await register_user(
        user_id=user_id,
        user_type="instagram",
        first_name=payload.first_name or "Mehmon"
    )
    
    if user_id in BOOKING_STORE and message in ['tasdiqlayman', 'tasdiq', 'ha', 'buyurtma tasdiqlayman', 'bron tasdiqlayman']:
        booking_data = BOOKING_STORE[user_id]
        order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        booking_data['id'] = order_id
        booking_data['source'] = 'instagram'
        
        try:
            await create_order(booking_data)
            await log_activity(user_id, "booking_confirmed", f"Order: {order_id}")
            log.info(f"[INSTAGRAM BOOKING] Saved: {order_id} - {booking_data.get('room_name')}")
            del BOOKING_STORE[user_id]
            
            from app.ai_handler import send_order_to_admins
            admins = await get_admins()
            super_admin = os.getenv("SUPER_ADMIN_ID")
            if super_admin:
                admins.extend([x.strip() for x in super_admin.split(',')])
            
            if admins:
                try:
                    from aiogram import Bot
                    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
                    for admin_id in admins:
                        await bot.send_message(
                            int(admin_id),
                            f"""🔔 <b>INSTAGRAMDAN YANGI BRON!</b>

━━━━━━━━━━━━━━━━━━━━━━━━
🏨 Xona: <b>{booking_data.get('room_name')}</b>
📅 {booking_data.get('check_in')} → {booking_data.get('check_out')}
👥 {booking_data.get('guests')} kishi
💰 <b>{booking_data.get('total_price'):,} so'm</b>

👤 {booking_data.get('name')}
📞 {booking_data.get('phone')}
📱 Platform: Instagram
━━━━━━━━━━━━━━━━━━━━━━━━"""
                        )
                    log.info(f"[INSTAGRAM] Admin notified: {len(admins)} admins")
                except Exception as e:
                    log.error(f"[INSTAGRAM] Admin notification error: {e}")
            
            reply = f"""✅ <b>Broningiz tasdiqlandi!</b>

🏨 Xona: {booking_data.get('room_name')}
📅 Kelish: {booking_data.get('check_in')}
📅 Ketish: {booking_data.get('check_out')}
👥 {booking_data.get('guests')} kishi
💰 Jami: {booking_data.get('total_price'):,} so'm

👤 {booking_data.get('name')}
📞 {booking_data.get('phone')}

Tez orada operator siz bilan bog'lanadi!"""
        except Exception as e:
            log.error(f"[INSTAGRAM BOOKING ERROR] {e}")
            reply = "❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring."
    elif user_id in BOOKING_STORE and message in ['bekor', 'yoq', 'cancel']:
        del BOOKING_STORE[user_id]
        reply = "❌ Bron bekor qilindi."
    else:
        reply = await get_ai_response(
            user_id=user_id,
            user_message=payload.message,
            user_name=payload.first_name or "Mehmon",
            platform="instagram"
        )
    
    await log_activity(user_id, "instagram_dm", payload.message[:50])
    
    return JSONResponse(content=format_manychat_response(reply))


@app.post("/webhook/make")
async def make_webhook(payload: MakePayload):
    """Make.com (Integromat) webhook"""
    user_id = f"ig_make_{payload.user_id}"
    message = payload.message.strip().lower()
    
    log.info(f"[Make.com Instagram] {payload.user_id}: {payload.message[:60]}")
    
    await register_user(
        user_id=user_id,
        user_type="instagram",
        first_name=payload.first_name or "Mehmon"
    )
    
    if user_id in BOOKING_STORE and message in ['tasdiqlayman', 'tasdiq', 'ha', 'buyurtma tasdiqlayman', 'bron tasdiqlayman']:
        booking_data = BOOKING_STORE[user_id]
        order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        booking_data['id'] = order_id
        booking_data['source'] = 'instagram'
        
        try:
            await create_order(booking_data)
            await log_activity(user_id, "booking_confirmed", f"Order: {order_id}")
            del BOOKING_STORE[user_id]
            
            from app.ai_handler import send_order_to_admins
            admins = await get_admins()
            super_admin = os.getenv("SUPER_ADMIN_ID")
            if super_admin:
                admins.extend([x.strip() for x in super_admin.split(',')])
            
            if admins:
                try:
                    from aiogram import Bot
                    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
                    for admin_id in admins:
                        await bot.send_message(
                            int(admin_id),
                            f"""🔔 <b>INSTAGRAMDAN (MAKE) YANGI BRON!</b>\n\n🏨 Xona: <b>{booking_data.get('room_name')}</b>\n📅 {booking_data.get('check_in')} → {booking_data.get('check_out')}\n💰 <b>{booking_data.get('total_price'):,} so'm</b>\n👤 {booking_data.get('name')}\n📞 {booking_data.get('phone')}"""
                        )
                except Exception as e:
                    log.error(f"[MAKE] Admin notification error: {e}")
            
            reply = f"✅ Broningiz tasdiqlandi!\n🏨 Xona: {booking_data.get('room_name')}\n📅 Kelish: {booking_data.get('check_in')}\n📅 Ketish: {booking_data.get('check_out')}\n💰 Jami: {booking_data.get('total_price'):,} so'm\n\nTez orada aloqaga chiqamiz!"
        except Exception as e:
            log.error(f"[MAKE BOOKING ERROR] {e}")
            reply = "❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring."
    elif user_id in BOOKING_STORE and message in ['bekor', 'yoq', 'cancel']:
        del BOOKING_STORE[user_id]
        reply = "❌ Bron bekor qilindi."
    else:
        reply = await get_ai_response(
            user_id=user_id,
            user_message=payload.message,
            user_name=payload.first_name or "Mehmon",
            platform="instagram"
        )
    
    await log_activity(user_id, "make_dm", payload.message[:50])
    return {"reply": reply}

@app.post("/webhook/chatfuel")
async def chatfuel_webhook(payload: ChatfuelPayload):
    """Chatfuel JSON API webhook"""
    user_id = f"ig_cf_{payload.chatfuel_user_id}"
    message = payload.last_user_freeform_input.strip().lower()
    
    log.info(f"[Chatfuel Instagram] {payload.chatfuel_user_id}: {payload.last_user_freeform_input[:60]}")
    
    await register_user(
        user_id=user_id,
        user_type="instagram",
        first_name=payload.first_name or "Mehmon"
    )
    
    if user_id in BOOKING_STORE and message in ['tasdiqlayman', 'tasdiq', 'ha', 'buyurtma tasdiqlayman', 'bron tasdiqlayman']:
        booking_data = BOOKING_STORE[user_id]
        order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        booking_data['id'] = order_id
        booking_data['source'] = 'instagram'
        
        try:
            await create_order(booking_data)
            await log_activity(user_id, "booking_confirmed", f"Order: {order_id}")
            del BOOKING_STORE[user_id]
            
            from app.ai_handler import send_order_to_admins
            admins = await get_admins()
            super_admin = os.getenv("SUPER_ADMIN_ID")
            if super_admin:
                admins.extend([x.strip() for x in super_admin.split(',')])
            
            if admins:
                try:
                    from aiogram import Bot
                    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
                    for admin_id in admins:
                        await bot.send_message(
                            int(admin_id),
                            f"""🔔 <b>INSTAGRAMDAN (CHATFUEL) YANGI BRON!</b>\n\n🏨 Xona: <b>{booking_data.get('room_name')}</b>\n📅 {booking_data.get('check_in')} → {booking_data.get('check_out')}\n💰 <b>{booking_data.get('total_price'):,} so'm</b>\n👤 {booking_data.get('name')}\n📞 {booking_data.get('phone')}"""
                        )
                except Exception as e:
                    log.error(f"[CHATFUEL] Admin notification error: {e}")
            
            reply = f"✅ Broningiz tasdiqlandi!\n🏨 Xona: {booking_data.get('room_name')}\n📅 Kelish: {booking_data.get('check_in')}\n📅 Ketish: {booking_data.get('check_out')}\n💰 Jami: {booking_data.get('total_price'):,} so'm\n\nTez orada aloqaga chiqamiz!"
        except Exception as e:
            log.error(f"[CHATFUEL BOOKING ERROR] {e}")
            reply = "❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring."
    elif user_id in BOOKING_STORE and message in ['bekor', 'yoq', 'cancel']:
        del BOOKING_STORE[user_id]
        reply = "❌ Bron bekor qilindi."
    else:
        reply = await get_ai_response(
            user_id=user_id,
            user_message=payload.last_user_freeform_input,
            user_name=payload.first_name or "Mehmon",
            platform="instagram"
        )
    
    await log_activity(user_id, "chatfuel_dm", payload.last_user_freeform_input[:50])
    
    # Chatfuel kutilgan maxsus JSON format:
    return JSONResponse(content={
        "messages": [
            {"text": reply}
        ]
    })


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
                            first_name="Instagram User"
                        )
                        
                        reply = await get_ai_response(
                            user_id=f"ig_{sender_id}",
                            user_message=message_text,
                            user_name="Instagram foydalanuvchisi",
                            platform="instagram"
                        )
                        
                        # Send reply back to Instagram
                        ig_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
                        if ig_token:
                            import httpx
                            url = f"https://graph.instagram.com/v18.0/me/messages?access_token={ig_token}"
                            payload = {
                                "recipient": {"id": sender_id},
                                "message": {"text": reply}
                            }
                            async with httpx.AsyncClient() as client:
                                await client.post(url, json=payload)
                            log.info(f"[Instagram Reply] Sent to {sender_id}")
                        else:
                            log.warning("INSTAGRAM_ACCESS_TOKEN not set!")
                            
                        await log_activity(f"ig_{sender_id}", "instagram_dm", message_text[:50])
                        
        return {"status": "ok"}
    except Exception as e:
        log.error(f"Instagram webhook error: {e}")
        return {"status": "error"}


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request, bot_token: str = None):
    """Telegram bot uchun webhook endpoint"""
    if not bot_token or bot_token != os.getenv("TELEGRAM_BOT_TOKEN"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        body = await request.json()
        log.info(f"[Telegram Webhook] Update received: {body.get('update_id', 'N/A')}")
        return {"status": "ok"}
    except Exception as e:
        log.error(f"Telegram webhook error: {e}")
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
        raise HTTPException(status_code=503, detail="Instagram verification is not configured")
    
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
async def create_order_api(order: OrderPayload, x_internal_token: str | None = Header(default=None)):
    """Bron qilish API"""
    require_internal_token(x_internal_token)

    import uuid
    order_id = f"ORD-{uuid.uuid4().hex[:10].upper()}"
    
    order_data = {
        'id': order_id,
        'user_id': order.user_id,
        'room_id': order.room_id,
        'room_name': order.room_name,
        'check_in': order.check_in,
        'check_out': order.check_out,
        'guests': order.guests,
        'total_price': order.total_price,
        'name': order.name,
        'phone': order.phone,
        'notes': order.notes or '',
        'source': 'api'
    }
    
    try:
        available = await is_room_available(order.room_id, order.check_in, order.check_out)
        if not available:
            raise HTTPException(status_code=409, detail="Room is not available for the selected dates")

        await register_user(
            user_id=order.user_id,
            user_type="api",
            first_name=order.name,
            phone=order.phone,
        )
        await create_order(order_data)
        await log_activity(order.user_id, "api_order", f"Order {order_id} created via API")
        return {"status": "success", "order_id": order_id}
    except Exception as e:
        log.error(f"Order creation error: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/stats")
async def get_stats():
    """Statistika API"""
    from config.database import get_monthly_stats
    
    monthly = await get_monthly_stats()
    
    return {
        "total_users": await get_user_count(),
        "total_orders": monthly['total_orders'],
        "monthly_revenue": monthly['revenue'],
        "active_chats": active_users()
    }


@app.post("/notify/admins")
async def notify_admins(request: Request, x_internal_token: str | None = Header(default=None)):
    """Adminlarni xabardor qilish API"""
    from config.database import get_admins

    require_internal_token(x_internal_token)

    try:
        body = await request.json()
        message = body.get("message", "")
        if not message.strip():
            raise HTTPException(status_code=400, detail="Message is required")
        admin_ids = await get_admins()
        super_admin = os.getenv("SUPER_ADMIN_ID")
        if super_admin:
            admin_ids.extend([x.strip() for x in super_admin.split(',')])

        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise HTTPException(status_code=503, detail="Telegram bot token is not configured")

        sent = 0
        from aiogram import Bot

        bot = Bot(token=bot_token)
        for admin_id in dict.fromkeys(admin_ids):
            try:
                await bot.send_message(int(admin_id), message)
                sent += 1
            except Exception as exc:
                log.error(f"Admin notification error for {admin_id}: {exc}")

        return {
            "status": "ok",
            "admins_count": len(admin_ids),
            "sent_count": sent,
            "message_preview": message[:50]
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        log.error(f"Notify admins error: {e}")
        return {"status": "error", "message": str(e)}
