"""
AI Handler - Marco Polo Hotel
100% ishlaydigan bron jarayoni + AI chat
"""

import os
import re
import json
import logging
from datetime import datetime
from openai import AsyncOpenAI
from config.database import (
    get_hotel,
    get_rooms,
    get_room,
    create_order,
    log_message,
    log_activity,
    register_user,
    get_admins,
    find_available_rooms,
    get_user,
    get_room_photos,
    get_hotel_location,
)

log = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        key = os.getenv("OPENAI_API_KEY", "")
        if not key or "dummy" in key or not key.strip():
            raise ValueError("OPENAI_API_KEY yo'q yoki noto'g'ri!")
        _client = AsyncOpenAI(api_key=key)
    return _client


MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

PENDING_ROOM_PHOTOS: dict[str, dict] = {}
PENDING_LOCATION: dict[str, dict] = {}

# Suhbat tarixi (xotirada)
_store: dict[str, list[dict]] = {}
MAX_HISTORY = 20

# Bron holatlari
BOOKING_STORE: dict[str, dict] = {}  # Tasdiqlash kutayotganlar
BOOKING_DRAFT: dict[str, dict] = {}  # To'ldirilayotgan bron

BOOKING_INTENT_KEYWORDS = [
    "xona kerak",
    "xona bron",
    "xona band",
    "bron qil",
    "band qil",
    "xona olmoqchi",
    "xona reserv",
    "reservatsiya",
    "booking",
    "joy band",
    "joy kerak",
    "qo'nmoqchi",
    "tunash",
    "bron qilmoqchi",
    "bron qilish",
    "band qilmoqchi",
    "xona olish",
    "joy olish",
]

BOOKING_CANCEL_KEYWORDS = [
    "bekor",
    "bekor qil",
    "bekor qiling",
    "bron bekor",
    "bekor qilish",
    "otkaz",
    "otkaz qil",
    "otkazish",
    "bron kerak emas",
    "rad etaman",
    "bron cancel",
    "bron toxtat",
]

GREETING_KEYWORDS = {
    "salom",
    "assalomu alaykum",
    "assalom",
    "hello",
    "hi",
    "privet",
    "alaykum",
}

BOOKING_CONTINUE_KEYWORDS = {
    "davom",
    "davom et",
    "davom etamiz",
    "continue",
    "ok",
    "xo'p",
    "hop",
    "ha",
}

ROOM_RECOMMENDATION_KEYWORDS = {
    "tavsiya",
    "qaysi",
    "qaysinisi",
    "maslahat",
    "recommended",
    "recommend",
    "which one",
    "qanaqasi",
}

ROOM_INFO_KEYWORDS = {
    "rasm",
    "foto",
    "photo",
    "narx",
    "qancha",
    "price",
    "qulaylik",
    "amenities",
    "xona haqida",
}

# ──────────────────────────────────────────────
# SANA PARSE
# ──────────────────────────────────────────────

MONTH_MAP = {
    "yanvar": 1,
    "yanvarь": 1,
    "january": 1,
    "jan": 1,
    "fevral": 2,
    "fevralь": 2,
    "february": 2,
    "feb": 2,
    "mart": 3,
    "march": 3,
    "mar": 3,
    "aprel": 4,
    "april": 4,
    "apr": 4,
    "may": 5,
    "iyun": 6,
    "iyunь": 6,
    "june": 6,
    "jun": 6,
    "iyul": 7,
    "iyulь": 7,
    "july": 7,
    "jul": 7,
    "avgust": 8,
    "august": 8,
    "aug": 8,
    "sentabr": 9,
    "sentyabr": 9,
    "september": 9,
    "sep": 9,
    "oktyabr": 10,
    "october": 10,
    "oct": 10,
    "noyabr": 11,
    "november": 11,
    "nov": 11,
    "dekabr": 12,
    "december": 12,
    "dec": 12,
}


def _normalize_date(
    year: int,
    month: int,
    day: int,
    today: datetime,
    allow_rollover: bool = False,
) -> str | None:
    """Sana qismlarini tekshiradi va YYYY-MM-DD qaytaradi."""
    try:
        dt = datetime(year, month, day)
    except ValueError:
        return None

    # Foydalanuvchi yil kiritmasa, o'tib ketgan sanani keyingi yilga o'tkazamiz
    if allow_rollover and year == today.year and dt.date() < today.date():
        try:
            dt = datetime(year + 1, month, day)
        except ValueError:
            return None
    return dt.strftime("%Y-%m-%d")


