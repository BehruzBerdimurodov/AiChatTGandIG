"""
AI Handler - Professional AI yordamchi
Marco Polo Hotel uchun - Barcha savolga javob beradi
"""

import os
import re
import logging
from datetime import datetime
from openai import AsyncOpenAI
from config.database import (
    get_hotel, get_rooms, get_room, create_order,
    log_message, log_activity, register_user,
    get_admins, find_available_rooms, get_user
)

log = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Suhbat tarixi
_store: dict[str, list[dict]] = {}
MAX_HISTORY = 20

# Bron jarayoni
BOOKING_STORE: dict[str, dict] = {}   # Tasdiqlash kutayotganlar
BOOKING_DRAFT: dict[str, dict] = {}   # Bron jarayonidagilar

TELEGRAM_BOT_LINK = "https://t.me/MarcoPoloHotelBot"

# Bron so'rovini aniqlash uchun kalit so'zlar
BOOKING_INTENT_KEYWORDS = [
    "xona kerak", "xona bron", "xona band", "bron qil", "band qil",
    "xona olmoqchi", "xona reserv", "reservatsiya", "booking",
    "xona bos", "xona band qilmoqchi", "joy band", "joy kerak",
    "qo'nmoqchi", "tunash", "tunamo", "tunab",
    "bron qilmoqchi", "bron qilish", "band qilmoqchi",
    "xona olish", "joy olish", "xona band olish",
]

# Bron BEKOR qilish uchun aniq so'zlar (faqat kuchli signal)
BOOKING_CANCEL_KEYWORDS = [
    "bron bekor", "bekor qilish", "bron kerak emas",
    "rad etaman", "bron yo'q", "bron cancel",
    "bron toxtat", "kerak emas bron",
]


