"""
Foydalanuvchi handlerlari - Tugmalarsiz 100% AI versiya
AI chat + Bron qilish faqat yozishma orqali
"""

import logging
import json
import os
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.ai_handler import get_ai_response, get_booking_data, clear_booking_data
from bot.handlers.admin import ADMIN_IN_ADMIN_MODE
from app.subscription import check_subscription
from config.database import (
    get_hotel, register_user, log_activity, get_user, get_setting, create_order, get_admins
)

log = logging.getLogger(__name__)
router = Router()


def _collect_admin_ids(db_admins: list[str], super_admin_env: str) -> list[int]:
    ids: list[int] = []
    for admin_id in db_admins:
        try:
            ids.append(int(str(admin_id).strip()))
        except Exception:
            continue
    if super_admin_env:
        for raw in super_admin_env.split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                ids.append(int(raw))
            except Exception:
                continue
    seen = set()
    unique_ids = []
    for aid in ids:
        if aid in seen:
            continue
        seen.add(aid)
        unique_ids.append(aid)
    return unique_ids


def format_price(price: int) -> str:
    return f"{price:,}".replace(",", " ")


async def send_start_message(bot: Bot, chat_id: int):
    raw = await get_setting("start_messages")
    if not raw:
        return False
    try:
        messages = json.loads(raw)
    except Exception:
        return False
    if not messages:
        return False

    sent_any = False
    for payload in messages:
        msg_type = payload.get("type")
        if msg_type == "text":
            await bot.send_message(chat_id, payload.get("text", ""))
            sent_any = True
        elif msg_type == "photo":
            await bot.send_photo(chat_id, payload.get("file_id"), caption=payload.get("caption", ""))
            sent_any = True
        elif msg_type == "video":
            await bot.send_video(chat_id, payload.get("file_id"), caption=payload.get("caption", ""))
            sent_any = True
        elif msg_type == "voice":
            await bot.send_voice(chat_id, payload.get("file_id"), caption=payload.get("caption", ""))
            sent_any = True
        elif msg_type == "document":
            await bot.send_document(chat_id, payload.get("file_id"), caption=payload.get("caption", ""))
            sent_any = True
        elif msg_type == "location":
            await bot.send_location(chat_id, payload.get("lat"), payload.get("lng"))
            sent_any = True
    return sent_any