def _parse_date(text: str) -> str | None:
    """
    Matndan sanani YYYY-MM-DD formatida qaytaradi.
    'mart 12', '12 mart', '2026-03-12', '12.03', '12/03' kabi formatlarni qabul qiladi.
    """
    text = text.strip().lower()
    today = datetime.now()
    year = today.year

    # YYYY-MM-DD
    m = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", text)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return _normalize_date(year, month, day, today, allow_rollover=False)

    # DD.MM.YYYY yoki DD/MM/YYYY
    m = re.search(r"(\d{1,2})[-./](\d{1,2})[-./](\d{4})", text)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return _normalize_date(year, month, day, today, allow_rollover=False)

    # DD.MM (yil yo'q)
    m = re.search(r"\b(\d{1,2})[-./](\d{1,2})\b", text)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        return _normalize_date(year, month, day, today, allow_rollover=True)

    # "12 mart", "mart 12", "12-mart"
    for month_name, month_num in MONTH_MAP.items():
        # "12 mart" yoki "12-mart"
        m = re.search(rf"(\d{{1,2}})\s*[-]?\s*{month_name}", text)
        if m:
            day = int(m.group(1))
            normalized = _normalize_date(year, month_num, day, today, allow_rollover=True)
            if normalized:
                return normalized
        # "mart 12"
        m = re.search(rf"{month_name}\s*[-]?\s*(\d{{1,2}})", text)
        if m:
            day = int(m.group(1))
            normalized = _normalize_date(year, month_num, day, today, allow_rollover=True)
            if normalized:
                return normalized

    return None


# ──────────────────────────────────────────────
# SYSTEM PROMPT
# ──────────────────────────────────────────────


async def _build_system_prompt(platform: str = "telegram") -> str:
    hotel = await get_hotel()
    rooms = await get_rooms(only_active=True)
    loc = await get_hotel_location()

    room_lines = []
    room_facts = []
    for r in rooms:
        price = f"{r['price']:,}".replace(",", " ")
        amenities = (r.get("amenities") or "").replace("|", ", ")
        room_numbers = r.get("room_numbers", "")
        room_lines.append(
            f"- {r['name']}: {price} so'm/kun | {r['description']} | "
            f"{r.get('capacity', 2)} kishi | {r.get('quantity', 1)} ta mavjud"
            f"{f' | Qulayliklar: {amenities}' if amenities else ''}"
            f"{f' | Raqamlar: {room_numbers}' if room_numbers else ''}"
        )
        room_facts.append(
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "price_per_day": r.get("price"),
                "capacity": r.get("capacity"),
                "quantity": r.get("quantity"),
                "description": r.get("description"),
                "amenities": r.get("amenities"),
                "room_numbers": r.get("room_numbers"),
            }
        )
    rooms_text = "\n".join(room_lines) if room_lines else "Xonalar yangilanmoqda"
    room_facts_json = json.dumps(room_facts, ensure_ascii=False)

    hotel_phone = hotel.get("phone", "+998773397171")
    hotel_address = hotel.get("address", "Do'mbirobod Naqqoshlik 121A")
    hotel_telegram = hotel.get("telegram", "@Marcopolohotel_1")
    hotel_instagram = hotel.get("instagram", "")
    hotel_about = hotel.get("about", "")
    bugun = datetime.now().strftime("%Y-%m-%d, %A")

    loc_info = ""
    if loc:
        loc_info = f"\n📍 Lokatsiya: {loc[0]}, {loc[1]}"

    platform_note = ""
    if platform == "instagram":
        platform_note = "\nPlatforma: Instagram. HTML teglarsiz, oddiy matn yoz."

    return f"""Sen Marco Polo Hotel ning samimiy va professional AI yordamchisissan.{platform_note}
Bugun: {bugun}

MEHMONXONA:
Nomi: Marco Polo Hotel
Manzil: {hotel_address}, Toshkent
Telefon: {hotel_phone}
Telegram: {hotel_telegram}{loc_info}
Instagram: {hotel_instagram or "mavjud emas"}
Qo'shimcha ma'lumot: {hotel_about or "Admin paneldagi so'nggi ma'lumotlardan foydalan"}

XONALAR:
{rooms_text}

XONALAR_JSON (aniq faktlar, javobda shu ma'lumotni asos qilib ol):
{room_facts_json}

SOATLIK IJARA: 200 000 - 250 000 so'm

XIZMATLAR: Maxfiylik 100%, ZAGS talab yo'q (1 pasport), Spa, Lounge bar, SMART TV, Wi-Fi, Konditsioner, 24/7 qabulxona, Xavfsiz avto to'xtash joyi

QO'LLANMA:
- Har qanday savol bo'lsa to'liq va iliq javob ber
- Mijozga "Siz" deb murojaat qil
- Rus, O'zbek, Ingliz tillarida javob ber
- Faqat oddiy matn yoz, markdown ishlatma (** yoki __ yo'q)
- Bron so'rasa men o'zim boshqaraman, sen shunchaki suhbatni davom ettir
- Telefon: {hotel_phone}
- Agar foydalanuvchi xona rasmini so'rasa, FAQAT shu buyruqni yoz (boshqa hech narsa qo'shma): SEND_ROOM_PHOTOS:xona_nomi — masalan: SEND_ROOM_PHOTOS:Standart
- Agar foydalanuvchi lokatsiya/manzil/joylashuv/location so'rasa, FAQAT shu buyruqni yoz: SEND_LOCATION
- Bu buyruqlarni boshqa matn bilan ARALASHTIRIM — faqat alohida yoz"""