async def _build_system_prompt(user_platform: str = "telegram") -> str:
    """Kuchli system prompt — barcha savolga javob beradi"""
    hotel = await get_hotel()
    rooms = await get_rooms(only_active=True)

    room_lines = []
    for r in rooms:
        price = f"{r['price']:,}".replace(",", " ")
        room_lines.append(
            f"- {r['name']}: {price} so'm/kun | {r['description']} | "
            f"{r['capacity']} kishi sig'imi | {r.get('quantity', 1)} ta mavjud"
        )
    rooms_text = "\n".join(room_lines) if room_lines else "Hozircha xonalar ma'lumotlari yangilanmoqda"

    hotel_phone = hotel.get('phone', '+998773397171')
    hotel_phone2 = hotel.get('phone_2', '+998771577171')
    hotel_address = hotel.get('address', "Do'mbirobod Naqqoshlik 121A")
    hotel_telegram = hotel.get('telegram', '@Marcopolohotel_1')

    platform_note = ""
    if user_platform == "instagram":
        platform_note = "\nPlatforma: Instagram Direct. HTML teglari ishlatma, oddiy matn yoz."
    
    return f"""Sen Marco Polo Hotel ning juda ham e'tiborli, nihoyatda samimiy, xushmuomala va professional AI yordamchisisan.
Sening asosiy vazifang — foydalanuvchining BARCHA savollariga erinmasdan, 100% TO'LIQ, BATAFSIL va ILIQ javob berish. Mijoz doimo o'zini eng qadrdon mehmonday his qilishi kerak!{platform_note}

═══════════════════════════════════
MEHMONXONA MA'LUMOTLARI:
═══════════════════════════════════
Nomi: Marco Polo Hotel 🏩
Manzil: {hotel_address}, Toshkent, Chilonzor tumani
Asosiy telefon: {hotel_phone}
Qo'shimcha telefon: {hotel_phone2}
Telegram: {hotel_telegram}

XONALAR VA NARXLAR:
{rooms_text}

SOATLIK IJARA: 200,000 - 250,000 so'm (kelishuv asosida)

AFZALLIKLAR VA XIZMATLAR:
✅ Maxfiylik 100% kafolatlanadi
✅ ZAGS talab qilinmaydi — 1 ta pasport yetarli
✅ Spa salon va dam olish maskani
✅ Lounge bar
✅ SMART TV barcha xonalarda
✅ Tezkor Wi-Fi
✅ Konditsioner (isitish/sovutish)
✅ Sutkalik qo'riqlash
✅ Qulay to'xtash joyi
✅ 24/7 qabulxona xizmati

═══════════════════════════════════
JAVOB BERISH QO'LLANMASI:
═══════════════════════════════════

1. 100% SAMIMIY VA BATAFSIL JAVOB BER:
   - Mehmonxona haqida har qanday savol (narx, manzil, joylashuv, xizmatlar) bo'lsa — erinmasdan, batafsil va eng chiroyli so'zlar bilan javob ber.
   - Hech qachon qisqa javob qaytarma, doim mijozni hurmat bilan "Siz" deb murojaat qil.
   - "Bilmayman" dema — doim alternativ yechim taklif qil yoki aloqa raqamini ber: {hotel_phone}.
   - Salomlashsa — eng issiq va chiroyli so'zlar bilan kutib ol. O'zingni mehmonxona xodimi sifatida his qil.

2. BRON QILISH SO'RALSA:
   Quyidagi tartibda juda muloyimlik bilan ma'lumot so'ra (faqat yetishmayotganlarini birma-bir):
   a) Ism (agar noma'lum bo'lsa)
   b) Qaysi xona (agar aytilmagan bo'lsa)
   c) Kelish sanasi
   d) Ketish sanasi
   e) Necha kishi mehmonga kelishi
   f) Telefon raqami

3. TILLAR VA MUOMALA MADANIYATI:
   - Mijoz qaysi tilda yozsa (O'zbek, Rus, Ingliz), o'sha tilda mukammal va xatosiz yoz.
   - Savollar ko'p bo'lsa barchasiga bittalab javob ber. Hech bir e'tiborsiz qoldirilmasin.

4. USLUB:
   - O'ta do'stona, insoniylik hissi bilan (robotdek emas).
   - Javoblarni uzun bo'lsa chiroyli formatda (nuqtali ro'yxatlar) berib o't.
   - Matn oxiriga doim qo'shimcha yordam kerakmi deb muloyim so'ra.
   - Mos va o'rinli emojilardan chiroyli foydalan.

═══════════════════════════════════
MUHIM: Har bir so'zingda samimiylik sezilsin. Maqsad — bot orqali muloqot qilgan insonga ajoyib kayfiyat ulashish va mehmonxonaga kelish ishtiyoqini uyg'otish!
═══════════════════════════════════"""


def _is_booking_intent(text: str) -> bool:
    """Foydalanuvchi bron qilmoqchi ekanligini aniqlash"""
    t = text.lower().strip()
    return any(kw in t for kw in BOOKING_INTENT_KEYWORDS)


def _is_cancel_intent(text: str) -> bool:
    """
    Faqat ANIQ bron bekor qilish so'rovini aniqlash.
    'yo\'q', 'boshqa', 'bekor' kabi oddiy so'zlarni sezmasligi kerak.
    """
    t = text.lower().strip()
    # Faqat kuchli signal beruvchi birikmalar
    return any(kw in t for kw in BOOKING_CANCEL_KEYWORDS)


