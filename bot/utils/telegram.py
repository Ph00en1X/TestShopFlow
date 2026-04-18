from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message


async def safe_delete(message: Message | None) -> None:
    if message is None:
        return
    try:
        await message.delete()
    except Exception:
        return


async def replace_with_new_text(message: Message, text: str, reply_markup=None) -> Message:
    sent = await message.answer(text, reply_markup=reply_markup)
    await safe_delete(message)
    return sent


async def edit_or_replace(message: Message, text: str, reply_markup=None) -> Message:
    try:
        result = await message.edit_text(text, reply_markup=reply_markup)
        return result if isinstance(result, Message) else message
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return message
        return await replace_with_new_text(message, text, reply_markup)