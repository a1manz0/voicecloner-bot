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


logger = logging.getLogger("uvicorn.error")


class TextRequest(BaseModel):
    text: str


app = FastAPI()


@app.post("/webhook/robokassa")
async def robokassa_webhook(request: Request):
    form = await request.form()
    data = dict(form)
    logger.info(f"Webhook received: {data}")
    logger.info(f"Webhook received: {request}")

    try:
        out_sum = float(data["OutSum"])
        inv_id = int(data["InvId"])
        signature = data["SignatureValue"]
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing field: {e}")

    # Проверяем подпись официальным методом Robokassa
    additional_params = {k: v for k, v in data.items() if k.startswith("shp_")}
    logger.info(f"ВАЛИДАЦИЯ")
    if not robokassa.is_result_notification_valid(
        out_sum=data["OutSum"],
        inv_id=data["InvId"],
        signature=data["SignatureValue"],
    ):
        logger.info(f"ВАЛИДАЦИЯ НЕ ПРОЙДЕНА")
        raise HTTPException(status_code=400, detail="Invalid signature")

    logger.info(f"ВАЛИДАЦИЯ ПРОЙДЕНА")
    # Получаем транзакцию из БД
    tx = await get_transaction(inv_id)
    user_id = tx.get("user_id")
    if not tx:
        payment_id = await record_transaction(
            user_id=user_id,
            provider="robokassa",
            amount=out_sum,
            status="pending",
            metadata={},
        )
        # raise HTTPException(status_code=404, detail="Transaction not found")

    # Если уже подтверждено — просто отвечаем OK
    if tx["status"] == "success":
        return Response(content=f"OK{inv_id}", media_type="text/plain")

    # Обновляем статус в БД
    await update_transaction_status(inv_id, "success")

    # Начисляем баланс пользователю
    await add_balance(user_id, out_sum / RUB_PER_MIN)

    # Robokassa требует ответ в виде OK{InvId}
    return Response(content=f"OK{inv_id}", media_type="text/plain")


@app.post("/webhook/yookassa")
async def yookassa_webhook(request: Request):
    """
    Обработка уведомлений от YooKassa.
    ЮKassa присылает JSON с информацией о платеже; в metadata мы положили user_id и credits.
    В документации ЮKassa описаны заголовки/подпись — сверяйте и используйте проверку подписи.
    """
    body = await request.body()
    # Прим.: ЮKassa может присылать заголовок Webhook-Signature (см документацию).
    # Пример проверки — зависит от версия API. Если не нужно — просто парсите body.
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail="invalid json")

    # Простой пример: при event payment.succeeded
    print("body", body)
    print("data", data)
    obj = data.get("object") or data
    event = data.get("event") or data.get("type")
    # адаптировать под фактическую структуру уведомления
    if event and ("payment" in event and "succeeded" in event):
        payment = obj.get("payment") or obj
        metadata = payment.get("metadata") or {}
        user_id = int(metadata.get("user_id"))
        credits = int(metadata.get("credits"))
        await add_balance(user_id, credits)
        return {"ok": True}
    return {"ok": False}


@app.post("/webhook/cloudpayments")
async def cloudpayments_webhook(request: Request, x_sign: str = Header(None)):
    """
    Обработка webhook от CloudPayments.
    CloudPayments рекомендует проверять подпись и статус транзакции.
    Документация: https://developers.cloudpayments.ru
    """
    body = await request.body()
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400)
    # ПРИМЕР проверки подписи (уточните в доке конкретный заголовок)
    if CLOUDPAYMENTS_SECRET:
        # часто CloudPayments не подписывает таким header; это псевдокод — проверьте у них
        # пример HMAC-SHA256:
        sig = base64.b64encode(
            hmac.new(CLOUDPAYMENTS_SECRET.encode(), body, hashlib.sha256).digest()
        ).decode()
        # сравнение сигнатур (если header содержит sig)
        # if x_sign != sig: raise HTTPException(status_code=403)

    # Здесь payload содержит поля: ["Model"]["Amount"], ["Model"]["InvoiceId"], ["Model"]["AccountId"] ...
    model = payload.get("Model") or payload
    account_id = model.get("AccountId") or payload.get("AccountId")
    amount = model.get("Amount") or 0
    # Найдите user_id и credits: возможно храните в InvoiceId или AccountId
    try:
        user_id = int(account_id)
    except Exception:
        # если InvoiceId содержит user_id — раскодируйте
        # invoice = model.get("InvoiceId")
        return {"ok": False}

    # Простой перевод суммы в кредиты (в зависимости от вашей ценовой политики)
    credits = int(round(float(amount) / float(RUB_PER_MIN)))
    await add_balance(user_id, credits)
    return {"ok": True}
