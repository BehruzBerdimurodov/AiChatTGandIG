"""
AI Handler - Professional AI yordamchi
Bron qilish va barcha savollarga javob beradi
"""

import os
import re
from datetime import datetime
from openai import AsyncOpenAI
from config.database import get_hotel, get_rooms, get_room, create_order, log_message, log_activity, register_user, get_admins

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_store: dict[str, list[dict]] = {}
MAX_HISTORY = 12

BOOKING_STORE: dict[str, dict] = {}

TELEGRAM_BOT_LINK = "https://t.me/MarcoPoloHotelBot"


async def _build_system_prompt(user_platform: str = "telegram") -> str:
    hotel = await get_hotel()
    rooms = await get_rooms(only_active=True)
    
    room_lines = []
    for r in rooms:
        price = f"{r['price']:,}".replace(",", " ")
        room_lines.append(f"- {r['name']}: {price} so'm/kun | {r['description']} | {r['capacity']} kishi")
    rooms_text = "\n".join(room_lines) if room_lines else "Xonalar mavjud emas"
    
    hotel_phone = hotel.get('phone', '+998773397171')
    hotel_phone2 = hotel.get('phone_2', '+998771577171')
    hotel_address = hotel.get('address', "Do'mbirobod Naqqoshlik 122A")

    platform_intro = "SIZ: Marco Polo Hotel 🏩 - Professional Telegram AI yordamchisi"
    if user_platform == "instagram":
        platform_intro = "SIZ: Marco Polo Hotel 🏩 - Professional Instagram Direct AI yordamchisi"

    return f"""
{platform_intro}

MEHMONXONA: Marco Polo Hotel
Manzil: {hotel_address}, Toshkent, Chilonzor tumani
Telefon: {hotel_phone}
Telefon 2: {hotel_phone2}

XONALAR VA NARXLAR:
{rooms_text}

SOATLIK IJARAGA Olish: 200.000 - 250.000 so'm

AFZALLIKLAR:
✅ Maxfiylik kafolatlanadi | ✅ ZAGS talab qilinmaydi
✅ 1 pasport evaziga | ✅ Spa salon | ✅ Lounge bar
✅ SMART TV | ✅ Wi-Fi | ✅ Konditsioner

BRON QILISHDA QUYIDAGI TARTIBDA MALUMOT SO'RANG:
1. Avval ism so'rang
2. Qaysi xona kerakligini so'rang
3. Kelish sanasini so'rang (kun-oy-yil)
4. Ketish sanasini so'rang
5. Necha kishi ekanligini so'rang
6. Telefon raqamini so'rang

AGAR MALUMOT TO'LIQ BO'LSA:
✅ Qabul qiling va quyidagi xabarni yuboring:

"✅ <b>Broningiz qabul qilindi!</b>

🏨 Xona: [xona nomi]
📅 Kelish: [sana]
📅 Ketish: [sana]
👥 [kishi soni] kishi
💰 Jami: [narxi] so'm

👤 [ism]
📞 [telefon]

━━━━━━━━━━━━━━━━━━━━━━
✅ Bronni tasdiqlash uchun: <b>Tasdiqlayman</b>
❌ Rad etish uchun: <b>Rad etaman</b> deb yozing."

AGAR MALUMOT TO'LIQ EMAS BO'LSA:
- Qaysi malumot yo'q ekanini aniq ayting
- Masalan: "Iltimos, telefon raqamingizni ham yuboring" yoki "Qaysi sanadan boshlab kerak?"
- Bitta savol bering, ortiqcha savol bermang

JAVOB BERISHDA:
- Do'stona va professional bo'ling
- Har doim telefon raqamini bering: {hotel_phone}
- Xonalar haqida batafsil ma'lumot bering
- Narxni aniq ayting

TONALIK: Do'stona, yo'naltiruvchi, professional, har doim yordam berishga tayyor
"""


