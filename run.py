"""
Hammasini birgalikda ishga tushirish:
  - Aiogram Telegram bot (polling)
  - FastAPI server (Instagram ManyChat)

Ishlatish:
    python run.py
"""

import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

log = logging.getLogger(__name__)


async def run_bot():
    from aiogram import Bot, Dispatcher
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.fsm.storage.redis import RedisStorage
    from bot.handlers import user, admin

    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        storage = RedisStorage.from_url(redis_url)
        log.info("Redis orqali ulashilmoqda ✅")
    else:
        storage = MemoryStorage()
        log.info("MemoryStorage orqali ulashilmoqda ⚠️ (Production uchun Redis tavsiya etiladi)")

    bot = Bot(
        token=os.getenv("TELEGRAM_BOT_TOKEN"),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=storage)
    dp.include_router(admin.router)
    dp.include_router(user.router)

    log.info("Telegram bot boshlandi ✅")
    await dp.start_polling(bot, skip_updates=True)


async def run_api():
    import uvicorn
    from app.main import app

    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8001)),
        log_level="warning",
    )
    server = uvicorn.Server(config)
    log.info(f"FastAPI server boshlandi (port {os.getenv('PORT', 8001)}) ✅")
    await server.serve()


async def main():
    from config.database import init_db
    
    missing = []
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        missing.append("TELEGRAM_BOT_TOKEN")
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if not os.getenv("SUPER_ADMIN_ID"):
        missing.append("SUPER_ADMIN_ID")

    if missing:
        log.error(f"Quyidagi muhit o'zgaruvchilari topilmadi: {', '.join(missing)}")
        sys.exit(1)

    log.info("Database tayyorlanmoqda...")
    await init_db()
    log.info("✅ Database tayyor!")

    log.info("Hotel AI Chatbot v4 ishga tushmoqda... 🏨")
    await asyncio.gather(run_bot(), run_api())


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    asyncio.run(main())
