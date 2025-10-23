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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


import handlers.messages
import handlers.commands
import handlers.callbacks
import handlers.payments


async def main():
    await init_db_pool()

    await client.start(bot_token=BOT_TOKEN)

    print("Bot started")
    await client.run_until_disconnected()


# Старт бота
if __name__ == "__main__":
    import os

    os.makedirs(REFS_DIR, exist_ok=True)

    asyncio.run(main())