def extract_booking_info(text: str) -> dict | None:
    """Foydalanuvchi xabaridan bron ma'lumotlarini ajratib olish"""
    text_lower = text.lower().strip()
    
    name = None
    phone = None
    check_in = None
    check_out = None
    guests = None
    room_type = None
    
    name_patterns = [
        r'ism(?:i|im|lar|larim)?[:\s]+([a-zA-Zа-яА-ЯёЁ\s]+?)(?:,|\.|$)',
        r'ism\s*[:\-]?\s*([a-zA-Zа-яА-ЯёЁ\s]+?)(?:,|\n|$)',
        r'name\s*[:\-]?\s*([a-zA-Z\s]+?)(?:,|\n|$)',
        r'^([a-zA-Zа-яА-ЯёЁ]{3,20})\s*(?:,|\.| Mening)',
    ]
    for pattern in name_patterns:
        name_match = re.search(pattern, text, re.IGNORECASE)
        if name_match:
            name = name_match.group(1).strip().title()
            name = re.sub(r'[^a-zA-Zа-яА-ЯёЁ\s]', '', name)
            if len(name) > 2:
                break
    
    phone_match = re.search(r'\+?998[\d]{9}', text)
    if phone_match:
        phone = phone_match.group(0)
        if not phone.startswith('+'):
            phone = '+' + phone
    
    month_map = {
        'yanvar': '01', 'fevral': '02', 'mart': '03', 'aprel': '04',
        'may': '05', 'iyun': '06', 'iyul': '07', 'avgust': '08',
        'sentabr': '09', 'oktabr': '10', 'noyabr': '11', 'dekabr': '12'
    }
    
    year = datetime.now().year
    
    date_patterns = [
        r'(\d{1,2})\s*(?:dekabr|yanvar|fevral|mart|aprel|may|iyun|iyul|avgust|sentabr|oktabr|noyabr)',
        r'(\d{4})[-./](\d{2})[-./](\d{2})',
        r'(\d{1,2})[-./](\d{1,2})[-./](\d{2,4})',
    ]
    
    dates_found = []
    
    for month_name, month_num in month_map.items():
        pattern = rf'(\d{{1,2}})\s*{month_name}(?:dan|gatacha)?'
        matches = re.findall(pattern, text_lower)
        for m in matches:
            dates_found.append(f"{year}-{month_num}-{m.zfill(2)}")
    
    if len(dates_found) >= 1:
        check_in = dates_found[0]
    if len(dates_found) >= 2:
        check_out = dates_found[1]
    
    if not check_in or not check_out:
        date_std = re.findall(r'(\d{4})[-./](\d{2})[-./](\d{2})', text)
        if len(date_std) >= 1:
            if not check_in:
                check_in = f"{date_std[0][0]}-{date_std[0][1]}-{date_std[0][2]}"
        if len(date_std) >= 2:
            if not check_out:
                check_out = f"{date_std[1][0]}-{date_std[1][1]}-{date_std[1][2]}"
    
    guests_match = re.search(r'(\d+)\s*(?:kishi|odam|mehmon|kishi|odamlari|kishilik)', text_lower)
    if guests_match:
        guests = int(guests_match.group(1))
    
    room_keywords = [
        ('premium', 'premium'),
        ('standart', 'standart'),
        ('standard', 'standart'),
        ('deluxe', 'deluxe'),
        ('suite', 'suite'),
        ('suit', 'suite'),
        ('vip', 'vip'),
        ('family', 'family'),
        ('oilaviy', 'family'),
    ]
    for keyword, room_id in room_keywords:
        if keyword in text_lower:
            room_type = room_id
            break
    
    if check_in and check_out:
        return {
            'name': name or 'Mehmon',
            'phone': phone or '+998000000000',
            'check_in': check_in,
            'check_out': check_out,
            'guests': guests or 2,
            'room_type': room_type
        }
    
    return None


def get_history(user_id: str) -> list:
    return list(_store.get(str(user_id), []))


def push_message(user_id: str, role: str, content: str):
    uid = str(user_id)
    history = _store.setdefault(uid, [])
    history.append({"role": role, "content": content})
    if len(history) > MAX_HISTORY:
        _store[uid] = history[-MAX_HISTORY:]


def clear_history(user_id: str):
    _store.pop(str(user_id), None)


def active_users() -> int:
    return len(_store)


