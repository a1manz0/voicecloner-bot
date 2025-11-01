from telethon import events, errors
from client_provider import client
from db import ensure_user, get_available_credits, set_user_mode, set_auto_accent
from state import get_state
from ui_components import (
    show_persistent_menu,
    VOICE_CHOICE_BUTTONS,
    MODEL_CHOICE_BUTTONS,
    BUY_CREDITS_BUTTONS,
)
import config


# Обработчики команд
@client.on(events.NewMessage(pattern="/update"))
async def update_handler(event):
    user_id = event.sender_id
    if user_id == 588440387:
        config.load_settings_from_directus()


@client.on(events.NewMessage(pattern="/ogg"))
async def ogg_handler(event):
    user_id = event.sender_id
    st = await get_state(event)
    st["mode"] = "ogg"
    await set_user_mode(user_id, mode="ogg")
    # await event.reply("Результат будет отправляться в виде голосовых сообщений")
    await show_persistent_menu(
        client,
        event.chat_id,
        caption="Результат будет отправляться в виде голосовых сообщений",
    )


@client.on(events.NewMessage(pattern="/mp3"))
async def mp3_handler(event):
    user_id = event.sender_id
    st = await get_state(event)
    st["mode"] = "mp3"
    await set_user_mode(user_id, mode="mp3")
    # await event.reply("Результат будет отправляться в виде mp3 файлов")
    await show_persistent_menu(
        client, event.chat_id, caption="Результат будет отправляться в виде mp3 файлов"
    )


@client.on(events.NewMessage(pattern=r"^/(start|menu|старт|меню)$"))
async def start_handler(event):
    uid = event.sender_id
    chat_id = event.chat_id
    sender = await event.get_sender()  # загрузит User (или None)
    username = getattr(sender, "username", None)  # может быть None
    await ensure_user(uid, username=username)
    await show_persistent_menu(client, chat_id, caption=config.HELP_TEXT)


@client.on(events.NewMessage(pattern=r"^/(choose_voice|выбрать_голос)$"))
async def choose_voice_handler(event):
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


@client.on(events.NewMessage(pattern=r"^/(choose_model|выбрать_модель)$"))
async def choose_model_handler(event):
    try:
        await event.edit("Выберите модель синтеза речи:", buttons=MODEL_CHOICE_BUTTONS)
    except (
        errors.rpcerrorlist.MessageEditTimeExpiredError,
        errors.rpcerrorlist.MessageIdInvalidError,
    ) as e:
        await event.respond(
            "Выберите модель синтеза речи:", buttons=MODEL_CHOICE_BUTTONS
        )
        try:
            await event.message.delete()  # удалить старое сообщение с кнопками
        except Exception:
            pass
    return


@client.on(events.NewMessage(pattern=r"^/(help|помощь)$"))
async def help_handler(event):
    # await event.reply(HELP_TEXT, parse_mode="html")
    await show_persistent_menu(client, event.chat_id, caption=config.HELP_TEXT)


@client.on(events.NewMessage(pattern=r"^/(topup|купить_минуты)$"))
async def topup_cmd(event):
    uid = event.sender_id
    # Кнопки выбора провайдера
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


@client.on(events.NewMessage(pattern=r"^/(balance|баланс)$"))
async def balance_cmd(event):
    uid = event.sender_id
    sender = await event.get_sender()  # загрузит user (или none)
    username = getattr(sender, "username", None)  # может быть none
    avail = await get_available_credits(uid, username)
    # await event.reply(f"Вам доступно {avail:.4f} минут.")
    await show_persistent_menu(
        client, event.chat_id, caption=f"Вам доступно {avail:.4f} минут."
    )


@client.on(events.NewMessage(pattern=r"^/(autoaccent_off|выкл_автоударение)$"))
async def auto_accent_off(event):
    user_id = event.sender_id
    st = await get_state(event)
    st["auto_accent"] = False
    await set_auto_accent(user_id, auto_accent="False")
    # await event.reply("Автоударение выключено")
    await show_persistent_menu(client, event.chat_id, caption="Автоударение выключено")


@client.on(events.NewMessage(pattern=r"^/(autoaccent_on|вкл_автоударение)$"))
async def auto_accent_on(event):
    user_id = event.sender_id
    st = await get_state(event)
    st["auto_accent"] = True
    await set_auto_accent(user_id, auto_accent="True")
    # await event.reply("Автоударение включено")
    await show_persistent_menu(client, event.chat_id, caption="Автоударение включено")