def _is_greeting(text: str) -> bool:
    t = text.lower().strip()
    greetings = [
        "salom", "assalomu alaykum", "assalom", "hello", "hi",
        "hey", "привет", "здравствуйте", "xayr", "qalaysiz",
    ]
    return any(t.startswith(g) or t == g for g in greetings)


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

    # Ism
    name_patterns = [
        r'ism(?:i|im|lar|larim)?[:\s]+([a-zA-ZА-Яа-яЁёа-яÀ-ÿ\s]+?)(?:,|\.|$)',
        r'ism\s*[:\-]?\s*([a-zA-ZА-Яа-яЁёА-ЯÀ-ÿ\s]+?)(?:,|\n|$)',
        r'name\s*[:\-]?\s*([a-zA-Z\s]+?)(?:,|\n|$)',
        r'^([a-zA-ZА-Яа-яЁё]{2,20}(?:\s+[a-zA-ZА-Яа-яЁё]{2,20})?)$',
    ]
    for pattern in name_patterns:
        name_match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if name_match:
            candidate = name_match.group(1).strip()
            # Bo'sh so'zlarni tozalash
            candidate = re.sub(r'\s+', ' ', candidate).strip()
            if 2 < len(candidate) < 50:
                name = candidate.title()
                break

    # Telefon
    phone_match = re.search(r'\+?998[\d]{9}', text)
    if phone_match:
        phone = phone_match.group(0)
        if not phone.startswith('+'):
            phone = '+' + phone

    # Sanalar — oylar nomi bilan
    month_map = {
        'yanvar': '01', 'yanvarь': '01',
        'fevral': '02', 'fevralь': '02',
        'mart': '03',
        'aprel': '04',
        'may': '05',
        'iyun': '06', 'iyunь': '06',
        'iyul': '07', 'iyulь': '07',
        'avgust': '08',
        'sentabr': '09', 'sentyabr': '09', 'sentябр': '09',
        'oktabr': '10', 'oktyabr': '10',
        'noyabr': '11',
        'dekabr': '12',
    }

    year = datetime.now().year
    dates_found = []

    for month_name, month_num in month_map.items():
        pattern = rf'(\d{{1,2}})\s*{month_name}(?:dan|gatacha|ga|da)?'
        matches = re.findall(pattern, text_lower)
        for m in matches:
            dates_found.append(f"{year}-{month_num}-{m.zfill(2)}")

    if len(dates_found) >= 1:
        check_in = dates_found[0]
    if len(dates_found) >= 2:
        check_out = dates_found[1]

    # YYYY-MM-DD formatidagi sanalar
    if not check_in or not check_out:
        date_std = re.findall(r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})', text)
        if len(date_std) >= 1 and not check_in:
            check_in = f"{date_std[0][0]}-{date_std[0][1].zfill(2)}-{date_std[0][2].zfill(2)}"
        if len(date_std) >= 2 and not check_out:
            check_out = f"{date_std[1][0]}-{date_std[1][1].zfill(2)}-{date_std[1][2].zfill(2)}"

    # DD-MM-YYYY formatidagi sanalar
    if not check_in or not check_out:
        date_dmy = re.findall(r'(\d{1,2})[-./](\d{1,2})[-./](\d{2,4})', text)
        for d, m, y in date_dmy:
            if len(y) == 2:
                y = "20" + y
            formatted = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
            if not check_in:
                check_in = formatted
            elif not check_out:
                check_out = formatted

    # Mehmonlar soni
    guests_match = re.search(
        r'(\d+)\s*(?:kishi|odam|mehmon|kishilik|nafar|ta kishi)',
        text_lower
    )
    if guests_match:
        guests = int(guests_match.group(1))

    # Xona turi
    room_keywords = [
        ('premium', 'premium'),
        ('deluxe', 'deluxe'),
        ('suite', 'suite'),
        ('suit', 'suite'),
        ('люкс', 'suite'),
        ('vip', 'vip'),
        ('family', 'family'),
        ('oilaviy', 'family'),
        ('standart', 'standart'),
        ('standard', 'standart'),
        ('econom', 'standart'),
    ]
    for keyword, room_id in room_keywords:
        if keyword in text_lower:
            room_type = room_id
            break

    # Raqam bilan xona tanlash (1, 2, 3 ...)
    room_index_match = re.search(
        r'\b([1-9])\s*(?:-?\s*(?:xona|raqam|variant|tanladim|maqul|kerak|bo\'ladi))?\b',
        text_lower
    )
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


