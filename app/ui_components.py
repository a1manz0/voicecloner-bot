from telethon import Button, types
from config import (
    RUB_PER_MIN,
    STARS_PER_MIN,
)

MAIN_MENU_BUTTONS_COMMANDS = [
    [("/выбрать_голос", "Выбрать голос")],
    [("/купить_минуты", "Пополнить минуты")],
    [("/баланс", "Мой баланс")],
    [("/помощь", "Инструкция")],
]
HELP_TEXT = (
    "<b>Привет!</b> 👋\n"
    "Я — <b>TTS-бот</b> 🎙️\n\n"
    "<b>Бот предоставляет 1 бесплатную минуту в месяц.</b>\n\n"
    "<b>Чтобы загрузить референс-голос:</b>\n"
    "Просто отправьте <b>аудио-файл</b> или запишите <b>голосовое</b>.\n\n"
    "<b>Чтобы начать синтез речи:</b>\n"
    "Просто отправьте <b>текст</b>.\n\n"
    "<b>Чтобы указать ударение в слове:</b>\n"
    "Ставьте <code>+</code> перед буквой, на которую нужно поставить ударение.\n"
    "<i>Пример:</i> <code>молок+о</code>\n\n"
    "<b>Чтобы указать паузу:</b>\n"
    "Используйте формат <code>[пауза n]</code>, где <b>n</b> — длительность паузы в секундах.\n"
    "<i>Пример:</i> <code>Привет [пауза 1] как дела?</code>\n\n"
    "<b>Команды для управления ботом:</b>\n"
    "- <code>/старт</code> или <code>/меню</code> — показать <b>главное меню</b>\n"
    "- <code>/выбрать_голос</code> — <b>выбрать голос</b> для синтеза\n"
    "- <code>/купить_минуты</code> — <b>пополнить минуты</b>\n"
    "- <code>/баланс</code> — узнать <b>текущий баланс</b>\n"
    "- <code>/помощь</code> — показать <b>эту инструкцию</b>\n"
    "- <code>/ogg</code> — отправлять как <b>голосовое сообщение</b>\n"
    "- <code>/ogg</code> — отправлять как <b>голосовое сообщение</b>\n"
    "- <code>/вкл_автоударение</code> — Включить <b>автоматическую растановку ударений</b>\n"
    "- <code>/выкл_автоударение</code> — Выключить <b>автоматическую растановку ударений</b>\n\n"
    "Задать вопрос/сообщить о баге: https://t.me/ask_garage\n"
    "Канал с новостями о проекте: https://t.me/a1manz001"
)
MAIN_MENU_BUTTONS = [
    [Button.switch_inline("Загрузить референс (аудио)", b"upload_ref")],
    [Button.switch_inline("Выбрать голос", b"choose_voice")],
    [Button.switch_inline("Пополнить минуты", b"buy_credits")],
    [Button.switch_inline("Мой баланс", b"my_balance")],
]
VOICE_CHOICE_BUTTONS = [
    [
        Button.inline("Голос 1 (Муж)", b"voice:1"),
        Button.inline("Голос 2 (Жен)", b"voice:2"),
    ],
    # [
    #    Button.inline("Вернуться в меню", b"cancel"),
    # ],
]
BUY_CREDITS_BUTTONS = [
    [
        Button.inline("Robokassa (карта)", b"topup_robokassa"),
        Button.inline("Telegram Stars", b"topup_stars"),
    ],
    # [Button.inline("Вернуться в меню", b"cancel")],
]
TOPUP_ROBOKASSA_BUTTONS = [
    [Button.inline(f"1 мин ({RUB_PER_MIN} ₽)", b"buy_robokassa_1")],
    [Button.inline(f"5 мин ({5 * RUB_PER_MIN} ₽)", b"buy_robokassa_5")],
    [Button.inline(f"10 мин ({10 * RUB_PER_MIN} ₽)", b"buy_robokassa_10")],
    [Button.inline(f"100 мин ({100 * RUB_PER_MIN} ₽)", b"buy_robokassa_100")],
    # [Button.inline("Вернуться в меню", b"cancel")],
]

TOPUP_STARS_BUTTONS = [
    [Button.inline(f"1 мин ({STARS_PER_MIN} ⭐)", b"buy_stars_1")],
    [Button.inline(f"5 мин ({5 * STARS_PER_MIN} ⭐)", b"buy_stars_5")],
    [Button.inline(f"10 мин ({10 * STARS_PER_MIN} ⭐)", b"buy_stars_10")],
    [Button.inline(f"100 мин ({100 * STARS_PER_MIN} ⭐)", b"buy_stars_100")],
    # [Button.inline("Вернуться в меню", b"cancel")],
]


async def show_persistent_menu(client, chat_id, caption="Меню:"):
    rows = []
    for row in MAIN_MENU_BUTTONS_COMMANDS:
        kb_buttons = [types.KeyboardButton(text=command) for command, _label in row]
        rows.append(types.KeyboardButtonRow(buttons=kb_buttons))

    reply_markup = types.ReplyKeyboardMarkup(
        rows,
        resize=True,
        single_use=False,
        persistent=True,
    )

    await client.send_message(chat_id, caption, buttons=reply_markup, parse_mode="html")
