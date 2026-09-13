import aiosqlite
import aiohttp
import random
import os
import logging
from config import DB_PATH, NAMES_FILE, SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

# Supabase REST Headers
SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

async def init_db():
    """Local SQLite Database tables initialize karein"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,          -- 'text' or 'photo'
                content TEXT NOT NULL,       -- review text / caption
                media_path TEXT             -- photo file path if type == 'photo'
            )
        """)

        # Used Reviews Table (Taaki reviews kabhi repeat na hon)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS used_reviews (
                review_id INTEGER PRIMARY KEY
            )
        """)

        # Used Names Table (Taaki names repeat na hon)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS used_names (
                name TEXT PRIMARY KEY
            )
        """)
        await db.commit()

# ================= SUPABASE CLOUD ACCOUNTS MANAGEMENT =================

async def save_account(phone: str, session_string: str, first_name: str, user_id: int):
    """Account ko directly Supabase Cloud me Upsert karta hai"""
    url = f"{SUPABASE_URL}/rest/v1/accounts"
    headers = {
        **SUPABASE_HEADERS,
        "Prefer": "resolution=merge-duplicates"
    }
    payload = {
        "phone": phone,
        "session_string": session_string,
        "first_name": first_name or "Trader",
        "user_id": user_id,
        "is_active": 1
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return resp.status in (200, 201)
    except Exception as e:
        logger.error(f"Supabase Save Error: {e}")
        return False

async def get_all_accounts():
    """Supabase Cloud se saare active accounts fetch karta hai"""
    url = f"{SUPABASE_URL}/rest/v1/accounts?is_active=eq.1&select=*"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=SUPABASE_HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
                return []
    except Exception as e:
        logger.error(f"Supabase Fetch Error: {e}")
        return []

async def get_accounts_count():
    accounts = await get_all_accounts()
    return len(accounts)

async def delete_account(phone: str):
    url = f"{SUPABASE_URL}/rest/v1/accounts?phone=eq.{phone}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=SUPABASE_HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return resp.status in (200, 204)
    except Exception as e:
        logger.error(f"Supabase Delete Error: {e}")
        return False

# ================= TARGET USER ID MANAGEMENT =================

async def set_target_id(target_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('target_id', ?)", (str(target_id),))
        await db.commit()

async def get_target_id():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = 'target_id'") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

# ================= NON-REPEATING REVIEWS ENGINE =================

async def add_review(review_type: str, content: str, media_path: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO reviews (type, content, media_path) VALUES (?, ?, ?)",
            (review_type, content, media_path)
        )
        await db.commit()

async def add_bulk_photos(photo_paths: list):
    async with aiosqlite.connect(DB_PATH) as db:
        for p in photo_paths:
            await db.execute(
                "INSERT INTO reviews (type, content, media_path) VALUES ('photo', '', ?)",
                (p,)
            )
        await db.commit()

async def get_all_reviews():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM reviews") as cursor:
            return await cursor.fetchall()

async def get_text_reviews():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM reviews WHERE type = 'text'") as cursor:
            return await cursor.fetchall()

async def get_photo_reviews():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM reviews WHERE type = 'photo'") as cursor:
            return await cursor.fetchall()

async def get_unique_text_review() -> str:
    """Zero-Repetition Text Review Picker"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM reviews WHERE type = 'text'") as cursor:
            all_texts = await cursor.fetchall()

        if not all_texts:
            return "Bhai trading session bohot accha tha, profit booked! 🔥"

        # Check used reviews
        async with db.execute("SELECT review_id FROM used_reviews") as cursor:
            used_ids = set(row[0] for row in await cursor.fetchall())

        available = [r for r in all_texts if r["id"] not in used_ids]

        # Agar saare use ho chuke hain, toh used_reviews ko reset karein
        if not available:
            await db.execute("DELETE FROM used_reviews")
            await db.commit()
            available = all_texts

        chosen = random.choice(available)
        await db.execute("INSERT OR IGNORE INTO used_reviews (review_id) VALUES (?)", (chosen["id"],))
        await db.commit()
        return chosen["content"]

async def get_reviews_count():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM reviews WHERE type = 'text'") as c1:
            text_cnt = (await c1.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM reviews WHERE type = 'photo'") as c2:
            photo_cnt = (await c2.fetchone())[0]
        return text_cnt, photo_cnt

async def clear_all_reviews():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM reviews")
        await db.execute("DELETE FROM used_reviews")
        await db.commit()

# ================= RANDOM NAME PICKER =================

async def get_next_name() -> str:
    if not os.path.exists(NAMES_FILE):
        return f"Trader_{random.randint(100, 999)}"

    with open(NAMES_FILE, "r", encoding="utf-8") as f:
        all_names = [line.strip() for line in f if line.strip()]

    if not all_names:
        return f"Member_{random.randint(100, 999)}"

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM used_names") as cursor:
            used = set(row[0] for row in await cursor.fetchall())

        available = [n for n in all_names if n not in used]

        if not available:
            await db.execute("DELETE FROM used_names")
            await db.commit()
            available = all_names

        chosen = random.choice(available)
        await db.execute("INSERT OR IGNORE INTO used_names (name) VALUES (?)", (chosen,))
        await db.commit()
        return chosen