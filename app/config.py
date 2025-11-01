import os, requests

ACCENT_URL = os.getenv("ACCENT_URL", "")
API_TOKEN = os.getenv("API_TOKEN", "")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

FISH_API_KEY = os.getenv("FISH_API_KEY", "")

PG_HOST = os.getenv("PG_HOST", "postgres")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
PG_DB = os.getenv("POSTGRES_DB", "postgres")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
GRADIO_URL = os.getenv("GRADIO_URL")

FREE_CREDITS_PER_DAY = int(os.getenv("FREE_CREDITS_PER_DAY", "1"))

OUTPUT_DIR = os.path.join("/out")
REFS_DIR = os.path.join("/refs")
REF_VOICE_1 = os.getenv("REF_VOICE_1", "/refs/ref_1.ogg")
REF_VOICE_2 = os.getenv("REF_VOICE_2", "/refs/ref_2.ogg")

YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
ROBOKASSA_LOGIN = os.getenv("ROBOKASSA_LOGIN", "")
ROBOKASSA_PASS_1 = os.getenv("ROBOKASSA_PASS_1", "")
ROBOKASSA_PASS_2 = os.getenv("ROBOKASSA_PASS_2", "")
ROBOKASSA_TEST_PASS_1 = os.getenv("ROBOKASSA_TEST_PASS_1", "")
ROBOKASSA_TEST_PASS_2 = os.getenv("ROBOKASSA_TEST_PASS_2", "")
ROBOKASSA_RESULT_URL = os.getenv("ROBOKASSA_RESULT_URL", "")


TELEGRAM_PROVIDER_TOKEN = os.getenv(
    "TELEGRAM_PROVIDER_TOKEN", ""
)  # optional (BotFather)
RUB_PER_MIN = float(os.getenv("RUB_PER_MIN", "13"))  # price per 1 credit
STARS_PER_MIN = float(os.getenv("STARS_PER_MIN", "8"))  # price per 1 credit
STARS_TEST = os.getenv("STARS_TEST", "0") == "1"
WEBHOOK_BASE = os.getenv("WEBHOOK_BASE", "https://example.com")  # for return URLs

WORKER_NUMBER = int(os.getenv("WORKER_NUMBER", "1"))

DIRECTUS_URL = os.environ.get("DIRECTUS_URL")
DIRECTUS_TOKEN = os.environ.get("DIRECTUS_TOKEN")
DIRECTUS_COLLECTION = os.environ.get("DIRECTUS_SETTINGS_COLLECTION", "settings")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "settings")
VC_PROXY_API_KEY = os.environ.get("VC_PROXY_API_KEY")
VC_PROXY_BACKEND_URL = os.environ.get("VC_PROXY_BACKEND_URL")


HELP_TEXT = (
    "<b>Привет!</b> 👋\n"
    "Я — <b>TTS-бот</b> 🎙️\n\n"
    "<b>Бот предоставляет 1 бесплатную минуту в месяц.</b>\n\n"
    "Доступны 2 модели <b>F5-TTS и OpenAudio S1</b>. По умолчанию используется F5-TTS.\n\n"
    "<b>Чтобы загрузить референс-голос:</b>\n"
    "Просто отправьте <b>аудио-файл</b> или запишите <b>голосовое</b>.\n\n"
    "<b>Чтобы начать синтез речи:</b>\n"
    "Просто отправьте <b>текст</b>.\n\n"
    "<b>Чтобы указать ударение в слове (только для модели F5-TTS):</b>\n"
    "Ставьте <code>+</code> перед буквой, на которую нужно поставить ударение.\n"
    "<i>Пример:</i> <code>молок+о</code>\n\n"
    "<b>Чтобы указать паузу:</b>\n"
    "Используйте формат <code>[пауза n]</code>, где <b>n</b> — длительность паузы в секундах.\n"
    "<i>Пример:</i> <code>Привет [пауза 1] как дела?</code>\n\n"
    "<b>Команды для управления ботом:</b>\n"
    "- <code>/старт</code> или <code>/меню</code> — показать <b>главное меню</b>\n"
    "- <code>/помощь</code> — показать <b>эту инструкцию</b>\n"
    "- <code>/выбрать_модель</code> — <b>выбрать модель</b> для синтеза (F5-TTS или OpenAudio S1)\n"
    "- <code>/выбрать_голос</code> — <b>выбрать голос</b> для синтеза\n"
    "- <code>/купить_минуты</code> — <b>пополнить минуты</b>\n"
    "- <code>/баланс</code> — узнать <b>текущий баланс</b>\n"
    "- <code>/ogg</code> — отправлять как <b>голосовое сообщение</b>\n"
    "- <code>/mp3</code> — отправлять как <b>mp3 файл</b>\n"
    "- <code>/вкл_автоударение</code> — Включить <b>автоматическую растановку ударений</b>\n"
    "- <code>/выкл_автоударение</code> — Выключить <b>автоматическую растановку ударений</b>\n\n"
    "Задать вопрос/сообщить о баге: https://t.me/ask_garage\n"
    "Канал с новостями о проекте: https://t.me/a1manz001"
)