def _missing_question(missing: str) -> str:
    questions = {
        "name": "Ismingizni yozib yuboring, iltimos 😊",
        "room": "Qaysi xona kerak? Xona nomini yoki ro'yxatdan raqamini yozing.",
        "check_in": "Kelish sanangizni yuboring (masalan: 2026-05-10).",
        "check_out": "Ketish sanangizni yuboring (masalan: 2026-05-12).",
        "guests": "Necha kishi bo'ladi? (raqam bilan yozing, masalan: 2)",
        "phone": "Telefon raqamingizni yuboring (+998901234567).",
    }
    return questions.get(missing, "")


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


async def _ai_reply(user_id: str, user_message: str, platform: str = "telegram") -> str:
    """OpenAI orqali javob olish"""
    history = get_history(user_id)
    system_prompt = await _build_system_prompt(platform)

    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": user_message},
    ]

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=700,
            temperature=0.75,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        import traceback
        log.error(f"[AI ERROR OPENAI] {e}\n{traceback.format_exc()}")
        hotel = await get_hotel()
        return (
            f"Kechirasiz, hozir texnik muammo bor. "
            f"Iltimos, to'g'ridan-to'g'ri bog'laning:\n"
            f"📞 {hotel.get('phone', '+998773397171')}"
        )


async def _handle_booking_flow(
    user_id: str,
    user_message: str,
    platform: str,
    booking_info: dict | None,
) -> str | None:
    """
    Faqat foydalanuvchi bron qilmoqchi bo'lganda ishlaydigan funksiya.
    Agar bron jarayoni aktiv bo'lmasa va foydalanuvchi bron so'ramasa — None qaytaradi.
    """
    text_lower = user_message.lower().strip()
    draft = BOOKING_DRAFT.get(user_id, {})

    # Agar draft ACTIVE bo'lmasa va foydalanuvchi bron so'ramasa — chiqib ket
    if not draft and not _is_booking_intent(user_message):
        return None

    # Bron bekor qilish
    if _is_cancel_intent(user_message) and draft:
        BOOKING_DRAFT.pop(user_id, None)
        BOOKING_STORE.pop(user_id, None)
        return "Bron jarayoni bekor qilindi. Boshqa savol bo'lsa, yozing! 😊"

    # Yangi bron — draft tozalash
    if _is_booking_intent(user_message) and not draft:
        BOOKING_DRAFT.pop(user_id, None)
        BOOKING_STORE.pop(user_id, None)
        draft = {}

    # Booking info ni draft ga qo'shish
    if booking_info:
        # Agar check_in bor, lekin check_out yo'q bo'lsa va yangi sana kelsa
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

    # Telegram foydalanuvchi uchun DB dan ma'lumot to'ldirish
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

    # Ism faqat harflardan iborat bo'lsa qabul qil
    if not draft.get("name"):
        name_only = re.fullmatch(
            r'[A-Za-zА-Яа-яЁё]+(?:\s+[A-Za-zА-Яа-яЁё]+)?',
            user_message.strip()
        )
        if name_only and not re.search(r'\d', user_message):
            draft["name"] = user_message.strip().title()
            BOOKING_DRAFT[user_id] = draft

    # Mehmonlar soni — sof raqam bo'lsa
    missing = _next_missing_field(draft)
    if missing == "guests":
        text_norm = user_message.strip().lower()
        date_words = [
            "yanvar", "fevral", "mart", "aprel", "may", "iyun",
            "iyul", "avgust", "sentabr", "oktyabr", "noyabr", "dekabr"
        ]
        has_date = any(m in text_norm for m in date_words) or bool(
            re.search(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}", text_norm)
        )
        explicit_guest = re.search(r"(\d+)\s*(kishi|odam|mehmon|nafar|ta kishi)", text_norm)
        pure_number = re.fullmatch(r"\d+", text_norm)
        if explicit_guest:
            draft["guests"] = int(explicit_guest.group(1))
            BOOKING_DRAFT[user_id] = draft
            missing = _next_missing_field(draft)
        elif pure_number and not has_date:
            draft["guests"] = int(text_norm)
            BOOKING_DRAFT[user_id] = draft
            missing = _next_missing_field(draft)

    # Telefon — noto'g'ri format
    if missing == "phone":
        phone_candidate = user_message.strip()
        looks_like_phone = (
            '+998' in phone_candidate
            or phone_candidate.startswith('998')
            or re.fullmatch(r'\d{9,12}', phone_candidate.replace(" ", ""))
        )
        if looks_like_phone:
            clean = phone_candidate.replace(" ", "").replace("-", "")
            if not clean.startswith('+'):
                clean = '+' + clean
            if re.fullmatch(r'\+998\d{9}', clean):
                draft['phone'] = clean
                BOOKING_DRAFT[user_id] = draft
                missing = _next_missing_field(draft)
            else:
                return "📞 Telefon raqam formati noto'g'ri. Iltimos, quyidagi formatda yozing: +998901234567"

    # Keyingi bo'sh maydon bo'lsa — savol ber
    missing = _next_missing_field(draft)
    if missing:
        # Xona ro'yxatini ko'rsatish
        if missing == "room":
            rooms = await get_rooms(only_active=True)
            if rooms:
                lines = ["Qaysi xonani tanlaysiz?\n"]
                for idx, room in enumerate(rooms, start=1):
                    price = f"{room['price']:,}".replace(",", " ")
                    lines.append(
                        f"{idx}. 🛏 {room['name']} — {price} so'm/kun "
                        f"| {room.get('description', '')} "
                        f"| {room.get('capacity', 1)} kishigacha"
                    )
                lines.append("\nNom yoki raqam bilan yozing.")
                return "\n".join(lines)
        return _missing_question(missing)

    # Barcha ma'lumot to'liq — xona topish
    rooms_all = await get_rooms(only_active=True)
    room = None

    if draft.get("room_choice_index"):
        idx = draft["room_choice_index"] - 1
        if 0 <= idx < len(rooms_all):
            room = rooms_all[idx]

    if not room and draft.get("room_type"):
        room = next(
            (
                r for r in rooms_all
                if draft["room_type"].lower() in r["id"].lower()
                or draft["room_type"].lower() in r["name"].lower()
            ),
            None,
        )

    if not room:
        for r in rooms_all:
            if r["name"].lower() in text_lower:
                room = r
                break

    if not room:
        BOOKING_DRAFT[user_id] = draft
        lines = ["Xona topilmadi. Qaysi xona kerak?\n"]
        for idx, r in enumerate(rooms_all, start=1):
            price = f"{r['price']:,}".replace(",", " ")
            lines.append(f"{idx}. {r['name']} — {price} so'm/kun")
        return "\n".join(lines)

    # Sanani tekshirish
    try:
        check_in_dt = datetime.strptime(draft["check_in"], "%Y-%m-%d")
        check_out_dt = datetime.strptime(draft["check_out"], "%Y-%m-%d")
    except Exception:
        draft["check_in"] = None
        draft["check_out"] = None
        BOOKING_DRAFT[user_id] = draft
        return "Sana formati noto'g'ri. Iltimos, YYYY-MM-DD formatida yozing. Masalan: 2026-05-10"

    days = (check_out_dt - check_in_dt).days
    if days <= 0:
        draft["check_out"] = None
        BOOKING_DRAFT[user_id] = draft
        return "❗ Ketish sanasi kelish sanasidan keyin bo'lishi kerak. Ketish sanasini qayta yuboring."

    # Sig'im tekshirish
    if int(draft["guests"]) > int(room.get("capacity", 1)):
        capacity = room.get("capacity", 1)
        draft["guests"] = None
        BOOKING_DRAFT[user_id] = draft
        return (
            f"⚠️ {room['name']} xonasi {capacity} kishigacha. "
            f"Boshqa xona tanlaysizmi yoki mehmonlar sonini kamaytirasizmi?"
        )

    # Mavjudlik tekshirish
    available_rooms = await find_available_rooms(
        draft["check_in"], draft["check_out"], only_active=True
    )
    if room["id"] not in {r["id"] for r in available_rooms}:
        if available_rooms:
            room_names = "\n".join(
                f"- {r['name']} ({r.get('available_count', 0)} ta)"
                for r in available_rooms
            )
            draft["availability_needed"] = True
            draft["available_rooms"] = available_rooms
            BOOKING_DRAFT[user_id] = draft
            return (
                f"😔 Tanlagan xonangiz bu sanalarda band.\n\n"
                f"Mavjud xonalar:\n{room_names}\n\n"
                f"Boshqa xona tanlaysizmi?"
            )
        else:
            draft["check_in"] = None
            draft["check_out"] = None
            draft.pop("availability_needed", None)
            BOOKING_DRAFT[user_id] = draft
            return (
                "😔 Bu sanalarda bo'sh xona yo'q. "
                "Boshqa sanalarni yozing, tekshirib beraman."
            )

    # Narx hisoblash
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
    log.info(f"[BOOKING] Stored: {order_id} for {user_id}")

    if platform == "telegram":
        return (
            f"<b>✅ Broningiz qabul qilindi!</b>\n\n"
            f"🏨 Xona: <b>{room['name']}</b>\n"
            f"📅 Kelish: {draft['check_in']}\n"
            f"📅 Ketish: {draft['check_out']}\n"
            f"🕐 {days} kun × {day_price_fmt} so'm/kun\n"
            f"👥 {draft['guests']} kishi\n"
            f"💰 Jami: <b>{price_fmt} so'm</b>\n\n"
            f"👤 {draft['name']}\n"
            f"📞 {draft['phone']}\n\n"
            f"──────────────────────\n"
            f"✅ Tasdiqlash uchun: <b>Tasdiqlayman</b>\n"
            f"❌ Bekor qilish uchun: <b>Bekor</b> deb yozing."
        )
    else:
        return (
            f"✅ Broningiz qabul qilindi!\n\n"
            f"🏨 Xona: {room['name']}\n"
            f"📅 Kelish: {draft['check_in']}\n"
            f"📅 Ketish: {draft['check_out']}\n"
            f"🕐 {days} kun | {day_price_fmt} so'm/kun\n"
            f"👥 {draft['guests']} kishi\n"
            f"💰 Jami: {price_fmt} so'm\n\n"
            f"👤 {draft['name']}\n"
            f"📞 {draft['phone']}\n\n"
            f"──────────────────────\n"
            f"Tasdiqlash uchun: Tasdiqlayman\n"
            f"Bekor qilish uchun: Bekor deb yozing."
        )


