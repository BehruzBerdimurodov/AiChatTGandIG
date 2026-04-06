"""
Foydalanuvchi handlerlari - Professional versiya
AI chat + Bron qilish + Barcha funksiyalar
"""

import logging
import json
import os
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InputMediaPhoto
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.ai_handler import get_ai_response, clear_history, get_booking_data, clear_booking_data
from bot.handlers.admin import ADMIN_IN_ADMIN_MODE
from app.subscription import check_subscription, subscription_keyboard
from config.database import (
    get_hotel, get_rooms, get_room, register_user, is_admin, log_activity, get_user, get_setting
)
from bot.keyboards.keyboards import main_kb, rooms_inline_kb, back_main_inline_kb

log = logging.getLogger(__name__)
router = Router()

booking_store = {}


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
    # unique while preserving order
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
        elif msg_type == "media_group":
            files = payload.get("files") or []
            caption = payload.get("caption") or ""
            media = []
            for i, file_id in enumerate(files):
                if i == 0 and caption:
                    media.append(InputMediaPhoto(media=file_id, caption=caption))
                else:
                    media.append(InputMediaPhoto(media=file_id))
            if media:
                await bot.send_media_group(chat_id, media)
                sent_any = True
        else:
            continue

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
        # Reset admin mode on /start to avoid getting stuck
        ADMIN_IN_ADMIN_MODE.discard(user_id)

    ok, missing = await check_subscription(bot, user.id)
    if not ok:
        await message.answer(
            """Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:""",
            reply_markup=subscription_keyboard(missing),
        )
        return

    existing = await get_user(user_id)
    has_phone = bool(existing and existing.get("phone"))
    has_name = bool(existing and (existing.get("first_name") or existing.get("last_name")))

    if not has_phone or not has_name:
        if has_name and not has_phone:
            await state.set_state(OnboardState.contact)
            kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Kontakt yuborish", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await message.answer("Telefon raqamingizni yuboring:", reply_markup=kb)
            return
        await state.set_state(OnboardState.name)
        await message.answer(
            """Assalomu alaykum! Iltimos, ism va familiyangizni yozing.
Masalan: Behruz Berdimurodov""",
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
        f"""Assalomu alaykum, {name}!

Marco Polo Hotel ga xush kelibsiz!

Manzil: Do'mbirobod Naqqoshlik 121A
Telefon: {hotel.get('phone', '+998773397171')}

Men sizga yordam berishga tayyorman.
Savol yoki so'rov yozing!""",
        reply_markup=main_kb(user.id)
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
        keyboard=[[KeyboardButton(text="Kontakt yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Telefon raqamingizni yuboring:", reply_markup=kb)


@router.message(OnboardState.contact)
async def onboard_contact(message: Message, state: FSMContext):
    if not message.contact or not message.contact.phone_number:
        await message.answer("Iltimos, pastdagi tugma orqali kontakt yuboring.")
        return

    data = await state.get_data()
    first_name = data.get("first_name") or (message.from_user.first_name or "Mehmon")
    last_name = data.get("last_name") or (message.from_user.last_name or "")

    phone = message.contact.phone_number.strip()
    if not phone.startswith("+"):
        phone = "+" + phone

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

    await send_start_message(message.bot, message.chat.id)

    await message.answer(
        f"""Rahmat! Ma'lumotlar saqlandi.

Manzil: {address}
Telefon: {phone_main}

Savol yoki so'rov yozing!""",
        reply_markup=main_kb(message.from_user.id)
    )


@router.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: CallbackQuery, bot: Bot):
    ok, missing = await check_subscription(bot, callback.from_user.id)
    if ok:
        await callback.message.delete()
        await callback.message.answer(
            "✅ <b>Tasdiqlandi!</b>\n\nMarco Polo Hotel 🏩 ga xush kelibsiz!",
            reply_markup=main_kb(callback.from_user.id),
        )
    else:
        await callback.answer("⚠️ Obuna tasdiqlanmadi!", show_alert=True)





@router.callback_query(F.data == "book_now")
async def book_now(callback: CallbackQuery):
    rooms = await get_rooms(only_active=True)
    
    buttons = []
    for room in rooms:
        buttons.append([InlineKeyboardButton(
            text=f"🛏️ {room['name']} - {format_price(room['price'])} so'm",
            callback_data=f"book_room_{room['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_main")])
    
    await callback.message.edit_text(
        "📋 <b>Bron qilish - Xonani tanlang:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("book_room_"))
async def book_select_room(callback: CallbackQuery):
    room_id = callback.data.replace("book_room_", "")
    room = await get_room(room_id)
    
    if not room:
        await callback.answer("❌ Xona topilmadi", show_alert=True)
        return
    
    user_id = str(callback.from_user.id)
    booking_store[user_id] = {
        'room_id': room_id,
        'room_name': room['name'],
        'room_price': room['price'],
        'step': 'checkin'
    }
    
    await callback.message.edit_text(
        f"✅ <b>{room['name']}</b> tanlandi!\n\n"
        f"💰 {format_price(room['price'])} so'm/kun\n\n"
        f"📅 <b>Kelish sanasini yuboring:</b>\n"
        f"Format: 2026-04-15",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Bekor", callback_data="cancel_booking")]
        ])
    )


@router.callback_query(F.data == "cancel_booking")
async def cancel_booking(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    if user_id in booking_store:
        del booking_store[user_id]
    clear_booking_data(f"tg_{user_id}")
    
    try:
        await callback.message.edit_text(
            "❌ Bron bekor qilindi.\n\nSavolingiz bormi? 😊",
            reply_markup=back_main_inline_kb()
        )
    except:
        await callback.message.answer(
            "❌ Bron bekor qilindi.\n\nSavolingiz bormi? 😊",
            reply_markup=main_kb(callback.from_user.id)
        )


@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    try:
        await callback.message.edit_text(
            "🏩 <b>Marco Polo Hotel</b>\n\nSavolingizni yozing! 😊",
            reply_markup=back_main_inline_kb()
        )
    except Exception:
        await callback.message.answer(
            "🏩 <b>Marco Polo Hotel</b>\n\nSavolingizni yozing! 😊",
            reply_markup=back_main_inline_kb()
        )


@router.callback_query(F.data.startswith("room_"))
async def room_detail(callback: CallbackQuery):
    room_id = callback.data.replace("room_", "")
    room = await get_room(room_id)
    if not room:
        await callback.answer("❌ Xona topilmadi")
        return
    
    hotel = await get_hotel()
    
    await callback.message.edit_text(
        f"<b>🛏️ {room['name']}</b>\n\n"
        f"💰 <b>{format_price(room['price'])} so'm/kun</b>\n"
        f"📋 {room['description']}\n"
        f"👥 {room['capacity']} kishi\n\n"
        f"📞 {hotel.get('phone', '+998773397171')}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Bron qilish", callback_data=f"book_room_{room_id}")],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_main")]
        ])
    )