async def get_ai_response(
    user_id: str, 
    user_message: str, 
    user_name: str = "Mehmon",
    platform: str = "telegram"
) -> str:
    history = get_history(user_id)
    push_message(user_id, "user", user_message)

    booking_info = extract_booking_info(user_message)
    
    print(f"[AI] User: {user_id}, Platform: {platform}")
    print(f"[AI] Message: {user_message}")
    print(f"[AI] Booking info extracted: {booking_info}")
    
    if booking_info is None:
        print(f"[AI] DEBUG: extract_booking_info returned None")
    
    if booking_info:
        rooms = await get_rooms(only_active=True)
        room = None
        if booking_info.get('room_type'):
            room = next((r for r in rooms if booking_info['room_type'] in r['id'].lower() or booking_info['room_type'] in r['name'].lower()), None)
        if not room and rooms:
            room = rooms[0]
        
        if room:
            try:
                check_in = datetime.strptime(booking_info['check_in'], '%Y-%m-%d')
                check_out = datetime.strptime(booking_info['check_out'], '%Y-%m-%d')
                days = max(1, (check_out - check_in).days)
                total_price = room['price'] * days
                price_fmt = f"{total_price:,}".replace(",", " ")
                
                order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                order_data = {
                    'id': order_id,
                    'user_id': user_id.replace('tg_', '').replace('ig_', ''),
                    'room_id': room['id'],
                    'room_name': room['name'],
                    'check_in': booking_info['check_in'],
                    'check_out': booking_info['check_out'],
                    'guests': booking_info['guests'],
                    'total_price': total_price,
                    'name': booking_info['name'],
                    'phone': booking_info['phone'],
                    'notes': '',
                    'source': platform
                }
                
                BOOKING_STORE[user_id] = order_data
                print(f"[BOOKING] Stored: {order_id} for {user_id}")
                
                if platform == "telegram":
                    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                    
                    reply = f"""✅ <b>Broningiz qabul qilindi!</b>

🏨 Xona: <b>{room['name']}</b>
📅 Kelish: {booking_info['check_in']}
📅 Ketish: {booking_info['check_out']}
📆 {days} kun
👥 {booking_info['guests']} kishi
💰 Jami: <b>{price_fmt} so'm</b>

👤 {booking_info['name']}
📞 {booking_info['phone']}

━━━━━━━━━━━━━━━━━━━━━━
✅ Bronni tasdiqlash uchun: <b>Tasdiqlayman</b>
❌ Rad etish uchun: <b>Rad etaman</b> deb yozing."""
                else:
                    reply = f"""✅ <b>Broningiz qabul qilindi!</b>

🏨 Xona: {room['name']}
📅 Kelish: {booking_info['check_in']}
📅 Ketish: {booking_info['check_out']}
👥 {booking_info['guests']} kishi
💰 Jami: {price_fmt} so'm

👤 {booking_info['name']}
📞 {booking_info['phone']}

━━━━━━━━━━━━━━━━━━━━━━
✅ Bronni tasdiqlash uchun: <b>Tasdiqlayman</b>
❌ Rad etish uchun: <b>Rad etaman</b> deb yozing."""
                
                push_message(user_id, "assistant", reply)
                await log_message(user_id, "incoming", user_message, reply)
                return reply
                
            except Exception as e:
                pass

    messages = [
        {"role": "system", "content": await _build_system_prompt(platform)},
        *history,
        {"role": "user", "content": user_message},
    ]

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=500,
            temperature=0.7,
        )
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        import traceback
        import logging
        log = logging.getLogger(__name__)
        log.error(f"[AI ERROR OPENAI] {e}")
        print(f"[AI ERROR OPENAI] Exception details:\n{traceback.format_exc()}")
        hotel = await get_hotel()
        reply = f"""Kechirasiz, texnik muammo yuz berdi.

📞 Telefon: {hotel.get('phone', '+998773397171')}
💬 Telegram: @Marcopolohotel_1"""

    push_message(user_id, "assistant", reply)
    await log_message(user_id, "incoming", user_message, reply)
    await log_activity(user_id, "chat", user_message[:50])
    
    return reply


async def generate_post(topic: str, hotel_name: str) -> str:
    hotel = await get_hotel()
    prompt = f"""
Marco Polo Hotel uchun Telegram post yozing:
Mavzu: {topic}
Format:
📌 Sarlavha
Matn (3-5 jumla)
Narxlar albatta
📞 {hotel.get('phone', '+998773397171')} | {hotel.get('telegram', '@Marcopolohotel_1')}
"""
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.8,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Post yaratishda xatolik. Qayta urinib ko'ring."


async def generate_booking_confirmation(order_data: dict) -> str:
    hotel = await get_hotel()
    price_fmt = f"{order_data['total_price']:,}".replace(",", " ")
    
    return f"""
✅ BUYURTMA QABUL QILINDI!

━━━━━━━━━━━━━━━━━━━━━━━━
🏨 Xona: {order_data['room_name']}
📅 Kelish: {order_data['check_in']}
📅 Ketish: {order_data['check_out']}
👥 Mehmonlar: {order_data['guests']} kishi
💰 Jami: {price_fmt} so'm

👤 Ism: {order_data['name']}
📞 Telefon: {order_data['phone']}
━━━━━━━━━━━━━━━━━━━━━━━━

⏳ Operator tez orada siz bilan bog'lanadi!

📞 {hotel.get('phone', '+998773397171')}
"""


async def send_order_to_admins(bot, order_data: dict, admin_ids: list):
    hotel = await get_hotel()
    price_fmt = f"{order_data['total_price']:,}".replace(",", " ")
    
    hotel_address = hotel.get('address', "Do'mbirobod Naqqoshlik 122A")
    message = f"""
🔔 <b>YANGI BRON!</b>

━━━━━━━━━━━━━━━━━━━━━━━━
🏨 Xona: <b>{order_data['room_name']}</b>
📅 {order_data['check_in']} → {order_data['check_out']}
👥 {order_data['guests']} kishi
💰 <b>{price_fmt} so'm</b>

👤 {order_data['name']}
📞 {order_data['phone']}
━━━━━━━━━━━━━━━━━━━━━━━━
📍 Manzil: {hotel_address}
"""
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    phone_clean = order_data.get('phone', '').replace('tel:', '').strip()
    keyboard_buttons = [
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"order_confirm_{order_data['id']}"),
         InlineKeyboardButton(text="❌ Bekor", callback_data=f"order_cancel_{order_data['id']}")]
    ]
    if phone_clean and phone_clean.startswith('+'):
        keyboard_buttons.append([InlineKeyboardButton(text="📞 Qo'ng'iroq", url=f"https://t.me/+{phone_clean[1:]}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    for admin_id in admin_ids:
        try:
            await bot.send_message(int(admin_id), message, reply_markup=keyboard)
        except:
            pass


def get_booking_data(user_id: str) -> dict | None:
    return BOOKING_STORE.get(str(user_id))


def clear_booking_data(user_id: str):
    BOOKING_STORE.pop(str(user_id), None)
