"""
Majburiy obuna tekshirish
"""

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.database import get_channels


async def check_subscription(bot: Bot, user_id: int) -> tuple[bool, list]:
    """
    Foydalanuvchi barcha majburiy kanallarga obuna bo'lganini tekshiradi.
    Returns: (all_subscribed: bool, not_subscribed_channels: list)
    """
    channels = get_channels()
    if not channels:
        return True, []

    not_subscribed = []
    for channel in channels:
        try:
            member = await bot.get_chat_member(channel["channel_id"], user_id)
            if member.status in ("left", "kicked", "banned"):
                not_subscribed.append(channel)
        except Exception:
            pass

    return len(not_subscribed) == 0, not_subscribed


def subscription_keyboard(channels: list) -> InlineKeyboardMarkup:
    """Obuna bo'lmagan kanallar uchun tugmalar"""
    buttons = []
    for ch in channels:
        username = ch.get("username", "")
        title = ch.get("title", "Kanal")
        if username:
            url = f"https://t.me/{username.lstrip('@')}"
        else:
            channel_id = str(ch.get('channel_id', '')).replace('-100', '')
            url = f"https://t.me/c/{channel_id}"
        buttons.append([InlineKeyboardButton(text=f"📢 {title}", url=url)])

    buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
