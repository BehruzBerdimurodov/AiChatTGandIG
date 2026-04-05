"""
Admin Panel Handler - /admin orqali kirish
"""

import logging
import json
import json
import os
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.ai_handler import generate_post, active_users
from config.database import is_admin
from config.database import (
    is_admin, get_rooms, get_room, add_room, update_room, delete_room,
    get_hotel, update_hotel, get_channels, add_channel as db_add_channel, remove_channel,
    get_post_channel, set_post_channel, add_admin as db_add_admin, remove_admin as db_remove_admin, get_admins,
    get_user_count, get_orders, get_order, update_order, get_all_users,
    get_daily_stats, get_monthly_stats, log_activity, find_available_rooms, set_setting
)
from bot.keyboards.keyboards import admin_main_kb

log = logging.getLogger(__name__)
router = Router()


def format_price(price: int) -> str:
    return f"{price:,}".replace(",", " ")


class AdminInput(StatesGroup):
    waiting = State()


class BroadcastState(StatesGroup):
    message = State()


class RoomEditState(StatesGroup):
    waiting = State()


class HotelEditState(StatesGroup):
    waiting = State()


class ChannelState(StatesGroup):
    waiting = State()


class AdminManageState(StatesGroup):
    waiting = State()


class PostState(StatesGroup):
    waiting = State()


class AvailabilityState(StatesGroup):
    waiting = State()


class StartMessageState(StatesGroup):
    waiting = State()


ADMIN_IN_ADMIN_MODE = set()


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not await is_admin(user_id, os.getenv("SUPER_ADMIN_ID")):
        return
    
    ADMIN_IN_ADMIN_MODE.add(user_id)
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="stats_refresh")],
        [InlineKeyboardButton(text="🏠 Xonalar", callback_data="admin_rooms_list"),
         InlineKeyboardButton(text="🏨 Mehmonxona", callback_data="hotel_info")],
        [InlineKeyboardButton(text="📢 Kanallar", callback_data="channels_manage"),
         InlineKeyboardButton(text="📝 Post", callback_data="post_create")],
        [InlineKeyboardButton(text="🟢 Bo'sh xonalar", callback_data="available_rooms")],
        [InlineKeyboardButton(text="✉️ Start xabar", callback_data="start_message")],
        [InlineKeyboardButton(text="👥 Adminlar", callback_data="admins_list")],
        [InlineKeyboardButton(text="🚪 Chiqish", callback_data="admin_logout")],
    ])
    
    await message.answer(
        "⚙️ <b>Admin Panel - Marco Polo Hotel</b>\n\n"
        "Xush kelibsiz, Admin!",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "admin_logout")
async def admin_logout(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    ADMIN_IN_ADMIN_MODE.discard(user_id)
    await state.clear()
    
    await callback.message.edit_text(
        "✅ Admin rejmidan chiqdingiz!\n\n"
        "Bot asosiy holatga qaytdi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Asosiy menyu", callback_data="back_main")]
        ])
    )


@router.callback_query(F.data == "stats_refresh")
async def show_stats(callback: CallbackQuery):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    rooms = await get_rooms()
    active_rooms = sum(1 for r in rooms if r.get("active"))
    channels = await get_channels()
    daily = await get_daily_stats()
    monthly = await get_monthly_stats()
    
    await callback.message.edit_text(
        f"""
📊 <b>Statistika:</b>

━━━━━━━━━━━━━━━━━━
👥 Foydalanuvchilar:
   • Jami: <b>{await get_user_count()}</b> ta
   • Bugun: +{daily['new_users']} ta

📋 Buyurtmalar:
   • Jami: <b>{monthly['total_orders']}</b> ta
   • Bugun: +{daily['new_orders']} ta

🏠 Xonalar: <b>{active_rooms}/{len(rooms)}</b> ta

📢 Kanallar: <b>{len(channels)}</b> ta

💬 Suhbatlar: <b>{active_users()}</b> ta

💰 Daromad: <b>{format_price(monthly['revenue'])} so'm</b>

👮 Adminlar: <b>{len(await get_admins())}</b> ta
━━━━━━━━━━━━━━━━━━
""",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
        ])
    )