async def get_ai_response(
    user_id: str,
    user_message: str,
    user_name: str = "Mehmon",
    platform: str = "telegram",
) -> str:
    """
    Asosiy AI javob funksiyasi.
    - Bron jarayoni aktiv bo'lsa → bron jarayoni
    - Bron so'rasa → bron jarayoni
    - Boshqa barcha savollar → OpenAI
    """
    text_lower = user_message.lower().strip()
    push_message(user_id, "user", user_message)

    log.info(f"[AI] User={user_id} Platform={platform} Msg={user_message[:80]}")

    # Salomlashish — bron drafti yo'q bo'lsa AI ga oddiy salomlash
    if _is_greeting(user_message) and user_id not in BOOKING_DRAFT:
        BOOKING_STORE.pop(user_id, None)
        reply = await _ai_reply(user_id, user_message, platform)
        push_message(user_id, "assistant", reply)
        await log_message(user_id, "incoming", user_message, reply)
        return reply

    # Bron jarayoni aktiv bo'lsa yoki bron so'rasa
    booking_info = extract_booking_info(user_message) if (
        user_id in BOOKING_DRAFT or _is_booking_intent(user_message)
    ) else None

    booking_reply = await _handle_booking_flow(
        user_id, user_message, platform, booking_info
    )

    if booking_reply is not None:
        push_message(user_id, "assistant", booking_reply)
        await log_message(user_id, "incoming", user_message, booking_reply)
        return booking_reply

    # Barcha boshqa savollar — OpenAI ga yuborish
    reply = await _ai_reply(user_id, user_message, platform)

    push_message(user_id, "assistant", reply)
    await log_message(user_id, "incoming", user_message, reply)
    await log_activity(user_id, "chat", user_message[:50])

    return reply


