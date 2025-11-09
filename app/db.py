import asyncpg
import datetime
import config
from config import PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DB
from typing import Optional

_pool = None


async def init_db_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASSWORD,
            database=PG_DB,
            min_size=1,
            max_size=5,
        )
    return _pool


async def ensure_user(user_id: int, username=None):
    if username:
        link = f"https://t.me/{username}"  # веб-ссылка — лучший вариант
    else:
        link = f"tg://user?id={user_id}"
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
        INSERT INTO users (user_id, username, link, auto_accent, model_id, balance)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (user_id) DO NOTHING
        """,
            user_id,
            username,
            link,
            True,
            1,
            config.BALANCE,
        )


async def get_user(user_id: int):
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
        return dict(row) if row else {}


async def get_user_ref_path(user_id: int):
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchval(
            "SELECT ref_path FROM users WHERE user_id=$1", user_id
        )
        return row or None


async def set_user_ref_path(user_id: int, ref_path: str):
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET ref_path = $1
            WHERE user_id = $2
            """,
            ref_path,
            user_id,
        )


async def increase_model_count(model_name: str):
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE models
            SET count = models.count + 1
            WHERE name = $1
            """,
            model_name,
        )


async def set_user_model(user_id: int, model_id: int):
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET model_id = $1
            WHERE user_id = $2
            """,
            model_id,
            user_id,
        )


async def set_user_mode(user_id: int, mode: str):
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET mode = $1
            WHERE user_id = $2
            """,
            mode,
            user_id,
        )


async def set_auto_accent(user_id: int, auto_accent: str):
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET auto_accent = $1
            WHERE user_id = $2
            """,
            bool(auto_accent),
            user_id,
        )


async def get_user_mode(user_id: int):
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        mode = await conn.fetchval("SELECT mode FROM users WHERE user_id=$1", user_id)
        return mode or None


async def get_available_credits(user_id: int, username=None):
    user = await get_user(user_id)
    if not user:
        await ensure_user(user_id, username=username)
        user = await get_user(user_id)
    balance = user.get("balance", 0) or 0
    return balance


async def consume_credit(user_id: int, amount_minutes: float):
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, balance)
            VALUES ($1, 0)
            ON CONFLICT (user_id) DO UPDATE
            SET balance = GREATEST(users.balance - $2, 0)
            """,
            user_id,
            amount_minutes,
        )


async def add_balance(user_id: int, amount: float):
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, balance)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET balance = users.balance + $2
        """,
            user_id,
            amount,
        )


async def get_transaction(payment_id: int) -> Optional[dict]:
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, user_id, amount, status, metadata FROM transactions WHERE id=$1",
            payment_id,
        )
        return dict(row) if row else None


# transactions helpers
async def transaction_exists(payment_id: str):
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchval("SELECT 1 FROM transactions WHERE id=$1", payment_id)
        return bool(r)


async def record_transaction(
    user_id: int, provider: str, amount: float, status: str, metadata: dict
):
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        payment_id = await conn.fetchval(
            """
            INSERT INTO transactions (user_id, provider, amount, status, metadata, date_created, date_updated)
            VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
            RETURNING id
            """,
            user_id,
            provider,
            amount,
            status,
            str(metadata),
        )
        return payment_id


async def update_transaction_status(payment_id: int, new_status: str) -> bool:
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE transactions
            SET status = $2,
                date_updated = NOW()
            WHERE id = $1
              AND status IS DISTINCT FROM $2
            RETURNING id
            """,
            payment_id,
            new_status,
        )
        return bool(row)