# ──────────────────────────────────────────────
# XOTIRANI BOSHQARISH
# ──────────────────────────────────────────────


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


# ──────────────────────────────────────────────
# AI JAVOB
# ──────────────────────────────────────────────


async def _ai_reply(
    user_id: str,
    user_message: str,
    platform: str = "telegram",
    extra_instruction: str = "",
) -> str:
    history = get_history(user_id)
    system = await _build_system_prompt(platform)
    if extra_instruction:
        system += f"\n\nQO'SHIMCHA: {extra_instruction}"

    messages = [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": user_message},
    ]

    try:
        client = get_openai_client()
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=600,
            temperature=0.7,
        )
        text = resp.choices[0].message.content.strip()
        # Markdown tozalash — bold/italic belgilarini olib tashlash
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"_(.+?)_", r"\1", text)
        return text
    except Exception as e:
        log.error(f"[AI ERROR] {e}")
        hotel = await get_hotel()
        return f"Kechirasiz, texnik muammo. Iltimos, to'g'ridan-to'g'ri bog'laning:\n📞 {hotel.get('phone', '+998773397171')}"


# ──────────────────────────────────────────────
# BRON JARAYONI YORDAMCHILARI
# ──────────────────────────────────────────────


def _is_booking_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(kw in t for kw in BOOKING_INTENT_KEYWORDS)


def _is_cancel_intent(text: str) -> bool:
    t = text.lower().strip()
    return any(kw in t for kw in BOOKING_CANCEL_KEYWORDS)


def _next_missing(draft: dict) -> str | None:
    """Qaysi maydon yetishmayapti"""
    if not draft.get("room_id"):
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


def _format_room_list(rooms: list) -> str:
    lines = ["Qaysi xonani tanlaysiz?\n"]
    for i, r in enumerate(rooms, 1):
        price = f"{r['price']:,}".replace(",", " ")
        lines.append(
            f"{i}. {r['name']} — {price} so'm/kun "
            f"| {r.get('description', '')} "
            f"| {r.get('capacity', 2)} kishigacha"
        )
    lines.append("\nXona nomini yoki raqamini yozing.")
    return "\n".join(lines)


def _looks_like_expected_input(
    missing_field: str | None, user_message: str, rooms: list[dict]
) -> bool:
    text = user_message.strip().lower()
    if not missing_field:
        return False

    if missing_field == "room":
        if re.match(r"^\d+\b", text):
            return True
        for room in rooms:
            room_name = room.get("name", "").lower()
            if room_name and room_name in text:
                return True
            short = room_name.split()[0] if room_name else ""
            if short and short in text:
                return True
        return False

    if missing_field in {"check_in", "check_out"}:
        return _parse_date(text) is not None

    if missing_field == "guests":
        if re.search(r"\d{4}", text):  # sana bo'lishi mumkin
            return False
        if any(month in text for month in MONTH_MAP):
            return False
        return re.search(r"\b\d+\b", text) is not None

    if missing_field == "phone":
        normalized = text.replace(" ", "").replace("-", "")
        if not normalized.startswith("+"):
            normalized = "+" + normalized
        return re.fullmatch(r"\+\d{7,15}", normalized) is not None

    return False


def _is_recommendation_request(text: str) -> bool:
    normalized = text.strip().lower()
    return any(keyword in normalized for keyword in ROOM_RECOMMENDATION_KEYWORDS)


def _is_room_info_request(text: str) -> bool:
    normalized = text.strip().lower()
    return any(keyword in normalized for keyword in ROOM_INFO_KEYWORDS)