@router.callback_query(F.data == "orders_menu")
async def orders_menu(callback: CallbackQuery):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ Kutilayotgan", callback_data="orders_pending"),
         InlineKeyboardButton(text="✅ Tasdiqlangan", callback_data="orders_confirmed")],
        [InlineKeyboardButton(text="📋 Barchasi", callback_data="orders_all")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")],
    ])
    
    await callback.message.edit_text("📋 <b>Buyurtmalar:</b>", reply_markup=keyboard)


@router.callback_query(F.data.startswith("orders_"))
async def orders_list(callback: CallbackQuery):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    status_map = {
        "orders_pending": "pending",
        "orders_confirmed": "confirmed",
        "orders_all": None
    }
    
    status = status_map.get(callback.data)
    orders = await get_orders(status)
    
    if not orders:
        await callback.message.edit_text(
            "📋 Buyurtmalar yo'q",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Orqaga", callback_data="orders_menu")]
            ])
        )
        return
    
    buttons = []
    for order in orders[:15]:
        status_emoji = {"pending": "⏳", "confirmed": "✅", "completed": "🏁", "cancelled": "❌"}.get(order.get('status', 'pending'), "📋")
        source_emoji = "📱" if order.get('source') == 'instagram' else "💬"
        order_id_short = order.get('id', 'N/A')[-8:]
        
        buttons.append([InlineKeyboardButton(
            text=f"{status_emoji} {source_emoji} {order.get('room_name', 'Xona')} - {order.get('phone', 'N/A')}",
            callback_data=f"view_order_{order.get('id', '')}"
        )])
    
    buttons.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="orders_menu")])
    
    status_name = {"pending": "Kutilayotgan", "confirmed": "Tasdiqlangan", "orders_all": "Barcha"}.get(callback.data, "Buyurtmalar")
    
    try:
        await callback.message.edit_text(
            f"📋 <b>{status_name} buyurtmalar:</b>\n\n"
            "Buyurtmani bosib, tasdiqlashingiz yoki bekor qilishingiz mumkin.\n"
            "📱 = Instagram | 💬 = Telegram",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    except Exception:
        await callback.answer("Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data.startswith("view_order_"))
async def view_order(callback: CallbackQuery, bot: Bot):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    order_id = callback.data.replace("view_order_", "")
    order = await get_order(order_id)
    
    if not order:
        await callback.answer("❌ Buyurtma topilmadi", show_alert=True)
        return
    
    status_text = {"pending": "⏳ Kutilmoqda", "confirmed": "✅ Tasdiqlangan", "completed": "🏁 Tugallangan", "cancelled": "❌ Bekor qilingan"}.get(order.get('status', 'pending'), "📋")
    source_text = "📱 Instagram" if order.get('source') == 'instagram' else "💬 Telegram"
    
    phone = order.get('phone', '')
    phone_clean = phone.replace('tel:', '').strip() if phone else ''
    
    text = f"""
📋 <b>Buyurtma #{order.get('id', 'N/A')}</b>

{status_text} | {source_text}

━━━━━━━━━━━━━━━━━━━━━━
🏨 Xona: <b>{order.get('room_name', 'N/A')}</b>
📅 Kelish: {order.get('check_in', 'N/A')}
📅 Ketish: {order.get('check_out', 'N/A')}
👥 Mehmonlar: {order.get('guests', 1)} kishi
💰 Narxi: <b>{format_price(order.get('total_price', 0))} so'm</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 Ism: {order.get('name', 'N/A')}
📞 Telefon: {phone_clean}
📝 Manba: {order.get('source', 'N/A')}
━━━━━━━━━━━━━━━━━━━━━━
"""
    
    buttons = []
    if order.get('status') == 'pending':
        buttons.append([
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"order_confirm_{order_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"order_cancel_{order_id}")
        ])
    elif order.get('status') == 'confirmed':
        buttons.append([InlineKeyboardButton(text="🏁 Tugallangan", callback_data=f"order_complete_{order_id}")])
    
    if phone_clean and phone_clean.startswith('+'):
        buttons.append([InlineKeyboardButton(text="📞 Qo'ng'iroq", url=f"tel:{phone_clean}")])
    
    buttons.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="orders_pending")])
    
    try:
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    except Exception:
        await callback.answer("Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data.startswith("order_complete_"))
async def order_complete(callback: CallbackQuery):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    order_id = callback.data.replace("order_complete_", "")
    await update_order(order_id, "status", "completed")
    
    await callback.answer("✅ Tugallandi!", show_alert=True)
    await callback.message.edit_text("✅ Buyurtma tugallangan deb belgilandi!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="orders_confirmed")]
    ]))