# ──────────────────────────────────────────────────
# Yordamchi funksiyalar
# ──────────────────────────────────────────────────

def get_booking_data(user_id: str) -> dict | None:
    return BOOKING_STORE.get(str(user_id))


def clear_booking_data(user_id: str):
    BOOKING_STORE.pop(str(user_id), None)


async def generate_post(topic: str, hotel_name: str) -> str:
    hotel = await get_hotel()
    prompt = (
        f"Marco Polo Hotel uchun Telegram post yoz:\n"
        f"Mavzu: {topic}\n"
        f"Format: Sarlavha, Matn (3-5 jumla), Narxlar, "
        f"📞 {hotel.get('phone', '+998773397171')} | {hotel.get('telegram', '@Marcopolohotel_1')}"
    )
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
    return (
        f"✅ BUYURTMA QABUL QILINDI!\n\n"
        f"════════════════════════\n"
        f"🏨 Xona: {order_data['room_name']}\n"
        f"📅 Kelish: {order_data['check_in']}\n"
        f"📅 Ketish: {order_data['check_out']}\n"
        f"👥 Mehmonlar: {order_data['guests']} kishi\n"
        f"💰 Jami: {price_fmt} so'm\n\n"
        f"👤 Ism: {order_data['name']}\n"
        f"📞 Telefon: {order_data['phone']}\n"
        f"════════════════════════\n\n"
        f"⏱ Operator tez orada siz bilan bog'lanadi!\n\n"
        f"📞 {hotel.get('phone', '+998773397171')}"
    )


