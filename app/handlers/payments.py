import logging
import json
from telethon import events, Button, types, functions
from client_provider import client
from config import (
    RUB_PER_MIN,
    STARS_PER_MIN,
    STARS_TEST,
    ROBOKASSA_RESULT_URL,
)
from db import record_transaction, add_balance
from robokassa_service import robokassa
from robokassa.types import InvoiceType
from ui_components import show_persistent_menu

logger = logging.getLogger(__name__)


async def process_robokassa_payment(event, user_id, minutes):
    amount_val = float(minutes) * float(RUB_PER_MIN)
    payment_id = await record_transaction(
        user_id=user_id,
        provider="robokassa",
        amount=amount_val,
        status="pending",
        metadata={},
    )
    receipt = {
        "user_id": user_id,  # Система налогообложения (например, ОСН, УСН и т.д.)
    }
    payment_link = await robokassa.generate_protected_payment_link(
        invoice_type=InvoiceType.REUSABLE,
        out_sum=amount_val,
        inv_id=payment_id,
        shp_user_id=user_id,
        result_url=ROBOKASSA_RESULT_URL,
        merchant_comments=f"Покупка минут на сумму {amount_val}",
        receipt=receipt,
    )

    try:
        await event.edit(
            f"Итого - {amount_val:.2f}руб. Нажмите кнопку ниже, чтобы оплатить:",
            buttons=[
                [Button.url("Оплатить Robokassa", payment_link.url)],
            ],
        )
    except (
        errors.rpcerrorlist.MessageEditTimeExpiredError,
        errors.rpcerrorlist.MessageIdInvalidError,
    ) as e:
        await event.respond(
            f"Итого - {amount_val:.2f}руб. Нажмите кнопку ниже, чтобы оплатить:",
            buttons=[
                [Button.url("Оплатить Robokassa", payment_link.url)],
            ],
        )
        try:
            await event.message.delete()  # удалить старое сообщение с кнопками
        except Exception:
            pass
    return


async def create_stars_invoice(user_id: int, credits: int):
    """
    Создаёт и отправляет invoice в Stars (XTR) пользователю user_id.
    payload: topup:{user_id}:{credits}
    """
    try:
        stars_amount = credits * STARS_PER_MIN
        # Для XTR предполагаем, что smallest unit == 1 star. Если у вас другое (например exp != 0), скорректируйте.
        label = f"{credits} мин ({stars_amount} ⭐)"
        price = types.LabeledPrice(label=label, amount=int(stars_amount))
        invoice = types.Invoice(
            currency="XTR",
            prices=[price],
            test=STARS_TEST,  # если тестовый режим
        )

        payload = f"topup:{user_id}:{credits}"
        provider = ""  # для Stars provider обычно пустой (Bot API uses empty provider_token for XTR)
        provider_data = types.DataJSON(json.dumps({}))

        media = types.InputMediaInvoice(
            title=f"Пополнение {credits} минут",
            description=f"Покупка {credits} минут для TTS-бота",
            invoice=invoice,
            payload=payload.encode("utf-8"),
            provider=provider,
            provider_data=provider_data,
            start_param=f"topup_{user_id}_{credits}",
        )

        # Отправим invoice как "file" — так, как это делается в Telethon-примерах.
        await client.send_message(
            user_id, "Пожалуйста, завершите оплату ниже:", file=media
        )
        logger.info(
            "Stars invoice sent to %s (credits=%s, stars=%s)",
            user_id,
            credits,
            stars_amount,
        )
    except Exception as e:
        logger.exception("Failed to create/send Stars invoice: %s", e)
        # оповестим юзера об ошибке
        try:
            await client.send_message(
                user_id, "Ошибка при создании инвойса. Попробуйте позже."
            )
        except Exception:
            pass