@router.callback_query(F.data.startswith("order_confirm_"))
async def order_confirm(callback: CallbackQuery, bot: Bot):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    order_id = callback.data.replace("order_confirm_", "")
    await update_order(order_id, "status", "confirmed")
    
    order = await get_order(order_id)
    hotel = await get_hotel()
    
    if order:
        user_id = order.get('user_id', '')
        if order.get('source') == 'instagram':
            pass
        else:
            try:
                await bot.send_message(
                    int(user_id),
                    f"✅ <b>Broningiz tasdiqlandi!</b>\n\n"
                    f"🏨 {order.get('room_name')}\n"
                    f"📅 {order.get('check_in')} → {order.get('check_out')}\n"
                    f"📞 {hotel.get('phone', '+998773397171')}\n\n"
                    f"Xona tayyor bo'lganda siz bilan bog'lanamiz!"
                )
            except:
                pass
    
    await callback.answer("✅ Tasdiqlandi!", show_alert=True)
    await callback.message.edit_text("✅ Buyurtma tasdiqlandi!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Kutilayotganlarga", callback_data="orders_pending"),
         InlineKeyboardButton(text="📋 Barchasi", callback_data="orders_all")]
    ]))


@router.callback_query(F.data.startswith("order_cancel_"))
async def order_cancel(callback: CallbackQuery):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    order_id = callback.data.replace("order_cancel_", "")
    await update_order(order_id, "status", "cancelled")
    
    await callback.answer("❌ Bekor qilindi!", show_alert=True)
    await callback.message.edit_text("❌ Buyurtma bekor qilindi!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="orders_menu")]
    ]))


@router.callback_query(F.data == "users_menu")
async def users_menu(callback: CallbackQuery):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    users = await get_all_users()
    count = len(users)
    
    text = f"👥 <b>Foydalanuvchilar:</b>\n\nJami: <b>{count}</b> ta\n\n"
    
    for user in users[:10]:
        text += f"• {user.get('first_name', 'N/A')} (ID: {user.get('user_id', 'N/A')})\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Broadcast", callback_data="broadcast_menu")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == "broadcast_menu")
async def broadcast_menu(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    await state.set_state(BroadcastState.message)
    await state.update_data(step="broadcast")
    await callback.message.edit_text(
        "📤 <b>Broadcast xabar yuborish</b>\n\n"
        "Xabarni yozing:"
    )


@router.message(BroadcastState.message)
async def broadcast_send(message: Message, state: FSMContext, bot: Bot):
    if not await is_admin(str(message.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        await state.clear()
        return
    
    data = await state.get_data()
    if data.get("step") != "broadcast":
        await state.clear()
        return
    
    await state.clear()
    users = await get_all_users()
    sent = 0
    
    for user in users:
        try:
            await bot.send_message(
                int(user.get('user_id', 0)),
                f"📢 <b>Marco Polo Hotel dan:</b>\n\n{message.text}"
            )
            sent += 1
        except:
            pass
    
    await message.answer(
        f"✅ <b>Yuborildi!</b>\n\n{len(users)} ta foydalanuvchidan {sent} tasiga yuborildi."
    )


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="stats_refresh")],
        [InlineKeyboardButton(text="🏠 Xonalar", callback_data="admin_rooms_list"),
         InlineKeyboardButton(text="🏨 Mehmonxona", callback_data="hotel_info")],
        [InlineKeyboardButton(text="📢 Kanallar", callback_data="channels_manage"),
         InlineKeyboardButton(text="📝 Post", callback_data="post_create")],
        [InlineKeyboardButton(text="🟢 Bo'sh xonalar", callback_data="available_rooms")],
        [InlineKeyboardButton(text="✉️ Start xabar", callback_data="start_message")],
        [InlineKeyboardButton(text="👥 Adminlar", callback_data="admins_list")],
        [InlineKeyboardButton(text="🚪 Chiqish", callback_data="admin_logout")],
    ])
    
    await callback.message.edit_text("⚙️ <b>Admin Panel</b>", reply_markup=keyboard)


