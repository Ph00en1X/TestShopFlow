from __future__ import annotations

import asyncio
import logging
from typing import Iterable

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.models.catalog import Product
from bot.models.order import Order
from bot.utils.formatters import (
    format_admin_order_notification,
    format_broadcast_product_text,
    money,
    order_status_label,
    payment_status_label,
)
from config import Settings

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, bot: Bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings
        self._bot_username: str | None = None

    async def _send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> bool:
        for _ in range(2):
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    disable_web_page_preview=True,
                )
                return True
            except TelegramRetryAfter as exc:
                await asyncio.sleep(float(exc.retry_after))
            except TelegramForbiddenError:
                logger.warning("Пользователь %s заблокировал бота", chat_id)
                return False
            except TelegramBadRequest as exc:
                logger.warning("Не удалось отправить сообщение пользователю %s: %s", chat_id, exc)
                return False
            except Exception as exc:
                logger.exception("Ошибка отправки сообщения пользователю %s: %s", chat_id, exc)
                return False
        return False

    async def _send_photo(
        self,
        chat_id: int,
        photo: str,
        caption: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> bool:
        for _ in range(2):
            try:
                await self.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=caption,
                    reply_markup=reply_markup,
                )
                return True
            except TelegramRetryAfter as exc:
                await asyncio.sleep(float(exc.retry_after))
            except TelegramForbiddenError:
                logger.warning("Пользователь %s заблокировал бота", chat_id)
                return False
            except TelegramBadRequest as exc:
                logger.warning("Не удалось отправить фото пользователю %s: %s", chat_id, exc)
                return False
            except Exception as exc:
                logger.exception("Ошибка отправки фото пользователю %s: %s", chat_id, exc)
                return False
        return False

    async def _get_bot_username(self) -> str | None:
        if self._bot_username is not None:
            return self._bot_username
        try:
            me = await self.bot.get_me()
            self._bot_username = me.username
        except Exception:
            self._bot_username = None
        return self._bot_username

    async def _build_product_link_markup(self, product_id: int) -> InlineKeyboardMarkup | None:
        username = await self._get_bot_username()
        if not username:
            return None

        builder = InlineKeyboardBuilder()
        builder.button(
            text="Открыть товар",
            url=f"https://t.me/{username}?start=product_{product_id}",
        )
        builder.adjust(1)
        return builder.as_markup()

    def _chunked(self, items: Iterable[int], size: int) -> list[list[int]]:
        chunks: list[list[int]] = []
        current: list[int] = []

        for item in items:
            current.append(item)
            if len(current) >= size:
                chunks.append(current)
                current = []

        if current:
            chunks.append(current)

        return chunks

    async def notify_admins_new_order(self, order: Order) -> None:
        if not self.settings.ADMIN_IDS:
            return

        from bot.keyboards.admin import order_management_kb

        text = format_admin_order_notification(order, self.settings.TIMEZONE)
        markup = order_management_kb(order)

        for admin_id in sorted({item for item in self.settings.ADMIN_IDS if item > 0}):
            await self._send_message(admin_id, text, reply_markup=markup)

    async def notify_user_order_status(self, telegram_id: int, order: Order) -> None:
        text = (
            f"📦 <b>Заказ #{order.id}</b>\n"
            f"Статус: <b>{order_status_label(order.status)}</b>\n"
            f"Оплата: <b>{payment_status_label(order.payment_status)}</b>"
        )
        await self._send_message(telegram_id, text)

    async def notify_user_payment_confirmed(self, telegram_id: int, order_id: int) -> None:
        text = (
            f"✅ <b>Оплата подтверждена</b>\n\n"
            f"Оплата по заказу <b>#{order_id}</b> успешно подтверждена."
        )
        await self._send_message(telegram_id, text)

    async def remind_unpaid_order(self, telegram_id: int, order_id: int, total) -> None:
        text = (
            f"⏰ <b>Напоминание об оплате</b>\n\n"
            f"Заказ: <b>#{order_id}</b>\n"
            f"Сумма: <b>{money(total)}</b>\n\n"
            f"Пожалуйста, оплатите заказ, чтобы он не был отменён автоматически."
        )
        await self._send_message(telegram_id, text)

    async def broadcast_new_product(self, recipient_ids: list[int], product: Product) -> int:
        unique_recipients = list(dict.fromkeys(int(item) for item in recipient_ids if int(item) > 0))
        if not unique_recipients:
            return 0

        text = format_broadcast_product_text(product)
        markup = await self._build_product_link_markup(product.id)

        async def send_one(chat_id: int) -> bool:
            if product.images:
                if await self._send_photo(chat_id, product.images[0], text, reply_markup=markup):
                    return True
            return await self._send_message(chat_id, text, reply_markup=markup)

        sent = 0
        chunk_size = max(1, min(self.settings.BROADCAST_CHUNK_SIZE, 30))
        delay = max(0, self.settings.BROADCAST_DELAY_MS) / 1000

        for chunk in self._chunked(unique_recipients, chunk_size):
            results = await asyncio.gather(
                *(send_one(chat_id) for chat_id in chunk),
                return_exceptions=True,
            )
            sent += sum(1 for item in results if item is True)
            if delay:
                await asyncio.sleep(delay)

        return sent