@client.on(events.Raw(types.UpdateBotPrecheckoutQuery))
async def _stars_precheckout_handler(event: types.UpdateBotPrecheckoutQuery):
    """
    Вызывается, когда пользователь ввёл платёжные данные и Telegram ждёт подтверждение от бота.
    Нужно подтвердить через messages.SetBotPrecheckoutResultsRequest.
    """
    try:
        # payload приходит в event.payload (bytes)
        payload = event.payload.decode("utf-8") if event.payload else ""
        logger.info(
            "Received precheckout: query_id=%s payload=%s total_amount=%s user_id=%s",
            getattr(event, "query_id", None),
            payload,
            getattr(event, "total_amount", None),
            getattr(event, "user_id", None),
        )

        # Простейшая логика: если payload выглядит как topup:<uid>:<credits> -> подтверждаем
        if payload.startswith("topup:"):
            # здесь можно вставить проверку в базе: есть ли ожидающая транзакция, совпадает ли сумма и т.п.
            await client(
                functions.messages.SetBotPrecheckoutResultsRequest(
                    query_id=event.query_id, success=True, error=None
                )
            )
            logger.info("Precheckout accepted for query_id=%s", event.query_id)
        else:
            # на всякий случай — отклоним, если payload не узнаваем
            await client(
                functions.messages.SetBotPrecheckoutResultsRequest(
                    query_id=event.query_id, success=False, error="Invalid payload"
                )
            )
            logger.warning("Precheckout rejected (invalid payload): %s", payload)
    except Exception as e:
        logger.exception("Error in precheckout handler: %s", e)
        # в случае внутренней ошибки всегда отсылаем ошибку клиенту
        try:
            await client(
                functions.messages.SetBotPrecheckoutResultsRequest(
                    query_id=event.query_id, success=False, error="Internal error"
                )
            )
        except Exception:
            pass
    finally:
        # остановим дальнейшую обработку этого update другими хендлерами (как в примерах Telethon)
        raise events.StopPropagation


# --- Обработчик успешных платежей (MessageActionPaymentSentMe) ---
@client.on(events.Raw(types.UpdateNewMessage))
async def _stars_payment_received(event: types.UpdateNewMessage):
    """
    Отлавливаем MessageActionPaymentSentMe — когда оплата успешно совершена.
    В event.message.action лежит MessageActionPaymentSentMe.
    """
    try:
        if not hasattr(event, "message") or not getattr(event, "message", None):
            return

        action = event.message.action
        if not isinstance(action, types.MessageActionPaymentSentMe):
            return

        payload = action.payload.decode("utf-8") if action.payload else ""
        total_amount = getattr(action, "total_amount", None)
        logger.info(
            "Payment received: payload=%s total_amount=%s", payload, total_amount
        )

        # Ожидаемый payload формата topup:<user_id>:<credits>
        if payload.startswith("topup:"):
            try:
                _, uid_s, credits_s = payload.split(":", 2)
                uid = int(uid_s)
                credits = int(credits_s)
            except Exception:
                logger.warning("Unexpected topup payload format: %s", payload)
                uid = None
                credits = None

            # Если парсинг прошёл — положим минуты пользователю и запишем транзакцию
            if uid and credits:
                try:
                    await add_balance(uid, credits)
                except Exception:
                    logger.exception("add_balance failed for user %s", uid)

                # записываем транзакцию (если у вас есть record_transaction)
                try:
                    await record_transaction(
                        user_id=uid,
                        provider="stars",
                        amount=float(total_amount)
                        if total_amount is not None
                        else None,
                        status="succeeded",
                        metadata={"payload": payload},
                    )
                except Exception:
                    logger.exception("record_transaction failed for user %s", uid)

                # уведомим пользователя (можно использовать peer info из event.message)
                try:
                    # если event.message.peer_id.user_id доступен
                    peer_uid = None
                    if isinstance(event.message.peer_id, types.PeerUser):
                        peer_uid = event.message.peer_id.user_id
                    # fallback на uid из payload
                    if not peer_uid:
                        peer_uid = uid

                    await show_persistent_menu(
                        client,
                        uid,
                        caption=f"Оплата принята — зачислено {credits} минут. Спасибо!",
                    )
                except Exception:
                    logger.exception("Failed to notify user after payment")
        else:
            logger.info("Payment received with non-topup payload: %s", payload)

    except Exception as e:
        logger.exception("Error handling payment received: %s", e)
    finally:
        # чтобы аналогично не пропускать дальнейшую обработку
        raise events.StopPropagation