@router.callback_query(F.data == "admin_rooms_list")
async def rooms_manage(callback: CallbackQuery):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    rooms = await get_rooms()
    buttons = []
    for room in rooms:
        status = "✅" if room.get("active") else "❌"
        buttons.append([InlineKeyboardButton(
            text=f"{status} {room.get('name', 'Xona')} - {format_price(room.get('price', 0))} so'm",
            callback_data=f"admin_room_{room.get('id', '')}"
        )])
    
    buttons.append([InlineKeyboardButton(text="➕ Yangi xona", callback_data="add_room_start")])
    buttons.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")])
    
    await callback.message.edit_text(
        "🏠 <b>Xonalar boshqaruvi:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("admin_room_"))
async def room_detail_admin(callback: CallbackQuery):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    room_id = callback.data.replace("admin_room_", "")
    room = await get_room(room_id)
    
    if not room:
        await callback.answer("❌ Xona topilmadi")
        return

    status = "✅ Faol" if room.get("active") else "❌ Nofaol"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Narx", callback_data=f"edit_room_price_{room_id}"),
         InlineKeyboardButton(text="📝 Tavsif", callback_data=f"edit_room_desc_{room_id}")],
        [InlineKeyboardButton(text="❌ O'chirish" if room.get("active") else "✅ Yoqish", 
                             callback_data=f"toggle_room_{room_id}")],
        [InlineKeyboardButton(text="🗑 Xonani o'chirish", callback_data=f"delete_room_{room_id}")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_rooms_list")],
    ])
    
    await callback.message.edit_text(
        f"🏠 <b>{room.get('name')}</b>\n\n"
        f"💰 Narx: {format_price(room.get('price', 0))} so'm/kun\n"
        f"📋 Tavsif: {room.get('description', '')}\n"
        f"👥 Sig'im: {room.get('capacity', 0)} kishi\n"
        f"📌 Holat: {status}",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("toggle_room_"))
async def toggle_room(callback: CallbackQuery):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    room_id = callback.data.replace("toggle_room_", "")
    room = await get_room(room_id)
    new_status = 0 if room.get("active") else 1
    await update_room(room_id, "active", new_status)
    
    await callback.answer("✅ Holat o'zgartirildi!")
    await callback.message.edit_text(
        f"🏠 <b>{room.get('name')}</b>\n\n"
        f"💰 Narx: {format_price(room.get('price', 0))} so'm/kun\n"
        f"📋 Tavsif: {room.get('description', '')}\n"
        f"📌 Holat: {'✅ Faol' if new_status else '❌ Nofaol'}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_rooms_list")]
        ])
    )


