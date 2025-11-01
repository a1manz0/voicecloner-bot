from telethon import events, errors
from bot import client  # Импортируем 'client' из главного bot.py
from config import REF_VOICE_1, REF_VOICE_2
from db import set_user_ref_path, get_available_credits, set_user_model
from state import get_state
from ui_components import (
    VOICE_CHOICE_BUTTONS,
    BUY_CREDITS_BUTTONS,
    TOPUP_ROBOKASSA_BUTTONS,
    TOPUP_STARS_BUTTONS,
    MAIN_MENU_BUTTONS,
    S1_INSTRUCTIONS,
)


@client.on(events.CallbackQuery)
async def callback_handler(event):
    uid = event.sender_id
    chat_id = event.chat_id
    sender = await event.get_sender()  # загрузит User (или None)
    username = getattr(sender, "username", None)  # может быть None

    data = event.data.decode() if event.data else ""
    # подтверждаем, чтобы у пользователя не висел "spinner"
    try:
        await event.answer()  # просто закрыть "loading" в интерфейсе
    except Exception:
        pass

    # Обработка разных callback'ов
    if data == "upload_ref":
        await event.respond(
            "Отправьте голосовое сообщение (voice/note) — я сохраню его как референс."
        )
        return

    if data == "choose_voice":
        try:
            await event.edit("Выберите голос:", buttons=VOICE_CHOICE_BUTTONS)
        except (
            errors.rpcerrorlist.MessageEditTimeExpiredError,
            errors.rpcerrorlist.MessageIdInvalidError,
        ) as e:
            await event.respond("Выберите голос:", buttons=VOICE_CHOICE_BUTTONS)
            try:
                await event.message.delete()  # удалить старое сообщение с кнопками
            except Exception:
                pass
        return

    if data.startswith("voice:"):
        choice = data.split(":", 1)[1]
        st = await get_state(event)
        if choice == "1":
            st["ref_path"] = REF_VOICE_1
            await set_user_ref_path(uid, REF_VOICE_1)
            await client.send_file(
                chat_id,
                REF_VOICE_1,
                caption=f"Выбран голос {choice}. Отправьте текст, чтобы получить речь",
            )
        elif choice == "2":
            st["ref_path"] = REF_VOICE_2
            await set_user_ref_path(uid, REF_VOICE_2)
            await client.send_file(
                chat_id,
                REF_VOICE_2,
                caption=f"Выбран голос {choice}. Отправьте текст, чтобы получить речь",
            )
        return
    if data.startswith("model:"):
        choice = data.split(":", 1)[1]
        st = await get_state(event)
        model_name = 1
        if choice == "1":
            model_name = "F5-TTS"
            st["model_id"] = 1
            await set_user_model(uid, 2)
        elif choice == "2":
            model_name = "OpenAudio S1"
            st["model_id"] = 2
            await set_user_model(uid, 2)
        elif choice == "3":
            model_name = "EL"
            st["model_id"] = 3
            await set_user_model(uid, 3)
        try:
            await event.edit(f"Вы выбрали модель {model_name}", parse_mode="html")
        except (
            errors.rpcerrorlist.MessageEditTimeExpiredError,
            errors.rpcerrorlist.MessageIdInvalidError,
        ) as e:
            await event.respond("Вы выбрали модель F5-TTS", parse_mode="html")
            try:
                await event.message.delete()  # удалить старое сообщение с кнопками
            except Exception:
                pass
        return

    if data == "buy_credits":
        try:
            await event.edit(
                "Выберите провайдера:",
                buttons=BUY_CREDITS_BUTTONS,
            )
        except (
            errors.rpcerrorlist.MessageEditTimeExpiredError,
            errors.rpcerrorlist.MessageIdInvalidError,
        ) as e:
            await event.respond(
                "Выберите провайдера:",
                buttons=BUY_CREDITS_BUTTONS,
            )
            try:
                await event.message.delete()  # удалить старое сообщение с кнопками
            except Exception:
                pass
        return

    if data == "topup_robokassa":
        st = await get_state(event)
        st["awaiting_topup"] = "robokassa"
        try:
            await event.edit(
                "Выберите количество минут или введите количество минут(целое число) вручную:",
                buttons=TOPUP_ROBOKASSA_BUTTONS,
            )
        except (
            errors.rpcerrorlist.MessageEditTimeExpiredError,
            errors.rpcerrorlist.MessageIdInvalidError,
        ) as e:
            await event.respond(
                "Выберите количество минут или введите количество минут(целое число) вручную:",
                buttons=TOPUP_ROBOKASSA_BUTTONS,
            )
            try:
                await event.message.delete()  # удалить старое сообщение с кнопками
            except Exception:
                pass
        return

    if data == "topup_stars":
        st = await get_state(event)
        st["awaiting_topup"] = "stars"

        try:
            await event.edit(
                "Выберите количество минут или введите своё число вручную:",
                buttons=TOPUP_STARS_BUTTONS,
            )
        except (
            errors.rpcerrorlist.MessageEditTimeExpiredError,
            errors.rpcerrorlist.MessageIdInvalidError,
        ) as e:
            await event.respond(
                "Выберите количество минут или введите своё число вручную:",
                buttons=TOPUP_STARS_BUTTONS,
            )
            try:
                await event.message.delete()  # удалить старое сообщение с кнопками
            except Exception:
                pass
        return

    if data == "my_balance":
        st = await get_state(event)
        avail = await get_available_credits(uid, username=username)
        await event.respond(f"Вам доступно {avail} минут.")
        return

    if data.startswith("buy_robokassa_"):
        st = await get_state(event)
        minutes = int(data.split("_")[-1])
        st.pop("awaiting_topup", None)

        from handlers.payments import process_robokassa_payment

        await process_robokassa_payment(event, uid, minutes)
        return

    if data.startswith("buy_stars_"):
        st = await get_state(event)
        minutes = int(data.split("_")[-1])
        st.pop("awaiting_topup", None)

        from handlers.payments import create_stars_invoice

        await create_stars_invoice(uid, minutes)
        return

    if data == "cancel":
        st = await get_state(event)
        for key in st:
            st[key] = None
        try:
            await event.edit(
                "Меню:",
                buttons=MAIN_MENU_BUTTONS,
            )
        except (
            errors.rpcerrorlist.MessageEditTimeExpiredError,
            errors.rpcerrorlist.MessageIdInvalidError,
        ) as e:
            await event.respond(
                "Меню:",
                buttons=MAIN_MENU_BUTTONS,
            )
            try:
                await event.message.delete()  # удалить старое сообщение с кнопками
            except Exception:
                pass
        return

    # fallback
    await event.respond("Нажата кнопка: " + data)
