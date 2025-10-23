import os
import logging
from telethon import events
from client_provider import client
from config import REFS_DIR
from db import set_user_ref_path, get_available_credits
from state import get_state
from tasks import synthesize_and_send
from ui_components import show_persistent_menu


print("messages.py imported — client id:", id(client))


async def save_ref_path(event, user_id, st, ref_path=None):
    msg = event.message
    sender = await event.get_sender()
    is_voice = False
    is_audio = False
    if sender and getattr(sender, "bot", False):
        return
    if getattr(msg, "fwd_from", None) is not None:
        return
    if getattr(msg, "voice", None) is not None:
        is_voice = True
    elif getattr(msg, "audio", None) is not None:
        is_audio = True

    if not (is_voice or is_audio):
        # не интересуемся — выход
        return

    kind = "voice" if is_voice else "audio"

    dest_dir = os.path.join(REFS_DIR, str(user_id))
    os.makedirs(dest_dir, exist_ok=True)
    path = await event.download_media(file=dest_dir)
    if not path:
        # нет медиа или ошибка скачивания
        await event.reply("❗ Не удалось скачать media.")
        return None
    st["ref_path"] = path
    await set_user_ref_path(user_id, path)

    # нормализуем пути для сравнения
    path = os.path.abspath(path)
    try:
        for fname in os.listdir(dest_dir):
            fpath = os.path.abspath(os.path.join(dest_dir, fname))
            # не удаляем сам только что скачанный файл
            if fpath == path:
                continue
            os.remove(fpath)
    except Exception:
        # если чтение директории по каким-то причинам упало — игнорируем
        pass

    await event.reply(f"✅ Установил {'голосовое' if is_voice else 'аудиофайл'}")


# Главный обработчик сообщений (загрузка референса и состояния для топапа)
@client.on(events.NewMessage(incoming=True))
async def global_handler(event):
    print("TEEEST")
    user_id = event.sender_id
    chat_id = event.chat_id

    sender = await event.get_sender()  # загрузит User (или None)
    username = getattr(sender, "username", None)  # может быть None

    st = await get_state(event)
    # Если сообщение содержит медиа — сохраняем как референс
    await save_ref_path(event, user_id, st)

    text = (event.text or "").strip()
    if not text:
        return

    # Если у пользователя открыт flow пополнения (awaiting_topup), ждём число (кол-во минут)
    awaiting = st.get("awaiting_topup")
    ref_path = st.get("ref_path")
    mode = st.get("mode", False)
    auto_accent = st.get("auto_accent", True)

    if awaiting:
        # Ожидаем, что пользователь прислал число: количество минут
        if text.isdigit():
            minutes = int(text)
            provider = awaiting
            st.pop("awaiting_topup", None)
            if provider == "stars":
                from handlers.payments import create_stars_invoice

                await create_stars_invoice(user_id, minutes)
                return
            elif provider == "robokassa":
                from handlers.payments import process_robokassa_payment

                await process_robokassa_payment(event, user_id, minutes)
                return
        else:
            await event.reply(
                "Отправьте число (количество минут) или выберите из списка"
            )
            return

    # Простая команда показать баланс
    elif text == "/balance":
        avail = await get_available_credits(user_id, username=username)
        await event.reply(f"Вам доступно {avail} минут.")
        return

    # Если пользователь отправил "Выбрать голос" ранее (state selected_voice) — простое сообщение-напоминание
    elif not text.startswith("/"):
        if ref_path:
            available = await get_available_credits(user_id, username=username)
            synthesize_and_send.delay(
                chat_id,
                user_id,
                available,
                text,
                ref_audio_local_path=ref_path,
                send_as_mp3=mode == "mp3",
                caption="",
                auto_accent=auto_accent,
            )
            await show_persistent_menu(
                client, event.chat_id, caption="Задача поставлена в очередь..."
            )
            return
        else:
            await show_persistent_menu(
                client, chat_id, caption="Выберите или отправьте референс голос."
            )
            return
