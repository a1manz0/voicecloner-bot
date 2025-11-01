from telethon import Button, types
from config import (
    RUB_PER_MIN,
    STARS_PER_MIN,
    HELP_TEXT,
)

HELP_TEXT = HELP_TEXT
S1_INSTRUCTIONS = """"""
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
]
MODEL_CHOICE_BUTTONS = [
    [
        Button.inline("F5-TTS", b"model:1"),
        Button.inline("EL", b"model:3"),
        Button.inline("OpenAudio S1", b"model:2"),
    ],
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

MAIN_MENU_BUTTONS_COMMANDS = [
    [
        ("/выбрать_модель", "Выбрать модель"),
        ("/выбрать_голос", "Выбрать голос"),
    ],
    [("/купить_минуты", "Пополнить минуты"), ("/баланс", "Мой баланс")],
    [("/помощь", "Инструкция")],
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
