"""
Barcha klaviaturalar
"""

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton,
)


def main_kb(user_id: int = None) -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def rooms_inline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Bron qilish", callback_data="book_now")],
        [InlineKeyboardButton(text="◀️ Asosiy menyu", callback_data="back_main")],
    ])


def back_main_inline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Asosiy menyu", callback_data="back_main")]
    ])


def admin_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Buyurtmalar", callback_data="orders_menu")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="stats_refresh")],
        [InlineKeyboardButton(text="🏠 Xonalar", callback_data="admin_rooms_list"),
         InlineKeyboardButton(text="🏨 Mehmonxona", callback_data="hotel_info")],
        [InlineKeyboardButton(text="📢 Kanallar", callback_data="channels_manage"),
         InlineKeyboardButton(text="📝 Post", callback_data="post_create")],
        [InlineKeyboardButton(text="👥 Adminlar", callback_data="admins_list")],
    ])


def rooms_manage_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")],
    ])


def room_detail_kb(room_id: str, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "❌ O'chirish" if is_active else "✅ Yoqish"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Nom", callback_data=f"edit_room_name_{room_id}"),
         InlineKeyboardButton(text="💰 Narx", callback_data=f"edit_room_price_{room_id}")],
        [InlineKeyboardButton(text="📝 Tavsif", callback_data=f"edit_room_desc_{room_id}"),
         InlineKeyboardButton(text="👥 Sig'im", callback_data=f"edit_room_capacity_{room_id}")],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_room_{room_id}")],
        [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"delete_room_{room_id}")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_rooms_list")],
    ])


def channels_manage_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")],
    ])


def post_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")],
    ])


def post_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")],
    ])


def hotel_edit_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")],
    ])


def confirm_delete_kb(room_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"confirm_delete_{room_id}"),
         InlineKeyboardButton(text="❌ Yo'q", callback_data=f"admin_room_{room_id}")],
    ])
