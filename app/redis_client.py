import os
import json
import logging
import redis.asyncio as redis

log = logging.getLogger(__name__)

# Global memory fallbacks (Redis yo'q paytida foydalanish uchun xavfsiz yostiqcha)
_mem_store = {}
_mem_booking_draft = {}
_mem_booking_store = {}

redis_conn = None
if os.getenv("REDIS_URL"):
    try:
        redis_conn = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
        log.info("AI Memory ulangan: Redis ✅")
    except Exception as e:
        log.error(f"Redis ulanishida xatolik: {e}")

async def get_history(user_id: str) -> list:
    if redis_conn:
        try:
            data = await redis_conn.get(f"history:{user_id}")
            return json.loads(data) if data else []
        except Exception:
            return _mem_store.get(str(user_id), [])
    return _mem_store.get(str(user_id), [])

async def push_message(user_id: str, role: str, content: str, max_history=20):
    history = await get_history(user_id)
    history.append({"role": role, "content": content})
    if len(history) > max_history:
        history = history[-max_history:]
    
    if redis_conn:
        try:
            await redis_conn.set(f"history:{user_id}", json.dumps(history), ex=3600*24*7)
            return
        except Exception:
            pass
    _mem_store[str(user_id)] = history

async def clear_history(user_id: str):
    if redis_conn:
        try:
            await redis_conn.delete(f"history:{user_id}")
        except Exception:
            pass
    _mem_store.pop(str(user_id), None)


async def get_booking_draft(user_id: str) -> dict:
    if redis_conn:
        try:
            data = await redis_conn.get(f"draft:{user_id}")
            return json.loads(data) if data else {}
        except Exception:
            return _mem_booking_draft.get(str(user_id), {})
    return _mem_booking_draft.get(str(user_id), {})

async def set_booking_draft(user_id: str, draft: dict):
    if redis_conn:
        try:
            await redis_conn.set(f"draft:{user_id}", json.dumps(draft), ex=3600*2) # 2 soat ichida qolib ketsa tozalaydi
            return
        except Exception:
            pass
    _mem_booking_draft[str(user_id)] = draft

async def clear_booking_draft(user_id: str):
    if redis_conn:
        try:
            await redis_conn.delete(f"draft:{user_id}")
        except Exception:
            pass
    _mem_booking_draft.pop(str(user_id), None)


async def get_booking_store(user_id: str) -> dict | None:
    if redis_conn:
        try:
            data = await redis_conn.get(f"store:{user_id}")
            return json.loads(data) if data else None
        except Exception:
            return _mem_booking_store.get(str(user_id))
    return _mem_booking_store.get(str(user_id))

async def set_booking_store(user_id: str, store: dict):
    if redis_conn:
        try:
            await redis_conn.set(f"store:{user_id}", json.dumps(store), ex=3600*24)
            return
        except Exception:
            pass
    _mem_booking_store[str(user_id)] = store

async def clear_booking_store(user_id: str):
    if redis_conn:
        try:
            await redis_conn.delete(f"store:{user_id}")
        except Exception:
            pass
    _mem_booking_store.pop(str(user_id), None)

