import os
import asyncio
import logging
from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN,
    REFS_DIR,
)
from db import (
    init_db_pool,
)
from ui_components import *
from client_provider import client
from schema import create_schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


import handlers.messages
import handlers.commands
import handlers.callbacks
import handlers.payments


async def main():
    # 1) Инициализируем пул
    pool = await init_db_pool()

    # 2) Создаём/проверяем таблицы (идемпотентно)
    try:
        await create_schema(
            init_db_pool
        )  # передаём функцию, которая вернёт pool внутри
    except Exception:
        logging.exception("Не удалось создать схему БД. Выход.")
        # закроем пул и прервём запуск приложения
        await pool.close()
        return

    # 3) Запускаем бота
    try:
        await client.start(bot_token=BOT_TOKEN)
        print("Bot started")
        # 4) Ждём отключения
        await client.run_until_disconnected()
    finally:
        # 5) Гарантированно закрываем пул при остановке/исключении
        try:
            await pool.close()
        except Exception:
            logging.exception("Ошибка при закрытии пула БД")
    await client.run_until_disconnected()


# Старт бота
if __name__ == "__main__":
    import os

    os.makedirs(REFS_DIR, exist_ok=True)

    asyncio.run(main())