async def send_order_to_admins(bot, order_data: dict, admin_ids: list):
    hotel = await get_hotel()
    price_fmt = f"{order_data['total_price']:,}".replace(",", " ")
    hotel_address = hotel.get('address', "Do'mbirobod Naqqoshlik 121A")

    source_label = order_data.get('source', 'telegram').upper()
    message = (
        f"🔔 <b>YANGI BRON! [{source_label}]</b>\n\n"
        f"════════════════════════\n"
        f"🏨 Xona: <b>{order_data['room_name']}</b>\n"
        f"📅 {order_data['check_in']} → {order_data['check_out']}\n"
        f"👥 {order_data['guests']} kishi\n"
        f"💰 <b>{price_fmt} so'm</b>\n\n"
        f"👤 {order_data['name']}\n"
        f"📞 {order_data['phone']}\n"
        f"════════════════════════\n"
        f"📍 Manzil: {hotel_address}"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    phone_clean = order_data.get('phone', '').replace('tel:', '').strip()
    keyboard_buttons = [
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"order_confirm_{order_data['id']}"),
            InlineKeyboardButton(text="❌ Bekor", callback_data=f"order_cancel_{order_data['id']}"),
        ]
    ]
    if phone_clean and phone_clean.startswith('+'):
        keyboard_buttons.append(
            [InlineKeyboardButton(text="📞 Qo'ng'iroq", url=f"tel:{phone_clean}")]
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    for admin_id in admin_ids:
        try:
            await bot.send_message(int(admin_id), message, reply_markup=keyboard)
        except Exception as e:
            log.error(f"Admin notify error ({admin_id}): {e}")

    # Guruhga ham yuborish
    if os.getenv("ORDERS_GROUP_ID"):
        try:
            await bot.send_message(int(os.getenv("ORDERS_GROUP_ID")), message)
        except Exception as e:
            log.error(f"Group notify error: {e}")
