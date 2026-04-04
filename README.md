# 🏨 Hotel AI Chatbot v3

**Telegram (Aiogram 3) + Instagram (ManyChat) + Admin Panel + AI Post**

---

## 📁 Tuzilma

```
hotel_bot/
├── run.py                        # Hammasini birga ishga tushirish
├── requirements.txt
├── .env.example
├── data/
│   └── db.json                   # Ma'lumotlar bazasi (avtomatik yaratiladi)
├── config/
│   └── database.py               # DB operatsiyalari
├── app/
│   ├── main.py                   # FastAPI (Instagram webhook)
│   ├── ai_handler.py             # OpenAI GPT
│   ├── manychat.py               # ManyChat format
│   └── subscription.py           # Majburiy obuna tekshirish
└── bot/
    ├── main.py                   # Faqat bot ishga tushirish
    ├── handlers/
    │   ├── user.py               # Foydalanuvchi handlerlari
    │   └── admin.py              # Admin panel handlerlari
    └── keyboards/
        └── keyboards.py          # Barcha klaviaturalar
```

---

## ⚡ Ishga tushirish

```bash
# 1. O'rnatish
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. .env yaratish
cp .env.example .env
# .env faylni oching va to'ldiring

# 3. Ishga tushirish
python run.py

# Faqat bot (API kerak bo'lmasa)
python bot/main.py
```

---

## 👑 Super Admin

`.env` da `SUPER_ADMIN_ID` ni o'z Telegram ID ingiz bilan to'ldiring.  
ID olish: @userinfobot ga /start yozing.

---

## ⚙️ Admin Panel imkoniyatlari

| Bo'lim | Imkoniyatlar |
|--------|-------------|
| 🏠 Xonalar | Qo'shish, tahrirlash, o'chirish, yoqish/o'chirish |
| 🏨 Mehmonxona | Nom, manzil, telefon, haqida, salomlashish matni |
| 📢 Kanallar | Majburiy obuna kanallari, post kanali |
| 📝 Post | AI bilan yoki qo'lda post yozish, kanalga yuborish |
| 👥 Adminlar | Qo'shish va o'chirish |
| 📊 Statistika | Foydalanuvchilar, xonalar, kanallar soni |

---

## 📢 Majburiy Obuna Sozlash

1. Admin panelda **📢 Kanallar** bo'limiga o'ting
2. Botni kanalga **admin** qiling
3. Kanal ID sini yuboring: `-1001234567890`
4. Post kanali uchun: `post:-1001234567890`

**Kanal ID olish:** @username_to_id_bot

---

## 📝 AI Post Yaratish

1. **📝 Post yaratish** tugmasini bosing
2. **🤖 AI bilan** → mavzu yozing → AI post tayyorlaydi
3. Preview ko'ring → **✅ Yuborish** yoki **♻️ Qayta yozish**

---

## 📸 ManyChat (Instagram) Sozlash

**External Request:**
- URL: `https://your-domain.com/webhook/manychat`
- Method: `POST`
- Body:
```json
{
  "user_id": "{{user_id}}",
  "first_name": "{{first_name}}",
  "message": "{{last_input_text}}"
}
```
- Response mapping: `content.messages[0].text` → `{{ai_response}}`

---

## 🌐 Deploy (Render.com)

1. GitHub ga yuklang
2. Render → New Web Service
3. Start command: `python run.py`
4. Environment Variables qo'shing (`.env.example` dan)
5. URL oling → ManyChat ga ulang

---

## 💰 Taxminiy narx

| Xizmat | Oylik |
|--------|-------|
| OpenAI gpt-4o-mini | ~$2-5 |
| Render.com (bepul plan) | $0 |
| **Jami** | **~$2-5** |
