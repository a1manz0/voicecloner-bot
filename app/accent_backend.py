# app/webhooks.py
import hmac
import hashlib
import base64
from fastapi import FastAPI, Header, Request, Response, HTTPException
from pydantic import BaseModel
from db import (
    update_transaction_status,
    get_transaction,
    add_balance,
    record_transaction,
)
from config import RUB_PER_MIN, STARS_PER_MIN, API_TOKEN
import json, asyncio
from robokassa_service import robokassa
import logging
from accentizer import accentizer


logger = logging.getLogger("uvicorn.error")


class TextRequest(BaseModel):
    text: str


app = FastAPI()


@app.post("/accent")
async def accent_text(
    request: TextRequest,
    x_api_token: str | None = Header(None),  # токен передаём в заголовке
):
    # Проверка токена
    if x_api_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API token")

    # Обработка текста через ruaccent
    accented_text = accentizer.process_all(request.text.strip())

    return {"accented_text": accented_text}
