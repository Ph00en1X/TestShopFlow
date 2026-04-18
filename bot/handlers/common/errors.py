from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ErrorEvent

from bot.core.exceptions import AccessDeniedError, ShopFlowError

router = Router()
logger = logging.getLogger(__name__)


@router.error()
async def error_handler(event: ErrorEvent) -> bool:
    exc = event.exception

    if isinstance(exc, asyncio.CancelledError):
        raise exc

    if isinstance(exc, TelegramBadRequest) and "message is not modified" in str(exc).lower():
        return True

    if isinstance(exc, AccessDeniedError):
        text = str(exc)
        logger.warning("Отказано в доступе: %s", exc)
    elif isinstance(exc, ShopFlowError):
        text = str(exc)
        logger.warning("Бизнес-ошибка: %s", exc)
    else:
        text = "Произошла непредвиденная ошибка. Попробуйте ещё раз."
        logger.exception("Необработанная ошибка: %s", exc)

    callback = getattr(event.update, "callback_query", None)
    message = getattr(event.update, "message", None)

    if callback:
        with suppress(Exception):
            await callback.answer(text, show_alert=True)
        return True

    if message:
        with suppress(Exception):
            await message.answer(text)
        return True

    return True