def load_settings_from_directus():
    """
    Загружает настройки из Directus и перезаписывает глобальные
    переменные этого модуля (config.py).
    """

    # Проверяем, что URL и коллекция вообще заданы
    if not DIRECTUS_URL or not DIRECTUS_COLLECTION:
        print(
            "DIRECTUS_URL или DIRECTUS_COLLECTION не заданы. "
            "Используются переменные окружения/значения по умолчанию."
        )
        return

    api_url = f"{DIRECTUS_URL}/items/{DIRECTUS_COLLECTION}"
    headers = {}

    if DIRECTUS_TOKEN:
        headers["Authorization"] = f"Bearer {DIRECTUS_TOKEN}"

    print(f"Попытка загрузки настроек из Directus: {api_url}")

    try:
        # Используем обычный синхронный requests, как вы и просили
        response = requests.get(api_url, headers=headers, timeout=5)

        # Проверяем на ошибки (4xx, 5xx)
        response.raise_for_status()

        data = response.json()

        print(data)
        if "data" not in data:
            print(
                "Ответ от Directus не содержит 'data' или список пуст. "
                "Используются значения по умолчанию."
            )
            return

        # Получаем первый (и единственный) элемент настроек
        directus_settings = data["data"]

        # Получаем доступ к глобальным переменным этого (config.py) модуля
        current_module_globals = globals()

        updated_vars = []
        # Начинаем динамическую перезапись
        for key, value in directus_settings.items():
            # Преобразуем ключ из Directus (напр. 'rub_per_min')
            # в имя переменной конфига (напр. 'RUB_PER_MIN')
            var_name = key.upper()

            # Проверяем, существует ли такая переменная в config.py
            if var_name in current_module_globals:
                if value is None:
                    print(
                        f"Настройка '{var_name}' (поле '{key}') из Directus имеет значение None. "
                        f"Используется текущее значение: {current_module_globals[var_name]}"
                    )
                    continue  # Переходим к следующей настройке
                try:
                    # Получаем ОРИГИНАЛЬНЫЙ тип переменной (int, float, str)
                    original_type = type(current_module_globals[var_name])

                    # Пытаемся привести значение из Directus к этому типу
                    # Это важно, чтобы '13.0' (str) стал 13.0 (float)
                    new_value = original_type(value)

                    # Перезаписываем глобальную переменную
                    current_module_globals[var_name] = new_value
                    updated_vars.append(
                        f"{var_name} = {new_value} (тип: {original_type.__name__})"
                    )

                except (ValueError, TypeError) as e:
                    # Ошибка приведения типа (например, пытаемся 'abc' привести к int)
                    print(
                        f"Не удалось применить настройку {var_name}: "
                        f"не удалось привести значение '{value}' "
                        f"к типу {original_type.__name__}. Ошибка: {e}"
                    )
                except Exception as e:
                    print(f"Неизвестная ошибка при обновлении {var_name}: {e}")

        if updated_vars:
            print("Настройки из Directus успешно загружены и применены:")
            for var_info in updated_vars:
                print(f"  -> {var_info}")
        else:
            print(
                "Настройки из Directus загружены, "
                "но не найдено совпадений с переменными в config.py."
            )

    except requests.exceptions.RequestException as e:
        print(
            f"Ошибка при подключении к Directus: {e}. "
            "Бот продолжит работу со значениями по умолчанию."
        )
    except Exception as e:
        print(
            f"Неожиданная ошибка при обработке настроек Directus: {e}. "
            "Бот продолжит работу со значениями по умолчанию."
        )


# --- ВЫПОЛНЕНИЕ ФУНКЦИИ ПРИ ИМПОРТЕ ---
# Этот код будет выполнен один раз, когда bot.py сделает 'import config'
load_settings_from_directus()
