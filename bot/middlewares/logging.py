from __future__ import annotations

import logging
from time import perf_counter

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

logger = logging.getLogger(__name__)


def _mask_payload(value: str) -> str:
    text = value.strip().replace("\n", " ")
    if len(text) > 160:
        return text[:160] + "..."
    return text or "-"


def _describe_event(event: Message | CallbackQuery) -> tuple[int | None, int | None, str]:
    user_id = getattr(getattr(event, "from_user", None), "id", None)

    if isinstance(event, Message):
        chat_id = getattr(getattr(event, "chat", None), "id", None)
        if event.contact:
            payload = "контакт"
        elif event.text:
            payload = _mask_payload(event.text)
        else:
            payload = f"<{event.content_type}>"
        return user_id, chat_id, payload

    if isinstance(event, CallbackQuery):
        chat_id = getattr(getattr(event.message, "chat", None), "id", None)
        payload = _mask_payload(event.data or "")
        return user_id, chat_id, payload

    return user_id, None, "-"


class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        started_at = perf_counter()
        user_id, chat_id, payload = _describe_event(event)

        logger.debug(
            "Получено обновление type=%s user=%s chat=%s payload=%s",
            type(event).__name__,
            user_id,
            chat_id,
            payload,
        )

        try:
            return await handler(event, data)
        finally:
            logger.debug(
                "Обновление обработано type=%s user=%s chat=%s duration=%.3fs",
                type(event).__name__,
                user_id,
                chat_id,
                perf_counter() - started_at,
            )