async def _booking_ai_guidance(
    user_id: str,
    user_message: str,
    missing_field: str | None,
    draft: dict,
    rooms: list[dict],
    platform: str,
) -> str:
    field_label_map = {
        "room": "xona tanlovi",
        "check_in": "kelish sanasi",
        "check_out": "ketish sanasi",
        "guests": "mehmonlar soni",
        "phone": "telefon raqami",
    }
    field_label = field_label_map.get(missing_field, "ma'lumot")
    field_hint = {
        "room": "xona nomi yoki raqami (masalan: 2 yoki VIP Room)",
        "check_in": "kelish sanasi (masalan: 10 may yoki 2026-05-10)",
        "check_out": "ketish sanasi (masalan: 12 may yoki 2026-05-12)",
        "guests": "mehmonlar soni raqamda (masalan: 2)",
        "phone": "telefon raqami (+998901234567)",
    }.get(missing_field, field_label)

    # Room bosqichida foydalanuvchi "qaysi yaxshi?" desa AI tavsiya bersin
    if missing_field == "room" and _is_recommendation_request(user_message):
        short_rooms = []
        for r in rooms:
            price = f"{r.get('price', 0):,}".replace(",", " ")
            short_rooms.append(
                f"{r.get('name', 'Xona')}: {price} so'm/kun, "
                f"sig'im {r.get('capacity', 2)} kishi, {r.get('description', '')}"
            )
        rooms_brief = "\n".join(f"- {row}" for row in short_rooms)
        ai_text = await _ai_reply(
            user_id=user_id,
            user_message=user_message,
            platform=platform,
            extra_instruction=(
                "Foydalanuvchi bron jarayonida xona tanlayapti. "
                "Xonalardan 1-2 mos variantni tavsiya qiling va qisqa sabab yozing. "
                "Javob oxirida aniq tanlov so'rang.\n\n"
                f"Bron draft: {json.dumps(draft, ensure_ascii=False)}\n"
                f"Mavjud xonalar:\n{rooms_brief}"
            ),
        )
        return (
            f"{ai_text}\n\n"
            "Tanlagan xonangiz nomini yoki raqamini yuboring (masalan: 2 yoki VIP Room)."
        )

    # Sana/raqam kutilayotgan paytda foydalanuvchi xona haqida savol bersa,
    # AI javob berib keyin jarayonni davom ettirishni eslatsin.
    if missing_field in {"check_in", "check_out", "guests", "phone"} and _is_room_info_request(
        user_message
    ):
        ai_text = await _ai_reply(
            user_id=user_id,
            user_message=user_message,
            platform=platform,
            extra_instruction=(
                "Foydalanuvchi bron jarayonida, lekin hozir boshqa savol berdi. "
                "Savolga aniq javob bering va oxirida bronni davom ettirish uchun "
                "kutilayotgan maydonni bitta jumlada eslating."
            ),
        )
        return (
            f"{ai_text}\n\n"
            f"Bronni davom ettiramiz: iltimos, {field_label}ni yuboring."
        )

    # Qolgan holatlarda ham AI bilan odamga o'xshash, kontekstli javob beramiz
    # va bron oqimidan chiqib ketmasdan keyingi qadamni eslatamiz.
    if missing_field in {"room", "check_in", "check_out", "guests", "phone"}:
        ai_text = await _ai_reply(
            user_id=user_id,
            user_message=user_message,
            platform=platform,
            extra_instruction=(
                "Foydalanuvchi bron jarayonida. Savoliga insoniy, samimiy va tabiiy "
                "ohangda javob bering, bir xil gapni takrorlamang. "
                "Javob oxirida bronni davom ettirish uchun aniq bitta keyingi qadamni yozing. "
                "Muhim: bronni AI o'zi yakunlamasin, faqat foydalanuvchini booking stepga qaytarsin. "
                f"Hozir kutilayotgan maydon: {field_label}. "
                f"Foydalanuvchidan so'raladigan format: {field_hint}."
            ),
        )
        return f"{ai_text}\n\nBronni davom ettiramiz: iltimos, {field_hint}ni yuboring."

    return (
        "🧾 Sizda tugallanmagan bron mavjud.\n"
        f"Hozir kutilayotgan ma'lumot: {field_label}.\n\n"
        "Davom ettirish uchun kerakli ma'lumotni yuboring.\n"
        "Yoki bronni bekor qilish uchun: Bekor deb yozing."
    )


