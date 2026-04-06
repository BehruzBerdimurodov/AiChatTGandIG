"""
AI Handler - Professional AI yordamchi
Bron qilish va barcha savollarga javob beradi
"""

import os
import re
from datetime import datetime
from openai import AsyncOpenAI
from config.database import get_hotel, get_rooms, get_room, create_order, log_message, log_activity, register_user, get_admins, find_available_rooms, get_user

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_store: dict[str, list[dict]] = {}
MAX_HISTORY = 12

BOOKING_STORE: dict[str, dict] = {}
BOOKING_DRAFT: dict[str, dict] = {}

TELEGRAM_BOT_LINK = "https://t.me/MarcoPoloHotelBot"


async def _build_system_prompt(user_platform: str = "telegram") -> str:
    hotel = await get_hotel()
    rooms = await get_rooms(only_active=True)
    
    room_lines = []
    for r in rooms:
        price = f"{r['price']:,}".replace(",", " ")
        room_lines.append(
            f"- {r['name']}: {price} so'm/kun | {r['description']} | {r['capacity']} kishi | {r.get('quantity', 1)} ta"
        )
    rooms_text = "\n".join(room_lines) if room_lines else "Xonalar mavjud emas"
    
    hotel_phone = hotel.get('phone', '+998773397171')
    hotel_phone2 = hotel.get('phone_2', '+998771577171')
    hotel_address = hotel.get('address', "Do'mbirobod Naqqoshlik 121A")

    platform_intro = "SIZ: Marco Polo Hotel рџЏ© - Professional Telegram AI yordamchisi"
    if user_platform == "instagram":
        platform_intro = "SIZ: Marco Polo Hotel рџЏ© - Professional Instagram Direct AI yordamchisi"

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
вњ… Maxfiylik kafolatlanadi | вњ… ZAGS talab qilinmaydi
вњ… 1 pasport evaziga | вњ… Spa salon | вњ… Lounge bar
вњ… SMART TV | вњ… Wi-Fi | вњ… Konditsioner

BRON QILISHDA QUYIDAGI TARTIBDA MALUMOT SO'RANG:
1. Avval ism so'rang
2. Qaysi xona kerakligini so'rang
3. Kelish sanasini so'rang (kun-oy-yil)
4. Ketish sanasini so'rang
5. Necha kishi ekanligini so'rang
6. Telefon raqamini so'rang

AGAR "BO'SH XONA" DEB SO'RASA:
- Avval kelish va ketish sanasini so'rang
- Sanalar berilsa, mavjud xonalarni ayting

AGAR MALUMOT TO'LIQ BO'LSA:
вњ… Qabul qiling va quyidagi xabarni yuboring:

"вњ… <b>Broningiz qabul qilindi!</b>

рџЏЁ Xona: [xona nomi]
рџ"… Kelish: [sana]
рџ"… Ketish: [sana]
рџ'Ґ [kishi soni] kishi
рџ'° Jami: [narxi] so'm

рџ'¤ [ism]
рџ"ћ [telefon]

в"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓ
вњ… Bronni tasdiqlash uchun: <b>Tasdiqlayman</b>
вќЊ Rad etish uchun: <b>Rad etaman</b> deb yozing."

AGAR MALUMOT TO'LIQ EMAS BO'LSA:
- Qaysi malumot yo'q ekanini aniq ayting
- Masalan: "Iltimos, telefon raqamingizni ham yuboring" yoki "Qaysi sanadan boshlab kerak?"
- Bitta savol bering, ortiqcha savol bermang

JAVOB BERISHDA:
- Do'stona va professional bo'ling
- Har doim telefon raqamini bering: {hotel_phone}
- Xonalar haqida batafsil ma'lumot bering
- Narxni aniq ayting
- Gaplarni xilma-xil yozing, bir xil jumlani takrorlamang
- Odamdek tabiiy, tushunarli va qiziqarli qilib yozing
- Kerak bo'lsa qisqa izoh va foydali maslahat qo'shing, lekin mavzudan chetlashmang
- Javobni soddalashtiring, oson tushunarli qiling

