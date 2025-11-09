import asyncpg
import asyncio
import logging

DDL = """
CREATE TABLE IF NOT EXISTS users (
    user_id            BIGINT PRIMARY KEY,
    username           TEXT,
    link               TEXT,
    auto_accent        BOOLEAN NOT NULL DEFAULT TRUE,
    model_id           INTEGER NOT NULL DEFAULT 1,
    ref_path           TEXT,
    balance            NUMERIC(18,6) NOT NULL DEFAULT 0,
    mode               TEXT,
    date_created       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    date_updated       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_model_id ON users(model_id);

CREATE TABLE IF NOT EXISTS models (
    id      SERIAL PRIMARY KEY,
    name    TEXT UNIQUE NOT NULL,
    count   BIGINT NOT NULL DEFAULT 0,
    meta    JSONB,
    date_created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    date_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transactions (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    provider      TEXT NOT NULL,
    amount        NUMERIC(18,6) NOT NULL,
    status        TEXT NOT NULL,
    metadata      JSONB,
    date_created  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    date_updated  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
"""


async def create_schema(init_db_pool):
    """
    init_db_pool - функция, которую вы привели (возвращает asyncpg pool)
    Вызывать один раз при старте приложения.
    """
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        try:
            async with conn.transaction():
                await conn.execute(DDL)
        except Exception:
            logging.exception("Ошибка при создании схемы базы данных")
            raise
    logging.info("Схема БД проверена/создана.")