async def _resolve_room(draft: dict, user_message: str, rooms: list) -> dict | None:
    """Foydalanuvchi xabaridan xonani topish"""
    text = user_message.strip().lower()

    # Raqam bilan tanlash: "1", "2", "1 maqul", "1 dedimu", "birinchi" va h.k.
    # Xabarning boshida yoki yolg'iz turgan raqam
    num_match = re.match(r"^(\d+)", text)
    if num_match:
        idx = int(num_match.group(1)) - 1
        if 0 <= idx < len(rooms):
            return rooms[idx]

    # So'zli raqam
    word_nums = {
        "birinchi": 0,
        "ikkinchi": 1,
        "uchinchi": 2,
        "to'rtinchi": 3,
        "beshinchi": 4,
        "oltinchi": 5,
        "first": 0,
        "second": 1,
        "third": 2,
    }
    for word, idx in word_nums.items():
        if word in text and 0 <= idx < len(rooms):
            return rooms[idx]

    # Nom bo'yicha qidirish
    for r in rooms:
        room_id_text = str(r.get("id", "")).lower()
        if r["name"].lower() in text or (room_id_text and room_id_text in text):
            return r
        # Qisqa nom: "standart", "delux", "suite", "vip", "family", "premium"
        short = r["name"].lower().split()[0]
        if short in text:
            return r

    # draft da room_id allaqachon bor
    if draft.get("room_id"):
        for r in rooms:
            if r["id"] == draft["room_id"]:
                return r

    return None


# ──────────────────────────────────────────────
# ASOSIY BRON JARAYONI
# ──────────────────────────────────────────────


async def _handle_booking_flow(
    user_id: str, user_message: str, platform: str
) -> str | None:
    """
    Bron jarayonini boshqaradi.
    Agar bron aktiv yoki intent bo'lsa — javob qaytaradi.
    Aks holda None qaytaradi (AI ga uzatiladi).
    """
    draft = BOOKING_DRAFT.get(user_id)
    normalized_message = user_message.strip().lower()

    # Salomlashish bilan qayta boshlasa eski draftni tozalaymiz
    if draft is not None and normalized_message in GREETING_KEYWORDS:
        BOOKING_DRAFT.pop(user_id, None)
        BOOKING_STORE.pop(user_id, None)
        return None

    # Bron jarayoni aktiv emas va intent yo'q — AI ga uzat
    if draft is None and not _is_booking_intent(user_message):
        return None

    # Bron bekor qilish
    if _is_cancel_intent(user_message) and draft is not None:
        BOOKING_DRAFT.pop(user_id, None)
        BOOKING_STORE.pop(user_id, None)
        return "Bron jarayoni bekor qilindi. Boshqa savol bo'lsa, yozing! 😊"

    # Yangi bron boshlash
    if draft is None:
        draft = {}
        BOOKING_DRAFT[user_id] = draft

        # Telegram foydalanuvchisi uchun DB dan ism/telefon to'ldirish
        if user_id.startswith("tg_"):
            tg_uid = user_id.replace("tg_", "")
            db_user = await get_user(tg_uid)
            if db_user:
                first = db_user.get("first_name") or ""
                last = db_user.get("last_name") or ""
                full = (first + " " + last).strip()
                if full:
                    draft["name"] = full
                if db_user.get("phone"):
                    draft["phone"] = db_user["phone"]

    rooms_all = await get_rooms(only_active=True)

    if draft is not None:
        missing_now = _next_missing(draft)
        if normalized_message in BOOKING_CONTINUE_KEYWORDS:
            pass
        elif not _is_cancel_intent(user_message) and not _is_booking_intent(user_message):
            if not _looks_like_expected_input(missing_now, user_message, rooms_all):
                if missing_now == "guests" and "boshqa xona" in normalized_message:
                    draft["room_id"] = None
                    draft["room_name"] = None
                    draft["room_price"] = None
                    draft["room_capacity"] = None
                    BOOKING_DRAFT[user_id] = draft
                    return _format_room_list(rooms_all)

                return await _booking_ai_guidance(
                    user_id=user_id,
                    user_message=user_message,
                    missing_field=missing_now,
                    draft=draft,
                    rooms=rooms_all,
                    platform=platform,
                )

    missing = _next_missing(draft)

    # ── XONA TANLASH ────────────────────────────────────
    if missing == "room":
        room = await _resolve_room(draft, user_message, rooms_all)
        if room:
            draft["room_id"] = room["id"]
            draft["room_name"] = room["name"]
            draft["room_price"] = room["price"]
            draft["room_capacity"] = room.get("capacity", 2)
            BOOKING_DRAFT[user_id] = draft
            missing = _next_missing(draft)
            # Keyingi savolga o't
        else:
            # Xona tushunilmadi — ro'yxat ko'rsat
            BOOKING_DRAFT[user_id] = draft
            return _format_room_list(rooms_all)

    # ── KELISH SANASI ────────────────────────────────────
    if missing == "check_in":
        date_str = _parse_date(user_message)
        if date_str:
            check_in_dt = datetime.strptime(date_str, "%Y-%m-%d")
            if check_in_dt.date() < datetime.now().date():
                return "❗ Kelish sanasi o'tib ketgan. Iltimos, bugun yoki kelajakdagi sanani yozing."
            draft["check_in"] = date_str
            BOOKING_DRAFT[user_id] = draft
            missing = _next_missing(draft)
        else:
            return "📅 Kelish sanasini yozing (masalan: 10 may yoki 2026-05-10)."

    # ── KETISH SANASI ────────────────────────────────────
    if missing == "check_out":
        date_str = _parse_date(user_message)
        if date_str:
            check_in_dt = datetime.strptime(draft["check_in"], "%Y-%m-%d")
            check_out_dt = datetime.strptime(date_str, "%Y-%m-%d")
            if check_out_dt <= check_in_dt:
                return f"❗ Ketish sanasi kelish sanasidan ({draft['check_in']}) keyin bo'lishi kerak. Qayta yozing."
            draft["check_out"] = date_str
            BOOKING_DRAFT[user_id] = draft
            missing = _next_missing(draft)
        else:
            return "📅 Ketish sanasini yozing (masalan: 15 may yoki 2026-05-15)."

    # ── MEHMONLAR SONI ────────────────────────────────────
    if missing == "guests":
        # Sof raqam yoki "X kishi/nafar" formatini qabul qil
        guests_match = re.search(
            r"(\d+)\s*(kishi|odam|mehmon|nafar|ta kishi)?", user_message.strip().lower()
        )
        if guests_match:
            # Lekin sana so'zlari bo'lsa skip
            date_words = list(MONTH_MAP.keys()) + ["-", "."]
            has_date = any(m in user_message.lower() for m in date_words) or re.search(
                r"\d{4}", user_message
            )
            if not has_date:
                n = int(guests_match.group(1))
                capacity = draft.get("room_capacity", 2)
                if n > capacity:
                    return (
                        f"⚠️ {draft['room_name']} xonasi {capacity} kishigacha sig'adi. "
                        f"Mehmonlar sonini kamaytirasizmi yoki boshqa xona tanlaysizmi?"
                    )
                draft["guests"] = n
                BOOKING_DRAFT[user_id] = draft
                missing = _next_missing(draft)
            else:
                return "Necha kishi bo'ladi? (Raqam bilan yozing, masalan: 2)"
        else:
            return "Necha kishi bo'ladi? (Raqam bilan yozing, masalan: 2)"

    # ── TELEFON ────────────────────────────────────
    if missing == "phone":
        phone_raw = user_message.strip().replace(" ", "").replace("-", "")
        if not phone_raw.startswith("+"):
            phone_raw = "+" + phone_raw
        if re.fullmatch(r"\+\d{7,15}", phone_raw):
            draft["phone"] = phone_raw
            BOOKING_DRAFT[user_id] = draft
            missing = _next_missing(draft)
        elif re.search(r"\d{6,}", user_message):
            return "📞 Telefon raqam formati noto'g'ri. Quyidagi formatda yozing: +998901234567"
        else:
            return "📞 Telefon raqamingizni yozing (masalan: +998901234567)."

    # ── HAMMA MA'LUMOT TO'LIQ ────────────────────────────────────
    if _next_missing(draft) is None:
        return await _finalize_booking(user_id, draft, platform, rooms_all)

    # ── KEYINGI SAVOL ────────────────────────────────────
    missing = _next_missing(draft)
    if missing == "room":
        return _format_room_list(rooms_all)
    elif missing == "check_in":
        return "📅 Kelish sanasini yozing (masalan: 10 may)."
    elif missing == "check_out":
        return f"📅 Ketish sanasini yozing (masalan: 15 may)."
    elif missing == "guests":
        return "👥 Necha kishi bo'ladi?"
    elif missing == "phone":
        return "📞 Telefon raqamingizni yozing (+998901234567)."

    return None


