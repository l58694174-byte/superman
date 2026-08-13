import os
import logging

logger = logging.getLogger(__name__)
_pool = None
_connected = False

async def attach(app):
    """Connect to Postgres if DATABASE_URL is set, otherwise skip."""
    global _pool, _connected
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.warning("[DB] DATABASE_URL not set. Premium persistence disabled.")
        _connected = False
        return
    try:
        import asyncpg
        _pool = await asyncpg.create_pool(db_url)
        async with _pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS premium_users (
                    uid TEXT PRIMARY KEY,
                    plan TEXT,
                    expires BIGINT,
                    name TEXT,
                    username TEXT,
                    last_receipt TEXT
                )
            """)
        _connected = True
        logger.info("[DB] PostgreSQL connected successfully.")
    except Exception as e:
        logger.error(f"[DB] Failed to connect: {e}")
        _connected = False

def is_connected() -> bool:
    return _connected

def status_text() -> str:
    return "✅ Connected" if _connected else "❌ Disconnected"

async def save_all_now(user_data: dict) -> int:
    if not _pool or not _connected:
        return 0
    count = 0
    try:
        async with _pool.acquire() as conn:
            for uid_str, ud in user_data.items():
                plan = ud.get("plan", "TRIAL").upper()
                expires = ud.get("expires", 0)
                if plan != "TRIAL" and expires > 0:
                    name = ud.get("name", "")
                    username = ud.get("username", "")
                    last_receipt = ud.get("last_receipt", "")
                    await conn.execute("""
                        INSERT INTO premium_users (uid, plan, expires, name, username, last_receipt)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (uid) DO UPDATE SET
                            plan = EXCLUDED.plan,
                            expires = EXCLUDED.expires,
                            name = EXCLUDED.name,
                            username = EXCLUDED.username,
                            last_receipt = EXCLUDED.last_receipt
                    """, uid_str, plan, expires, name, username, last_receipt)
                    count += 1
    except Exception as e:
        logger.error(f"[DB] Save failed: {e}")
    return count

async def close_db(bot_data: dict):
    if bot_data and _connected:
        await save_all_now(bot_data.get("user_data", {}))
    if _pool:
        await _pool.close()
        _pool = None
