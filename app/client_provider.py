from telethon import TelegramClient
from config import API_ID, API_HASH  # ваши константы

# не стартуем клиента здесь — только создаём объект
client = TelegramClient("bot_session", API_ID, API_HASH)
