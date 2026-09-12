import aiosqlite
import time

DB_PATH = r"C:\Users\lulu\OneDrive\Desktop\my-discord\bot-coordinator.db"


async def setup():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                guild_id INTEGER,
                channel_id INTEGER,
                bot_id INTEGER,
                claimed_at REAL,
                PRIMARY KEY (guild_id, channel_id)
            )
        """)
        await db.commit()


async def release_bot(bot_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM claims WHERE bot_id = ?",
            (bot_id,)
        )
        await db.commit()


async def release_claim(guild_id, channel_id, bot_id):
    # دعم لو تم إرسال كائنات بدلاً من الأرقام
    if hasattr(guild_id, "id"):
        guild_id = guild_id.id
    if hasattr(channel_id, "id"):
        channel_id = channel_id.id

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM claims WHERE guild_id = ? AND channel_id = ? AND bot_id = ?",
            (guild_id, channel_id, bot_id)
        )
        await db.commit()


async def claim_channel(guild_id, channel_id, bot_id):
    # دعم لو تم إرسال كائنات Guild و Channel بدلاً من الأرقام مباشرة
    if hasattr(guild_id, "id"):
        guild_id = guild_id.id
    if hasattr(channel_id, "id"):
        channel_id = channel_id.id

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA busy_timeout = 5000")
        await db.execute("BEGIN IMMEDIATE")

        cursor = await db.execute(
            "SELECT bot_id FROM claims WHERE guild_id = ? AND channel_id = ?",
            (guild_id, channel_id)
        )

        row = await cursor.fetchone()
        await cursor.close()

        if row:
            await db.rollback()
            return False

        await db.execute(
            """
            INSERT INTO claims (guild_id, channel_id, bot_id, claimed_at)
            VALUES (?, ?, ?, ?)
            """,
            (guild_id, channel_id, bot_id, time.time())
        )

        await db.commit()
        return True