@router.message(F.text)
async def handle_all_messages(message: Message, bot: Bot):
    """Barcha matnli xabarlar - AI ga jo'natiladi"""
    user = message.from_user
    user_id = str(user.id)
    text_lower = message.text.strip().lower()

    if message.chat.type != "private":
        return
    
    ok, missing = await check_subscription(bot, user.id)
    if not ok:
        await message.answer(
            "⚠️ <b>Botdan foydalanish uchun kanallarga obuna bo'ling:</b>",
            reply_markup=subscription_keyboard(missing),
        )
        return
    
    # Inline button orqali bron jarayoni (booking_store)
    if user_id in booking_store:

        step = booking_store[user_id]['step']
        text = message.text.strip()
        
        if step == 'checkin':
            if not validate_date(text):
                await message.answer("❌ Sana noto'g'ri! Format: YYYY-MM-DD")
                return
            booking_store[user_id]['check_in'] = text
            booking_store[user_id]['step'] = 'checkout'
            await message.answer("📅 Ketish sanasini yuboring (YYYY-MM-DD):")
            
        elif step == 'checkout':
            if not validate_date(text):
                await message.answer("❌ Sana noto'g'ri! Format: YYYY-MM-DD")
                return
            booking_store[user_id]['check_out'] = text
            booking_store[user_id]['step'] = 'guests'
            await message.answer("👥 Necha kishi? (raqam yuboring)")
            
        elif step == 'guests':
            try:
                guests = int(text)
                booking_store[user_id]['guests'] = guests
                booking_store[user_id]['step'] = 'name'
                await message.answer("👤 Ismingizni yuboring:")
            except:
                await message.answer("❌ Faqat raqam!")
                
        elif step == 'name':
            booking_store[user_id]['name'] = text
            booking_store[user_id]['step'] = 'phone'
            await message.answer("📞 Telefon raqamingizni yuboring:")
            
        elif step == 'phone':
            booking_store[user_id]['phone'] = text
            booking_store[user_id]['step'] = 'confirm'
            
            data = booking_store[user_id]
            
            try:
                check_in = datetime.strptime(data['check_in'], '%Y-%m-%d')
                check_out = datetime.strptime(data['check_out'], '%Y-%m-%d')
                days = (check_out - check_in).days
                if days <= 0:
                    await message.answer("❌ Ketish sanasi kelishdan keyin bo'lishi kerak!")
                    booking_store[user_id]['step'] = 'checkout'
                    return
                total_price = data['room_price'] * days
            except:
                await message.answer("❌ Sana xatosi!")
                return
            
            booking_store[user_id]['total_price'] = total_price
            booking_store[user_id]['days'] = days
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Bron qilish", callback_data="confirm_booking")],
                [InlineKeyboardButton(text="❌ Bekor", callback_data="cancel_booking")]
            ])
            
            await message.answer(
                f"📋 <b>Buyurtma tasdiqlash:</b>\n\n"
                f"🏨 Xona: <b>{data['room_name']}</b>\n"
                f"📅 {data['check_in']} - {data['check_out']}\n"
                f"📆 {days} kun\n"
                f"👥 {data['guests']} kishi\n"
                f"💰 <b>{format_price(total_price)} so'm</b>\n\n"
                f"👤 {data['name']}\n"
                f"📞 {data['phone']}",
                reply_markup=keyboard
            )
        return

    # ─── AI orqali javob ───────────────────────────────────────────────────
    ai_data = get_booking_data(f"tg_{user_id}")
    text_norm = message.text.strip().lower()

    CONFIRM_WORDS = {
        'tasdiqlayman', 'tasdiq', 'ha', 'buyurtma tasdiqlayman',
        'bron tasdiqlayman', 'tasdiql', 'confirm'
    }
    CANCEL_WORDS = {
        'bekor', "yo'q", 'yoq', 'cancel', 'bekor qilish', 'rad etaman'
    }

    # Bron tasdiqlash kutilmoqda va user Tasdiqlayman yozdi
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
        from config.database import create_order, get_admins
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
            reply_markup=main_kb(user.id)
        )
        return

    # Bron bekor qilish
    if ai_data and text_norm in CANCEL_WORDS:
        clear_booking_data(f"tg_{user_id}")
        if user_id in booking_store:
            del booking_store[user_id]
        await message.answer("❌ Bron bekor qilindi.", reply_markup=main_kb(user.id))
        return

    # Barcha boshqa xabarlar — AI ga yuborish
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    reply = await get_ai_response(
        user_id=f"tg_{user.id}",
        user_message=message.text,
        user_name=user.first_name or "Mehmon",
        platform="telegram"
    )

    # Agar bron tayyor bo'lsa eslatma qo'shmaymiz (AI allaqachon yozgan)
    if ai_data and "Broningiz qabul" not in reply:
        reminder = (
            f"\n\n──────────────────────\n"
            f"📋 <b>Eslatma:</b> Tasdiqlanmagan broningiz bor!\n"
            f"✅ <b>Tasdiqlayman</b> yoki ❌ <b>Bekor</b> deb yozing."
        )
        reply = reply + reminder

    if "Broningiz qabul qilindi" in reply or "Tasdiqlayman" in reply:
        await message.answer(reply)
    else:
        await message.answer(reply, reply_markup=main_kb(user.id))