TONALIK: Do'stona, yo'naltiruvchi, professional, tabiiy va iliq (odamdek)
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
    room_choice_index = None
    
    name_patterns = [
        r'ism(?:i|im|lar|larim)?[:\s]+([a-zA-Z\s]+?)(?:,|\.|$)',
        r'ism\s*[:\-]?\s*([a-zA-Z\s]+?)(?:,|\n|$)',
        r'name\s*[:\-]?\s*([a-zA-Z\s]+?)(?:,|\n|$)',
        r'^([a-zA-Z]{3,20})\s*(?:,|\.| Mening)',
    ]
    for pattern in name_patterns:
        name_match = re.search(pattern, text, re.IGNORECASE)
        if name_match:
            name = name_match.group(1).strip().title()
            name = re.sub(r'[^a-zA-Z\s]', '', name)
            if len(name) > 2:
                break

    # If the entire message is likely a name (one or two words, letters only)
    if not name and re.fullmatch(r'[A-Za-z]+(?:\s+[A-Za-z]+)?', text.strip()):
        name = text.strip().title()
    
    phone_match = re.search(r'\+?998[\d]{9}', text)
    if phone_match:
        phone = phone_match.group(0)
        if not phone.startswith('+'):
            phone = '+' + phone
    
    month_map = {
        'yanvar': '01', 'fevral': '02', 'mart': '03', 'aprel': '04',
        'may': '05', 'iyun': '06', 'iyul': '07', 'avgust': '08',
        'sentabr': '09', 'sentyabr': '09',
        'oktabr': '10', 'oktyabr': '10',
        'noyabr': '11', 'dekabr': '12'
    }
    
    year = datetime.now().year
    
    date_patterns = [
        r'(\d{1,2})\s*(?:dekabr|yanvar|fevral|mart|aprel|may|iyun|iyul|avgust|sentabr|sentyabr|oktabr|oktyabr|noyabr)',
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

    # "6 maqul", "6 xona", "xona 6", "6-tanladim" kabi holatlar
    room_index_match = re.search(r'\b([1-9])\s*(?:-?\s*xona|xona|maqul|tanladim|tanlayman)?\b', text_lower)
    if room_index_match:
        try:
            room_choice_index = int(room_index_match.group(1))
        except Exception:
            room_choice_index = None
    
    if any([name, phone, check_in, check_out, guests, room_type, room_choice_index]):
        return {
            'name': name,
            'phone': phone,
            'check_in': check_in,
            'check_out': check_out,
            'guests': guests,
            'room_type': room_type,
            'room_choice_index': room_choice_index,
        }
    
    return None


def _merge_booking(draft: dict, info: dict) -> dict:
    merged = dict(draft)
    for key, value in info.items():
        if value is not None and value != "":
            merged[key] = value
    return merged


def _next_missing_field(draft: dict) -> str | None:
    if not draft.get("name"):
        return "name"
    if not draft.get("room_type") and not draft.get("room_choice_index") and not draft.get("room_id"):
        return "room"
    if not draft.get("check_in"):
        return "check_in"
    if not draft.get("check_out"):
        return "check_out"
    if not draft.get("guests"):
        return "guests"
    if not draft.get("phone"):
        return "phone"
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
    text_lower = user_message.lower().strip()
    if "bosh xona" in text_lower:
        text_lower = text_lower.replace("bosh xona", "bo'sh xona")

    # Greeting: clear any stale draft so it doesn't force date questions
    if not booking_info and any(
        phrase in text_lower
        for phrase in [
            "salom",
            "assalomu alaykum",
            "Р°СЃСЃР°Р»РѕРјСѓ Р°Р»Р°Р№РєСѓРј",
            "hello",
            "hi",
        ]
    ):
        BOOKING_DRAFT.pop(user_id, None)
        BOOKING_STORE.pop(user_id, None)
        reply = "Salom! Sizga qaysi xona kerak bo\x27ladi? (masalan: Standart, Deluxe, Suite yoki ro'yxatdagi raqam bilan)"
        push_message(user_id, "assistant", reply)
        await log_message(user_id, "incoming", user_message, reply)
        return reply

    # Start-over intent: user wants to begin a new booking
    if any(
        phrase in text_lower
        for phrase in [
            "xona kerak",
            "xona band",
            "xona band qilish",
            "xona bron",
            "bron qilish",
            "band qilish",
        ]
    ):
        BOOKING_DRAFT.pop(user_id, None)
        BOOKING_STORE.pop(user_id, None)
    
    print(f"[AI] User: {user_id}, Platform: {platform}")
    print(f"[AI] Message: {user_message}")
    print(f"[AI] Booking info extracted: {booking_info}")
    
    if booking_info is None:
        print(f"[AI] DEBUG: extract_booking_info returned None")

    if not booking_info and any(
        phrase in text_lower
        for phrase in [
            "qancha bor",
            "qanqa bor",
            "qanaqa bor",
            "qanaqa xonalar",
            "qanday xonalar bor",
            "qanday xonalar",
            "xonalar bor",
            "xonalar bormi",
            "xonalar",
            "xona narx",
            "narxlari",
            "narxlar",
            "tarif",
            "tariflar",
            "tariflari",
        ]
    ):
        rooms = await get_rooms(only_active=True)
        if rooms:
            lines = ["Marhamat, hozirda quyidagi xonalar mavjud:"]
            for idx, room in enumerate(rooms, start=1):
                price = f"{room['price']:,}".replace(",", " ")
                lines.append(
                    f"{idx}. {room['name']}: {price} so'm/kun | {room.get('description', '')} | {room.get('capacity', 1)} kishi | {room.get('quantity', 1)} ta"
                )
            lines.append("Qaysi xonani tanlaysiz? (nom yoki raqam bilan yozsangiz bo'ladi)")
            reply = "\n".join(lines)
        else:
            reply = "Hozircha faol xonalar yo'q. Agar xohlasangiz, kelish sanasini yozing - mavjudlikni tekshirib beraman."
        push_message(user_id, "assistant", reply)
        await log_message(user_id, "incoming", user_message, reply)
        return reply
    

    # "bo'sh xona" so'rovida sanalarni talab qilish
    if ("bo'sh xona" in text_lower) and not booking_info:
        reply = "Albatta, bo'sh xonalarni tekshirib beraman. Kelish va ketish sanalarini yozing. Masalan: 2026-04-10 2026-04-12"
        push_message(user_id, "assistant", reply)
        await log_message(user_id, "incoming", user_message, reply)
        return reply

    draft = BOOKING_DRAFT.get(user_id, {})
    if booking_info:
        # If we already have check-in and user sends a single date next,
        # treat it as check-out instead of overwriting check-in.
        if (
            booking_info.get("check_in")
            and not booking_info.get("check_out")
            and draft.get("check_in")
            and not draft.get("check_out")
        ):
            booking_info["check_out"] = booking_info["check_in"]
            booking_info["check_in"] = None
        draft = _merge_booking(draft, booking_info)
        BOOKING_DRAFT[user_id] = draft

    if draft:
        # If last step said "other date or room", handle explicit choice
        if draft.get("availability_needed"):
            has_room_update = bool(
                booking_info and (booking_info.get("room_type") or booking_info.get("room_choice_index"))
            )
            has_date_update = bool(
                booking_info and (booking_info.get("check_in") or booking_info.get("check_out"))
            )
            if has_room_update or has_date_update:
                draft.pop("availability_needed", None)
                draft.pop("available_rooms", None)
                BOOKING_DRAFT[user_id] = draft
            else:
                if "xona" in text_lower or "room" in text_lower:
                    draft["room_type"] = None
                    draft["room_choice_index"] = None
                    draft.pop("room_id", None)
                    draft.pop("availability_needed", None)
                    available_rooms = draft.pop("available_rooms", None) or []
                    BOOKING_DRAFT[user_id] = draft
                    if available_rooms:
                        lines = ["Mavjud xonalar:"]
                        for idx, room in enumerate(available_rooms, start=1):
                            price = f"{room.get('price', 0):,}".replace(",", " ")
                            available_count = room.get("available_count", 0)
                            lines.append(
                                f"{idx}. {room.get('name')} - {price} so'm/kun | {room.get('capacity', 1)} kishi | {available_count} ta"
                            )
                        lines.append("Qaysi xonani tanlaysiz? (nom yoki raqam bilan yozsangiz bo'ladi)")
                        reply = "\n".join(lines)
                    else:
                        reply = "Qaysi xona kerak bo'ladi? (masalan: Standart, Deluxe, Suite yoki ro'yxatdagi raqam bilan)"
                    push_message(user_id, "assistant", reply)
                    await log_message(user_id, "incoming", user_message, reply)
                    return reply
                if "sana" in text_lower or "date" in text_lower:
                    draft["check_in"] = None
                    draft["check_out"] = None
                    draft.pop("availability_needed", None)
                    draft.pop("available_rooms", None)
                    BOOKING_DRAFT[user_id] = draft
                    reply = "Kelish sanasini yuboring, iltimos (YYYY-MM-DD)."
                    push_message(user_id, "assistant", reply)
                    await log_message(user_id, "incoming", user_message, reply)
                    return reply

        # Prefill name/phone from DB for Telegram users to avoid extra prompts
        if user_id.startswith("tg_"):
            db_user = await get_user(user_id.replace("tg_", ""))
            if db_user:
                if not draft.get("name"):
                    first = db_user.get("first_name") or ""
                    last = db_user.get("last_name") or ""
                    full = (first + " " + last).strip()
                    if full:
                        draft["name"] = full
                        BOOKING_DRAFT[user_id] = draft
                if not draft.get("phone") and db_user.get("phone"):
                    draft["phone"] = db_user.get("phone")
                    BOOKING_DRAFT[user_id] = draft

        # If user sent a name only, accept it as name to avoid loops
        if not draft.get('name'):
            name_only = re.fullmatch(r'[A-Za-z]+(?:\s+[A-Za-z]+)?', user_message.strip())
            has_digits = bool(re.search(r'\d', user_message))
            if name_only and not has_digits:
                draft['name'] = user_message.strip().title()
                BOOKING_DRAFT[user_id] = draft

        missing = _next_missing_field(draft)

        # If we are waiting for guests, accept "2" or "2 kishi" forms
        if missing == "guests":
            text_norm = user_message.strip().lower()
            has_date_words = any(m in text_norm for m in ["yanvar","fevral","mart","aprel","may","iyun","iyul","avgust","sentabr","oktabr","noyabr","dekabr"])
            has_date_pattern = bool(re.search(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}", text_norm))
            explicit_guest = re.search(r"(\d+)\s*(kishi|odam|mehmon|kishilik)", text_norm)
            pure_number = re.fullmatch(r"\d+", text_norm)
            if explicit_guest:
                draft["guests"] = int(explicit_guest.group(1))
                BOOKING_DRAFT[user_id] = draft
                missing = _next_missing_field(draft)
            elif pure_number and not (has_date_words or has_date_pattern):
                draft["guests"] = int(text_norm)
                BOOKING_DRAFT[user_id] = draft
                missing = _next_missing_field(draft)
        # If user is sending a phone but format is wrong, show explicit error
        if missing == "phone":
            phone_candidate = user_message.strip()
            looks_like_phone = (
                '+998' in phone_candidate
                or phone_candidate.startswith('998')
                or re.fullmatch(r'\d{9,12}', phone_candidate)
            )
            if looks_like_phone:
                if not re.fullmatch(r'\+?998\d{9}', phone_candidate):
                    reply = "Telefon raqam notogri. Format: +998901234567"
                    push_message(user_id, "assistant", reply)
                    await log_message(user_id, "incoming", user_message, reply)
                    return reply
                if not phone_candidate.startswith('+'):
                    phone_candidate = '+' + phone_candidate
                draft['phone'] = phone_candidate
                BOOKING_DRAFT[user_id] = draft
                missing = _next_missing_field(draft)
        if missing == "name":
            reply = "Yordam berishim uchun ismingizni yozib yuboring, iltimos."
            push_message(user_id, "assistant", reply)
            await log_message(user_id, "incoming", user_message, reply)
            return reply
        if missing == "room":
            reply = "Qaysi xona kerak bo'ladi? (masalan: Standart, Deluxe, Suite yoki ro'yxatdagi raqam bilan)"
            push_message(user_id, "assistant", reply)
            await log_message(user_id, "incoming", user_message, reply)
            return reply
        if missing == "check_in":
            reply = "Kelish sanasini yuboring, iltimos (YYYY-MM-DD)."
            push_message(user_id, "assistant", reply)
            await log_message(user_id, "incoming", user_message, reply)
            return reply
        if missing == "check_out":
            reply = "Ketish sanasini ham yuboring, iltimos (YYYY-MM-DD)."
            push_message(user_id, "assistant", reply)
            await log_message(user_id, "incoming", user_message, reply)
            return reply
        if missing == "guests":
            reply = "Necha kishi bo'ladi? (raqam bilan yozing)"
            push_message(user_id, "assistant", reply)
            await log_message(user_id, "incoming", user_message, reply)
            return reply
        if missing == "phone":
            reply = "Telefon raqamingizni yuboring, iltimos (+998901234567)."
            push_message(user_id, "assistant", reply)
            await log_message(user_id, "incoming", user_message, reply)
            return reply

        room = None
        rooms_all = await get_rooms(only_active=True)

        if draft.get("room_choice_index"):
            idx = draft["room_choice_index"] - 1
            if 0 <= idx < len(rooms_all):
                room = rooms_all[idx]
        if not room and draft.get("room_type"):
            room = next(
                (
                    r for r in rooms_all
                    if draft["room_type"] in r["id"].lower()
                    or draft["room_type"] in r["name"].lower()
                ),
                None
            )
        if not room:
            # Try to match by room name text in the last user message
            for r in rooms_all:
                if r["name"].lower() in text_lower:
                    room = r
                    break

        if not room:
            reply = "Xona topilmadi. Iltimos, xona nomini yoki royxatdagi raqamni yozing."
            push_message(user_id, "assistant", reply)
            await log_message(user_id, "incoming", user_message, reply)
            return reply

        try:
            check_in = datetime.strptime(draft["check_in"], "%Y-%m-%d")
            check_out = datetime.strptime(draft["check_out"], "%Y-%m-%d")
        except Exception:
            reply = "Sana formati notogri. Format: YYYY-MM-DD."
            push_message(user_id, "assistant", reply)
            await log_message(user_id, "incoming", user_message, reply)
            return reply

        days = (check_out - check_in).days
        if days <= 0:
            reply = "Ketish sanasi kelish sanasidan keyin bolishi kerak."
            push_message(user_id, "assistant", reply)
            await log_message(user_id, "incoming", user_message, reply)
            return reply

        if int(draft["guests"]) > int(room.get("capacity", 1)):
            capacity = room.get("capacity", 1)
            draft["guests"] = None
            BOOKING_DRAFT[user_id] = draft
            reply = (
                f"{room['name']} sigimi {capacity} kishigacha. "
                "Katta xona tanlaysizmi yoki mehmonlar sonini kamaytirasizmi?"
            )
            push_message(user_id, "assistant", reply)
            await log_message(user_id, "incoming", user_message, reply)
            return reply

        available_rooms = await find_available_rooms(
            draft["check_in"],
            draft["check_out"],
            only_active=True
        )
        if room["id"] not in {r["id"] for r in available_rooms}:
            if available_rooms:
                room_names = ", ".join(
                    f"{r['name']} ({r.get('available_count', 0)} ta)"
                    for r in available_rooms
                )
                reply = (
                    "Tanlangan xona bu sanalarda band. "
                    f"Mavjud xonalar: {room_names}. "
                    "Xohlasangiz boshqa sana yoki xona tanlaymiz."
                )
                draft["availability_needed"] = True
                draft["available_rooms"] = available_rooms
                BOOKING_DRAFT[user_id] = draft
            else:
                reply = "Afsus, bu sanalarda bo'sh xona yo'q. Boshqa sana aytsangiz, tekshirib beraman."
                draft["availability_needed"] = True
                draft["available_rooms"] = []
                BOOKING_DRAFT[user_id] = draft
            push_message(user_id, "assistant", reply)
            await log_message(user_id, "incoming", user_message, reply)
            return reply

        total_price = room["price"] * days
        price_fmt = f"{total_price:,}".replace(",", " ")
        day_price_fmt = f"{room['price']:,}".replace(",", " ")

        order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        order_data = {
            "id": order_id,
            "user_id": user_id.replace("tg_", "").replace("ig_", ""),
            "room_id": room["id"],
            "room_name": room["name"],
            "check_in": draft["check_in"],
            "check_out": draft["check_out"],
            "guests": int(draft["guests"]),
            "total_price": total_price,
            "name": draft["name"],
            "phone": draft["phone"],
            "notes": "",
            "source": platform,
        }

        BOOKING_STORE[user_id] = order_data
        BOOKING_DRAFT.pop(user_id, None)
        print(f"[BOOKING] Stored: {order_id} for {user_id}")

        if platform == "telegram":
            reply = f"""<b>Broningiz qabul qilindi!</b>

Xona: <b>{room['name']}</b>
Kelish: {draft['check_in']}
Ketish: {draft['check_out']}
{days} kun | {day_price_fmt} so'm/kun
{draft['guests']} kishi
Jami: <b>{price_fmt} so'm</b>

{draft['name']}
{draft['phone']}

----------------------
Bronni tasdiqlash uchun: <b>Tasdiqlayman</b>
Rad etish uchun: <b>Rad etaman</b> deb yozing."""
        else:
            reply = f"""<b>Broningiz qabul qilindi!</b>

Xona: {room['name']}
Kelish: {draft['check_in']}
Ketish: {draft['check_out']}
{days} kun | {day_price_fmt} so'm/kun
{draft['guests']} kishi
Jami: {price_fmt} so'm

{draft['name']}
{draft['phone']}

----------------------
Bronni tasdiqlash uchun: <b>Tasdiqlayman</b>
Rad etish uchun: <b>Rad etaman</b> deb yozing."""

        push_message(user_id, "assistant", reply)
        await log_message(user_id, "incoming", user_message, reply)
        return reply

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

рџ"ћ Telefon: {hotel.get('phone', '+998773397171')}
рџ'¬ Telegram: @Marcopolohotel_1"""

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
рџ"Њ Sarlavha
Matn (3-5 jumla)
Narxlar albatta
рџ"ћ {hotel.get('phone', '+998773397171')} | {hotel.get('telegram', '@Marcopolohotel_1')}
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
вњ… BUYURTMA QABUL QILINDI!

в"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓ
рџЏЁ Xona: {order_data['room_name']}
рџ"… Kelish: {order_data['check_in']}
рџ"… Ketish: {order_data['check_out']}
рџ'Ґ Mehmonlar: {order_data['guests']} kishi
рџ'° Jami: {price_fmt} so'm

рџ'¤ Ism: {order_data['name']}
рџ"ћ Telefon: {order_data['phone']}
в"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓ

вЏі Operator tez orada siz bilan bog'lanadi!

рџ"ћ {hotel.get('phone', '+998773397171')}
"""


async def send_order_to_admins(bot, order_data: dict, admin_ids: list):
    hotel = await get_hotel()
    price_fmt = f"{order_data['total_price']:,}".replace(",", " ")
    
    hotel_address = hotel.get('address', "Do'mbirobod Naqqoshlik 121A")
    message = f"""
рџ"" <b>YANGI BRON!</b>

в"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓ
рџЏЁ Xona: <b>{order_data['room_name']}</b>
рџ"… {order_data['check_in']} в†' {order_data['check_out']}
рџ'Ґ {order_data['guests']} kishi
рџ'° <b>{price_fmt} so'm</b>

рџ'¤ {order_data['name']}
рџ"ћ {order_data['phone']}
в"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓв"Ѓ
рџ"Ќ Manzil: {hotel_address}
"""
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    phone_clean = order_data.get('phone', '').replace('tel:', '').strip()
    keyboard_buttons = [
        [InlineKeyboardButton(text="вњ… Tasdiqlash", callback_data=f"order_confirm_{order_data['id']}"),
         InlineKeyboardButton(text="вќЊ Bekor", callback_data=f"order_cancel_{order_data['id']}")]
    ]
    if phone_clean and phone_clean.startswith('+'):
        keyboard_buttons.append([InlineKeyboardButton(text="Qo'ng'iroq", url=f"tel:{phone_clean}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    for admin_id in admin_ids:
        try:
            await bot.send_message(int(admin_id), message, reply_markup=keyboard)
        except:
            pass

    # Also send to orders group if enabled
    if os.getenv("ORDERS_GROUP_ID"):
        try:
            await bot.send_message(int(os.getenv("ORDERS_GROUP_ID")), message)
        except:
            pass


def get_booking_data(user_id: str) -> dict | None:
    return BOOKING_STORE.get(str(user_id))


def clear_booking_data(user_id: str):
    BOOKING_STORE.pop(str(user_id), None)