async def _finalize_booking(
    user_id: str, draft: dict, platform: str, rooms_all: list
) -> str:
    """Barcha ma'lumot to'liq — bron tasdiqlash xabarini qaytaradi"""
    # Xonani tekshirish
    room = None
    for r in rooms_all:
        if r["id"] == draft["room_id"]:
            room = r
            break

    if not room:
        BOOKING_DRAFT.pop(user_id, None)
        return "Xona topilmadi. Iltimos, qayta boshlang."

    # Mavjudlikni tekshirish
    available = await find_available_rooms(
        draft["check_in"], draft["check_out"], only_active=True
    )
    available_ids = {r["id"] for r in available}

    if room["id"] not in available_ids:
        other = [r for r in available if r["id"] != room["id"]]
        if other:
            draft["room_id"] = None
            draft["room_name"] = None
            BOOKING_DRAFT[user_id] = draft
            lines = [f"😔 {room['name']} bu sanalarda band.\n\nBoshqa bo'sh xonalar:"]
            for i, r in enumerate(other, 1):
                price = f"{r['price']:,}".replace(",", " ")
                lines.append(f"{i}. {r['name']} — {price} so'm/kun")
            lines.append("\nBoshqa xona tanlaysizmi?")
            return "\n".join(lines)
        else:
            draft["check_in"] = None
            draft["check_out"] = None
            BOOKING_DRAFT[user_id] = draft
            return "😔 Bu sanalarda bo'sh xona yo'q. Boshqa sanalarni yozing."

    # Narx hisoblash
    check_in_dt = datetime.strptime(draft["check_in"], "%Y-%m-%d")
    check_out_dt = datetime.strptime(draft["check_out"], "%Y-%m-%d")
    days = (check_out_dt - check_in_dt).days
    total = room["price"] * days
    price_fmt = f"{total:,}".replace(",", " ")
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
        "total_price": total,
        "name": draft.get("name", "Mehmon"),
        "phone": draft["phone"],
        "notes": "",
        "source": platform,
    }

    BOOKING_STORE[user_id] = order_data
    BOOKING_DRAFT.pop(user_id, None)

    name_line = f"👤 {draft.get('name', 'Mehmon')}\n" if draft.get("name") else ""

    if platform == "telegram":
        return (
            f"✅ <b>Broningiz qabul qilindi!</b>\n\n"
            f"🏨 Xona: <b>{room['name']}</b>\n"
            f"📅 Kelish: {draft['check_in']}\n"
            f"📅 Ketish: {draft['check_out']}\n"
            f"🕐 {days} kun × {day_price_fmt} so'm\n"
            f"👥 {draft['guests']} kishi\n"
            f"💰 Jami: <b>{price_fmt} so'm</b>\n\n"
            f"{name_line}"
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
            f"{name_line}"
            f"📞 {draft['phone']}\n\n"
            f"Tasdiqlash uchun: Tasdiqlayman\n"
            f"Bekor qilish uchun: Bekor deb yozing."
        )