@router.callback_query(F.data == "confirm_booking")
async def confirm_booking(callback: CallbackQuery, bot: Bot):
    user_id = str(callback.from_user.id)
    
    data = None
    source = 'telegram_ai'
    
    if user_id in booking_store:
        data = booking_store[user_id]
        del booking_store[user_id]
        source = 'telegram'
    else:
        ai_data = get_booking_data(f"tg_{user_id}")
        if ai_data:
            data = ai_data
            source = data.get('source', 'telegram_ai')
    
    if not data:
        await callback.answer("❌ Buyurtma topilmadi", show_alert=True)
        return
    
    from config.database import create_order, get_admins
    
    order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    order_data = {
        'id': order_id,
        'user_id': user_id,
        'room_id': data.get('room_id', 'unknown'),
        'room_name': data.get('room_name', 'Xona'),
        'check_in': data.get('check_in', ''),
        'check_out': data.get('check_out', ''),
        'guests': data.get('guests', 1),
        'total_price': data.get('total_price', 0),
        'name': data.get('name', ''),
        'phone': data.get('phone', ''),
        'notes': '',
        'source': source
    }
    
    try:
        await create_order(order_data)
        await log_activity(user_id, "booking_confirmed", f"Order: {order_id}")
        print(f"[CONFIRM] Order saved to DB: {order_id} - {data.get('room_name')} - {data.get('name')}")
    except Exception as e:
        log.error(f"Order error: {e}")
        print(f"[CONFIRM ERROR] {e}")
    
    clear_booking_data(f"tg_{user_id}")
    
    admins = await get_admins()
    super_admin = os.getenv("SUPER_ADMIN_ID", "")
    admin_ids = _collect_admin_ids(admins, super_admin)

    from app.ai_handler import send_order_to_admins
    if admin_ids:
        try:
            await send_order_to_admins(bot, order_data, admin_ids)
        except Exception as e:
            log.error(f"Admin notify error: {e}")
    
    await log_activity(user_id, "booking", f"Order {order_id}")
    
    hotel = await get_hotel()
    await callback.message.edit_text(
        f"✅ <b>Broningiz qabul qilindi!</b>\n\n"
        f"🏨 {data.get('room_name')}\n"
        f"📅 {data.get('check_in')} → {data.get('check_out')}\n"
        f"👥 {data.get('guests')} kishi\n"
        f"💰 <b>{format_price(data.get('total_price', 0))} so'm</b>\n\n"
        f"👤 {data.get('name')}\n"
        f"📞 {data.get('phone')}\n\n"
        f"⏳ Tez orada operator siz bilan bog'lanadi!\n\n"
        f"📞 {hotel.get('phone', '+998773397171')}",
        reply_markup=back_main_inline_kb()
    )
    await callback.answer("✅ Bron tasdiqlandi!")


def validate_date(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except:
        return False