class OnboardState(StatesGroup):
    name = State()
    contact = State()


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, state: FSMContext):
    user = message.from_user
    user_id = str(user.id)

    if message.chat.type != "private":
        return

    if user_id in ADMIN_IN_ADMIN_MODE:
        ADMIN_IN_ADMIN_MODE.discard(user_id)

    ok, missing = await check_subscription(bot, user.id)
    if not ok:
        text = "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>\n\n"
        for ch in missing:
            username = ch.get("username", "")
            title = ch.get("title", "Kanal")
            if username:
                url = f"https://t.me/{username.lstrip('@')}"
            else:
                url = "Yo'naltirilgan kanal"
            text += f"📢 {title}: {url}\n"
        text += "\nObuna bo'lgach, /start buyrug'ini qayta yuboring."
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
        return

    existing = await get_user(user_id)
    has_phone = bool(existing and existing.get("phone"))
    has_name = bool(existing and (existing.get("first_name") or existing.get("last_name")))

    if not has_phone or not has_name:
        if has_name and not has_phone:
            await state.set_state(OnboardState.contact)
            kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="📱 Kontakt yuborish", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await message.answer(
                f"Hurmatli {existing.get('first_name', '')}, botimizdan to'liq foydalanish uchun telefon raqamingizni yozib yuboring yuboring yoki pastdagi tugmani bosing:",
                reply_markup=kb
            )
            return
        await state.set_state(OnboardState.name)
        await message.answer(
            "Assalomu alaykum! Iltimos, ism va familiyangizni yozing.\nMasalan: Behruz Berdimurodov",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    await register_user(
        user_id=user_id,
        user_type='telegram',
        first_name=user.first_name or existing.get("first_name") or "Mehmon",
        last_name=user.last_name or existing.get("last_name") or "",
        username=user.username or existing.get("username") or ""
    )
    await log_activity(user_id, "start", f"/start")

    await send_start_message(bot, message.chat.id)

    hotel = await get_hotel()
    name = existing.get("first_name") or user.first_name or "Mehmon"

    await message.answer(
        f"Assalomu alaykum, {name}!\n\n"
        f"Marco Polo Hotel ga xush kelibsiz!\n\n"
        f"Manzil: Do'mbirobod Naqqoshlik 121A\n"
        f"Telefon: {hotel.get('phone', '+998773397171')}\n\n"
        f"Men sizga yordam berishga tayyorman.\n"
        f"Savol yoki so'rov yozing!",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(OnboardState.name)
async def onboard_name(message: Message, state: FSMContext):
    full_name = (message.text or "").strip()
    if not full_name:
        await message.answer("Ism va familiyangizni yozing.")
        return

    parts = full_name.split()
    first_name = parts[0]
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

    await register_user(
        user_id=str(message.from_user.id),
        user_type="telegram",
        first_name=first_name,
        last_name=last_name,
        username=message.from_user.username or "",
        phone=""
    )
    await state.update_data(first_name=first_name, last_name=last_name)
    await state.set_state(OnboardState.contact)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Kontakt yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Rahmat! Endi telefon raqamingizni yuboring yoki pastdagi tugmani bosing:", reply_markup=kb)


@router.message(OnboardState.contact)
async def onboard_contact(message: Message, state: FSMContext, bot: Bot):
    if message.contact and message.contact.phone_number:
        phone = message.contact.phone_number
    else:
        phone = (message.text or "").strip()
    
    if len(phone) < 7:
        await message.answer("Iltimos, to'g'ri telefon raqam yuboring.")
        return

    if not phone.startswith("+"):
        phone = "+" + phone

    data = await state.get_data()
    first_name = data.get("first_name") or (message.from_user.first_name or "Mehmon")
    last_name = data.get("last_name") or (message.from_user.last_name or "")

    await register_user(
        user_id=str(message.from_user.id),
        user_type="telegram",
        first_name=first_name,
        last_name=last_name,
        username=message.from_user.username or "",
        phone=phone
    )
    await log_activity(str(message.from_user.id), "onboard", "name_and_phone")

    await state.clear()
    hotel = await get_hotel()

    address = hotel.get("address", "Do'mbirobod Naqqoshlik 121A")
    phone_main = hotel.get("phone", "+998773397171")

    await send_start_message(bot, message.chat.id)

    await message.answer(
        f"Rahmat! Ma'lumotlar saqlandi.\n\n"
        f"Manzil: {address}\n"
        f"Telefon: {phone_main}\n\n"
        f"Savol yoki so'rov yozing!",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(F.text)
async def handle_all_messages(message: Message, bot: Bot):
    user = message.from_user
    user_id = str(user.id)
    text_norm = message.text.strip().lower()

    if message.chat.type != "private":
        return
    
    ok, missing = await check_subscription(bot, user.id)
    if not ok:
        text = "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>\n\n"
        for ch in missing:
            username = ch.get("username", "")
            title = ch.get("title", "Kanal")
            if username:
                url = f"https://t.me/{username.lstrip('@')}"
            else:
                url = "Yo'naltirilgan kanal"
            text += f"📢 {title}: {url}\n"
        text += "\nObuna bo'lgach, botga yozishingiz mumkin."
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
        return

    # ─── AI orqali javob (100%) ─────────────────────────────────────────────
    ai_data = get_booking_data(f"tg_{user_id}")

    CONFIRM_WORDS = {
        'tasdiqlayman', 'tasdiq', 'ha', 'buyurtma tasdiqlayman',
        'bron tasdiqlayman', 'tasdiql', 'confirm'
    }
    CANCEL_WORDS = {
        'bekor', "yo'q", 'yoq', 'cancel', 'bekor qilish', 'rad etaman'
    }

    # Tasdiqlash
    if ai_data and text_norm in CONFIRM_WORDS:
        order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        order_data = {
            'id': order_id,
            'user_id': user_id,
            'room_id': ai_data.get('room_id', 'unknown'),
            'room_name': ai_data.get('room_name', 'Xona'),
            'check_in': ai_data.get('check_in', ''),
            'check_out': ai_data.get('check_out', ''),
            'guests': ai_data.get('guests', 1),
            'total_price': ai_data.get('total_price', 0),
            'name': ai_data.get('name', ''),
            'phone': ai_data.get('phone', ''),
            'notes': '',
            'source': 'telegram'
        }
        try:
            await create_order(order_data)
            await log_activity(user_id, "booking_confirmed", f"Order: {order_id}")
        except Exception as e:
            log.error(f"Order error: {e}")

        admins = await get_admins()
        super_admin = os.getenv("SUPER_ADMIN_ID", "")
        admin_ids = _collect_admin_ids(admins, super_admin)
        from app.ai_handler import send_order_to_admins
        if admin_ids:
            try:
                await send_order_to_admins(bot, order_data, admin_ids)
            except Exception as e:
                log.error(f"Admin notify error: {e}")

        clear_booking_data(f"tg_{user_id}")
        await message.answer(
            f"✅ <b>Broningiz tasdiqlandi!</b>\n\n"
            f"🏨 {ai_data.get('room_name')}\n"
            f"📅 {ai_data.get('check_in')} → {ai_data.get('check_out')}\n"
            f"👥 {ai_data.get('guests')} kishi\n"
            f"💰 <b>{format_price(ai_data.get('total_price', 0))} so'm</b>\n\n"
            f"👤 {ai_data.get('name')}\n"
            f"📞 {ai_data.get('phone')}\n\n"
            f"⏳ Tez orada operator siz bilan bog'lanadi!",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    # Bekor qilish
    if ai_data and text_norm in CANCEL_WORDS:
        clear_booking_data(f"tg_{user_id}")
        await message.answer("❌ Bron bekor qilindi.", reply_markup=ReplyKeyboardRemove())
        return

    # Asosiy AI bilan so'zlashuv
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    reply = await get_ai_response(
        user_id=f"tg_{user.id}",
        user_message=message.text,
        user_name=user.first_name or "Mehmon",
        platform="telegram"
    )

    if ai_data and "Broningiz qabul" not in reply:
        reminder = (
            f"\n\n──────────────────────\n"
            f"📋 <b>Eslatma:</b> Tasdiqlanmagan broningiz bor!\n"
            f"✅ <b>Tasdiqlayman</b> yoki ❌ <b>Bekor</b> deb yozing."
        )
        reply = reply + reminder

    await message.answer(reply, reply_markup=ReplyKeyboardRemove())