# ──────────────────────────────────────────────
# ASOSIY FUNKSIYA
# ──────────────────────────────────────────────


async def get_ai_response(
    user_id: str,
    user_message: str,
    user_name: str = "Mehmon",
    platform: str = "telegram",
) -> str:
    push_message(user_id, "user", user_message)
    log.info(f"[AI] {user_id} ({platform}): {user_message[:80]}")

    # Bron jarayoni
    booking_reply = await _handle_booking_flow(user_id, user_message, platform)
    if booking_reply is not None:
        push_message(user_id, "assistant", booking_reply)
        await log_message(user_id, "incoming", user_message, booking_reply)
        return booking_reply

    # Oddiy AI javob
    reply = await _ai_reply(user_id, user_message, platform)

    # MAXSUS BUYURUQULARNI TEKSHIRISH
    # Lokatsiya buyrug'i (SEND_LOCATION yoki SENDLOCATION)
    loc_pattern = re.compile(r"SEND_?LOCATION", re.IGNORECASE)
    if loc_pattern.search(reply):
        PENDING_LOCATION[user_id] = {"action": "send_location"}
        reply = loc_pattern.sub("", reply).strip()

    # Xona rasmlari buyrug'i (SEND_ROOM_PHOTOS: yoki SENDROOMPHOTOS: kabi variantlar)
    photos_pattern = re.compile(
        r"SEND_?ROOM_?PHOTOS:?\s*([^\n\r]+)?", re.IGNORECASE
    )
    photos_match = photos_pattern.search(reply)
    if photos_match:
        room_name = (photos_match.group(1) or "").strip()
        reply = photos_pattern.sub("", reply).strip()
        if not room_name:
            # Xona nomi topilmasa barcha xonalarni ko'rsatish uchun belgi
            room_name = "_all_"
        PENDING_ROOM_PHOTOS[user_id] = {
            "room_name": room_name,
            "action": "send_photos",
        }

    if not reply:
        reply = "Mana siz so'ragan ma'lumot:"

    push_message(user_id, "assistant", reply)
    await log_message(user_id, "incoming", user_message, reply)
    await log_activity(user_id, "chat", user_message[:50])
    return reply


async def check_pending_actions(user_id: str) -> dict | None:
    """Foydalanuvchida kutayotgan actions borligini tekshiradi"""
    if user_id in PENDING_LOCATION:
        return PENDING_LOCATION.pop(user_id)
    if user_id in PENDING_ROOM_PHOTOS:
        return PENDING_ROOM_PHOTOS.pop(user_id)
    return None