@router.callback_query(F.data.startswith("delete_room_"))
async def delete_room_confirm(callback: CallbackQuery):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    room_id = callback.data.replace("delete_room_", "")
    room = await get_room(room_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"confirm_delete_{room_id}"),
         InlineKeyboardButton(text="❌ Yo'q", callback_data=f"admin_room_{room_id}")],
    ])
    
    await callback.message.edit_text(
        f"🗑 <b>{room.get('name')}</b>ni o'chirishni tasdiqlaysizmi?",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete(callback: CallbackQuery):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    room_id = callback.data.replace("confirm_delete_", "")
    await delete_room(room_id)
    
    await callback.answer("✅ Xona o'chirildi!")
    
    rooms = await get_rooms()
    buttons = []
    for room in rooms:
        status = "✅" if room.get("active") else "❌"
        buttons.append([InlineKeyboardButton(
            text=f"{status} {room.get('name', 'Xona')}",
            callback_data=f"admin_room_{room.get('id', '')}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")])
    
    await callback.message.edit_text("✅ Xona o'chirildi!", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("edit_room_price_"))
async def edit_room_price(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    room_id = callback.data.replace("edit_room_price_", "")
    await state.set_state(RoomEditState.waiting)
    await state.update_data(room_id=room_id, field="price")
    
    await callback.message.edit_text("💰 Yangi narxni yuboring (faqat raqam):")


@router.callback_query(F.data.startswith("edit_room_desc_"))
async def edit_room_desc(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    room_id = callback.data.replace("edit_room_desc_", "")
    await state.set_state(RoomEditState.waiting)
    await state.update_data(room_id=room_id, field="description")
    
    await callback.message.edit_text("📝 Yangi tavsifni yuboring:")


@router.message(RoomEditState.waiting)
async def save_room_edit(message: Message, state: FSMContext):
    if not await is_admin(str(message.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        await state.clear()
        return
    
    data = await state.get_data()
    step = data.get("step")
    room_id = data.get("room_id")
    field = data.get("field")
    
    if step == "room_name":
        room_name = message.text.strip()
        await state.update_data(room_name=room_name, step="room_price")
        await message.answer("💰 Narxini yuboring (faqat raqam):")
        
    elif step == "room_price":
        try:
            price = int(message.text.strip().replace(" ", "").replace(",", ""))
            await state.update_data(price=price, step="room_desc")
            await message.answer("📝 Tavsifni yuboring:")
        except:
            await message.answer("❌ Faqat raqam!")
            
    elif step == "room_desc":
        description = message.text.strip()
        await state.update_data(description=description, step="room_capacity")
        await message.answer("👥 Sig'imni yuboring (kishi soni):")
        
    elif step == "room_capacity":
        try:
            capacity = int(message.text.strip())
            data = await state.get_data()
            from uuid import uuid4
            room_id_new = str(uuid4().hex[:8])
            await add_room(room_id_new, {
                'name': data.get('room_name', 'Yangi xona'),
                'price': data.get('price', 200000),
                'description': data.get('description', ''),
                'capacity': capacity,
                'active': 1
            })
            await state.clear()
            await message.answer("✅ Xona qo'shildi!")
        except:
            await message.answer("❌ Faqat raqam!")
            
    elif room_id and field:
        value = message.text.strip()
        if field == "price":
            try:
                value = int(value.replace(" ", "").replace(",", ""))
            except:
                await message.answer("❌ Faqat raqam!")
                return
        await update_room(room_id, field, value)
        await state.clear()
        await message.answer("✅ Yangilandi!")
    else:
        await state.clear()


@router.callback_query(F.data == "add_room_start")
async def add_room_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    await state.set_state(RoomEditState.waiting)
    await state.update_data(step="room_name")
    await callback.message.edit_text("➕ Yangi xona qo'shish\n\nXona nomini yuboring:")


@router.callback_query(F.data == "hotel_info")
async def hotel_info(callback: CallbackQuery):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    hotel = await get_hotel()
    await callback.message.edit_text(
        f"""
🏨 <b>Mehmonxona:</b>

Nomi: {hotel.get('name', 'Marco Polo Hotel')}
Manzil: {hotel.get('address', '')}
Telefon: {hotel.get('phone', '')}
Telegram: {hotel.get('telegram', '')}
""",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Nom", callback_data="edit_hotel_name"),
             InlineKeyboardButton(text="📍 Manzil", callback_data="edit_hotel_address")],
            [InlineKeyboardButton(text="📞 Telefon", callback_data="edit_hotel_phone")],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
        ])
    )


@router.callback_query(F.data.startswith("edit_hotel_"))
async def edit_hotel(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    field = callback.data.replace("edit_hotel_", "")
    await state.set_state(HotelEditState.waiting)
    await state.update_data(hotel_field=field)
    await callback.message.edit_text(f"Yangi {field}ni yuboring:")


@router.message(HotelEditState.waiting)
async def save_hotel_edit(message: Message, state: FSMContext):
    if not await is_admin(str(message.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        await state.clear()
        return
    
    data = await state.get_data()
    field = data.get("hotel_field")
    
    if field:
        await update_hotel(field, message.text.strip())
    
    await state.clear()
    await message.answer("✅ Yangilandi!")


@router.callback_query(F.data == "channels_manage")
async def channels_manage(callback: CallbackQuery):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    channels = await get_channels()
    post_ch = await get_post_channel()
    
    text = f"📢 <b>Kanallar:</b>\n\n"
    for ch in channels:
        text += f"• {ch.get('title', ch.get('channel_id', ''))}\n"
    text += f"\nPost kanali: {post_ch or 'Belgilanmagan'}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_channel")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == "add_channel")
async def add_channel(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    await state.set_state(ChannelState.waiting)
    await state.update_data(step="add_channel")
    await callback.message.edit_text(
        "📢 Kanal ID sini yuboring:\n"
        "Format: -1001234567890\n"
        "Post kanali uchun: post:-1001234567890"
    )


@router.message(ChannelState.waiting)
async def save_channel(message: Message, state: FSMContext, bot: Bot):
    if not await is_admin(str(message.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        await state.clear()
        return
    
    data = await state.get_data()
    
    if data.get("step") == "add_channel":
        text = message.text.strip()
        is_post = text.startswith("post:")
        if is_post:
            text = text.replace("post:", "").strip()
            await set_post_channel(text)
            await state.clear()
            await message.answer("✅ Post kanali belgilandi!")
            return
        
        try:
            channel_id = int(text)
            chat = await bot.get_chat(channel_id)
            await db_add_channel({"channel_id": str(channel_id), "title": chat.title or str(channel_id), "username": chat.username or ""})
            await state.clear()
            await message.answer("✅ Kanal qo'shildi!")
        except:
            await message.answer("❌ Kanal topilmadi!")
            await state.clear()
        return
    
    await state.clear()


@router.callback_query(F.data == "post_create")
async def post_create(callback: CallbackQuery):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    post_ch = await get_post_channel()
    if not post_ch:
        await callback.answer("⚠️ Post kanali belgilanmagan!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 AI bilan yozish", callback_data="post_ai")],
        [InlineKeyboardButton(text="✍️ Qo'lda yozish", callback_data="post_manual")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text("📝 <b>Post yaratish</b>", reply_markup=keyboard)


@router.callback_query(F.data == "post_ai")
async def post_ai(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    await state.set_state(PostState.waiting)
    await state.update_data(step="post_topic")
    await callback.message.edit_text("🤖 Post mavzusini yozing:")


@router.callback_query(F.data == "post_manual")
async def post_manual(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    await state.set_state(PostState.waiting)
    await state.update_data(step="post_manual")
    await callback.message.edit_text("✍️ Post matnini yozing:")


@router.message(PostState.waiting)
async def generate_post_message(message: Message, state: FSMContext, bot: Bot):
    if not await is_admin(str(message.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        await state.clear()
        return
    
    data = await state.get_data()
    step = data.get("step")
    
    if step == "post_topic":
        await message.answer("⏳ Post yozilmoqda...")
        post_text = await generate_post(message.text, "Marco Polo Hotel")
        
        await state.update_data(post_text=post_text, step="post_preview")
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Yuborish", callback_data="send_post"),
             InlineKeyboardButton(text="♻️ Qayta", callback_data="post_ai")],
            [InlineKeyboardButton(text="❌ Bekor", callback_data="admin_back")]
        ])
        
        await message.answer(f"📝 <b>Tayyor post:</b>\n\n{post_text}", reply_markup=keyboard)
        
    elif step == "post_manual":
        await state.update_data(post_text=message.text, step="post_preview")
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Yuborish", callback_data="send_post")],
            [InlineKeyboardButton(text="❌ Bekor", callback_data="admin_back")]
        ])
        
        await message.answer(f"📝 <b>Post:</b>\n\n{message.text}", reply_markup=keyboard)
    
    elif step == "post_preview":
        await state.clear()
        await message.answer("❌ Bekor qilindi.")


@router.callback_query(F.data == "send_post")
async def send_post(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    data = await state.get_data()
    post_text = data.get("post_text", "")
    post_ch = await get_post_channel()
    
    if not post_ch:
        await callback.answer("⚠️ Kanal belgilanmagan!", show_alert=True)
        return
    
    try:
        await bot.send_message(int(post_ch), post_text)
        await callback.answer("✅ Yuborildi!", show_alert=True)
        await callback.message.edit_text("✅ Post kanalga yuborildi!")
    except:
        await callback.answer("❌ Xatolik!", show_alert=True)
    
    await state.clear()


@router.callback_query(F.data == "admins_list")
async def admins_list(callback: CallbackQuery):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    admins = await get_admins()
    super_admin = os.getenv("SUPER_ADMIN_ID", "belgilanmagan")
    
    text = f"👥 <b>Adminlar:</b>\n\n"
    text += f"👑 Super Admin: <code>{super_admin}</code>\n\n"
    text += "📋 Adminlar:\n"
    for admin in admins:
        text += f"• <code>{admin}</code>\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qo'shish", callback_data="add_admin_start")],
        [InlineKeyboardButton(text="➖ O'chirish", callback_data="remove_admin_start")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == "add_admin_start")
async def add_admin_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return
    
    await state.set_state(AdminManageState.waiting)
    await state.update_data(step="add_admin")
    await callback.message.edit_text("➕ Yangi admin ID sini yuboring:")


@router.callback_query(F.data == "remove_admin_start")
async def remove_admin_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return

    await state.set_state(AdminManageState.waiting)
    await state.update_data(step="remove_admin")
    await callback.message.edit_text("➖ O'chiriladigan admin ID sini yuboring:")


@router.message(AdminManageState.waiting)
async def save_admin(message: Message, state: FSMContext):
    if not await is_admin(str(message.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        await state.clear()
        return
    
    data = await state.get_data()
    
    if data.get("step") == "add_admin":
        admin_id = message.text.strip()
        await db_add_admin(admin_id)
        await state.clear()
        await message.answer(f"✅ Admin qo'shildi: {admin_id}")
    elif data.get("step") == "remove_admin":
        admin_id = message.text.strip()
        await db_remove_admin(admin_id)
        await state.clear()
        await message.answer(f"✅ Admin o'chirildi: {admin_id}")
    else:
        await state.clear()


@router.callback_query(F.data == "available_rooms")
async def available_rooms_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return

    await state.set_state(AvailabilityState.waiting)
    await callback.message.edit_text(
        "🟢 Bo'sh xonalar\n\n"
        "Sanalarni yuboring:\n"
        "Format: 2026-04-10 2026-04-12"
    )


@router.message(AvailabilityState.waiting)
async def available_rooms_show(message: Message, state: FSMContext):
    if not await is_admin(str(message.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        await state.clear()
        return

    text = message.text.strip()
    parts = text.split()
    if len(parts) != 2:
        await message.answer("❌ Format xato. Masalan: 2026-04-10 2026-04-12")
        return

    check_in, check_out = parts[0], parts[1]
    if not _validate_date(check_in) or not _validate_date(check_out):
        await message.answer("❌ Sana noto'g'ri! Format: YYYY-MM-DD")
        return

    rooms = await find_available_rooms(check_in, check_out, only_active=True)
    await state.clear()


@router.callback_query(F.data == "start_message")
async def start_message(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(str(callback.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        return

    await state.set_state(StartMessageState.waiting)
    await callback.message.edit_text(
        "Start xabarni yuboring.\n"
        "Matn, rasm+matn, voice, video, dokument yoki location bo'lishi mumkin.\n"
        "Shu xabar /start bosilganda yuboriladi."
    )


@router.message(StartMessageState.waiting)
async def save_start_message(message: Message, state: FSMContext):
    if not await is_admin(str(message.from_user.id), os.getenv("SUPER_ADMIN_ID")):
        await state.clear()
        return

    payload = {"type": "text", "text": ""}

    if message.location:
        payload = {
            "type": "location",
            "lat": message.location.latitude,
            "lng": message.location.longitude,
        }
    elif message.photo:
        payload = {
            "type": "photo",
            "file_id": message.photo[-1].file_id,
            "caption": message.caption or "",
        }
    elif message.video:
        payload = {
            "type": "video",
            "file_id": message.video.file_id,
            "caption": message.caption or "",
        }
    elif message.voice:
        payload = {
            "type": "voice",
            "file_id": message.voice.file_id,
            "caption": message.caption or "",
        }
    elif message.document:
        payload = {
            "type": "document",
            "file_id": message.document.file_id,
            "caption": message.caption or "",
        }
    elif message.text:
        payload = {"type": "text", "text": message.text}

    await set_setting("start_message", json.dumps(payload, ensure_ascii=False))
    await state.clear()
    await message.answer("✅ Start xabar saqlandi.")

    if not rooms:
        await message.answer("❌ Bu sanalarda bo'sh xona topilmadi.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
        ]))
        return

    lines = [f"✅ Bo'sh xonalar ({check_in} → {check_out}):"]
    for room in rooms:
        lines.append(f"- {room.get('name')} | {format_price(room.get('price', 0))} so'm/kun")

    await message.answer("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
    ]))


def _validate_date(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except Exception:
        return False
