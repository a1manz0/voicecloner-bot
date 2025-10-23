import os

ACCENT_URL = os.getenv("ACCENT_URL", "")
API_TOKEN = os.getenv("API_TOKEN", "")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

PG_HOST = os.getenv("PG_HOST", "postgres")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
PG_DB = os.getenv("POSTGRES_DB", "postgres")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
GRADIO_URL = os.getenv("GRADIO_URL", "http://127.0.0.1:7860")

FREE_CREDITS_PER_DAY = int(os.getenv("FREE_CREDITS_PER_DAY", "5"))

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
RUB_PER_MIN = float(os.getenv("RUB_PER_MIN", "16"))  # price per 1 credit
STARS_PER_MIN = float(os.getenv("STARS_PER_MIN", "9"))  # price per 1 credit
STARS_TEST = os.getenv("STARS_TEST", "0") == "1"
WEBHOOK_BASE = os.getenv("WEBHOOK_BASE", "https://example.com")  # for return URLs

WORKER_NUMBER = int(os.getenv("WORKER_NUMBER", "1"))
