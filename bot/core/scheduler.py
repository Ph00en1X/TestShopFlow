from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.core.container import AppContainer

logger = logging.getLogger(__name__)


async def send_unpaid_order_reminders(container: AppContainer) -> None:
    async with container.request_context() as services:
        orders = await services.orders.get_due_unpaid_orders(limit=100)
        if not orders:
            return

        sent = 0
        for order in orders:
            await services.notifications.remind_unpaid_order(
                telegram_id=order.user.telegram_id,
                order_id=order.id,
                total=order.total_price,
            )
            await services.orders.mark_reminder_sent(order.id)
            sent += 1

        logger.info("Отправлено напоминаний об оплате: %s", sent)


async def expire_unpaid_orders(container: AppContainer) -> None:
    async with container.request_context() as services:
        orders = await services.orders.expire_unpaid_orders(limit=100)
        if not orders:
            return

        for order in orders:
            await services.notifications.notify_user_order_status(
                telegram_id=order.user.telegram_id,
                order=order,
            )

        logger.info("Автоматически отменено неоплаченных заказов: %s", len(orders))


async def broadcast_new_products(container: AppContainer) -> None:
    async with container.request_context() as services:
        products = await services.products.get_pending_broadcast_products(limit=1)
        if not products:
            return

        recipients = await services.users.get_broadcast_recipients()

        for product in products:
            delivered = await services.notifications.broadcast_new_product(recipients, product)
            await services.products.mark_broadcasted(product.id)
            logger.info("Рассылка товара #%s завершена, доставлено: %s", product.id, delivered)


def setup_scheduler(container: AppContainer) -> AsyncIOScheduler:
    tz = ZoneInfo(container.settings.TIMEZONE)
    now = datetime.now(tz)
    scheduler = AsyncIOScheduler(timezone=tz)

    scheduler.add_job(
        send_unpaid_order_reminders,
        trigger="interval",
        minutes=30,
        kwargs={"container": container},
        id="shopflow_unpaid_reminders",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
        next_run_time=now,
    )
    scheduler.add_job(
        expire_unpaid_orders,
        trigger="interval",
        minutes=60,
        kwargs={"container": container},
        id="shopflow_expire_orders",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
        next_run_time=now,
    )
    scheduler.add_job(
        broadcast_new_products,
        trigger="interval",
        minutes=10,
        kwargs={"container": container},
        id="shopflow_product_broadcasts",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
        next_run_time=now,
    )

    return scheduler