async def get_room_photos_for_user(room_name: str) -> tuple[str, list]:
    """Xona nomi bo'yicha rasm file_ids qaytaradi"""
    rooms = await get_rooms(only_active=True)
    room_name_lower = room_name.lower()

    for room in rooms:
        if (
            room_name_lower in room.get("name", "").lower()
            or room.get("name", "").lower() in room_name_lower
        ):
            photos = await get_room_photos(room["id"])
            return room.get("name", "Xona"), photos

    for room in rooms:
        short = room.get("name", "").lower().split()[0]
        if short in room_name_lower:
            photos = await get_room_photos(room["id"])
            return room.get("name", "Xona"), photos

    return "", []


async def get_hotel_location_for_user() -> tuple[float, float] | None:
    """Mehmonxona lokatsiyasini qaytaradi"""
    return await get_hotel_location()


# ──────────────────────────────────────────────
# YORDAMCHI FUNKSIYALAR
# ──────────────────────────────────────────────


def get_booking_data(user_id: str) -> dict | None:
    return BOOKING_STORE.get(str(user_id))


def clear_booking_data(user_id: str):
    BOOKING_STORE.pop(str(user_id), None)


def reset_user_session(user_id: str):
    uid = str(user_id)
    BOOKING_STORE.pop(uid, None)
    BOOKING_DRAFT.pop(uid, None)
    PENDING_ROOM_PHOTOS.pop(uid, None)
    PENDING_LOCATION.pop(uid, None)
    clear_history(uid)


async def generate_post(topic: str, hotel_name: str) -> str:
    hotel = await get_hotel()
    prompt = (
        f"Marco Polo Hotel uchun Telegram post yoz:\n"
        f"Mavzu: {topic}\n"
        f"Format: Sarlavha, Matn (3-5 jumla), Narxlar, "
        f"📞 {hotel.get('phone', '+998773397171')} | {hotel.get('telegram', '@Marcopolohotel_1')}\n"
        f"Faqat oddiy matn, markdown ishlatma."
    )
    try:
        client = get_openai_client()
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.8,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        log.error(f"Post error: {e}")
        return "Post yaratishda xatolik. Qayta urinib ko'ring."


async def generate_booking_confirmation(order_data: dict) -> str:
    hotel = await get_hotel()
    price_fmt = f"{order_data['total_price']:,}".replace(",", " ")
    return (
        f"✅ BUYURTMA QABUL QILINDI!\n\n"
        f"🏨 Xona: {order_data['room_name']}\n"
        f"📅 Kelish: {order_data['check_in']}\n"
        f"📅 Ketish: {order_data['check_out']}\n"
        f"👥 Mehmonlar: {order_data['guests']} kishi\n"
        f"💰 Jami: {price_fmt} so'm\n\n"
        f"👤 Ism: {order_data['name']}\n"
        f"📞 Telefon: {order_data['phone']}\n\n"
        f"⏱ Operator tez orada siz bilan bog'lanadi!\n"
        f"📞 {hotel.get('phone', '+998773397171')}"
    )


async def send_order_to_admins(bot, order_data: dict, admin_ids: list):
    hotel = await get_hotel()
    price_fmt = f"{order_data['total_price']:,}".replace(",", " ")
    hotel_address = hotel.get("address", "Do'mbirobod Naqqoshlik 121A")
    source_label = order_data.get("source", "telegram").upper()

    message = (
        f"🔔 <b>YANGI BRON! [{source_label}]</b>\n\n"
        f"🏨 Xona: <b>{order_data['room_name']}</b>\n"
        f"📅 {order_data['check_in']} → {order_data['check_out']}\n"
        f"👥 {order_data['guests']} kishi\n"
        f"💰 <b>{price_fmt} so'm</b>\n\n"
        f"👤 {order_data['name']}\n"
        f"📞 {order_data['phone']}\n"
        f"📍 {hotel_address}"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    phone_clean = order_data.get("phone", "").replace("tel:", "").strip()
    buttons = [
        [
            InlineKeyboardButton(
                text="✅ Tasdiqlash", callback_data=f"order_confirm_{order_data['id']}"
            ),
            InlineKeyboardButton(
                text="❌ Bekor", callback_data=f"order_cancel_{order_data['id']}"
            ),
        ]
    ]
    if phone_clean and phone_clean.startswith("+"):
        buttons.append(
            [InlineKeyboardButton(text="📞 Qo'ng'iroq", url=f"tel:{phone_clean}")]
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    for admin_id in admin_ids:
        try:
            await bot.send_message(int(admin_id), message, reply_markup=keyboard)
        except Exception as e:
            log.error(f"Admin notify error ({admin_id}): {e}")

    if os.getenv("ORDERS_GROUP_ID"):
        try:
            await bot.send_message(int(os.getenv("ORDERS_GROUP_ID")), message)
        except Exception as e:
            log.error(f"Group notify error: {e}")
