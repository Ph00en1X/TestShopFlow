from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from redis.asyncio import from_url as redis_from_url

from bot.core.container import AppContainer
from bot.core.scheduler import setup_scheduler
from bot.handlers import register_routers
from bot.middlewares.logging import LoggingMiddleware
from bot.middlewares.user_context import UserContextMiddleware
from bot.models.base import init_db
from config import Settings, get_settings

logger = logging.getLogger(__name__)


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


async def build_storage(settings: Settings):
    if settings.USE_MEMORY_FSM or not settings.REDIS_URL:
        if not settings.USE_MEMORY_FSM:
            logger.warning("REDIS_URL не указан. Используется память процесса для FSM.")
        return MemoryStorage()

    try:
        redis = redis_from_url(settings.REDIS_URL)
        await redis.ping()
        await redis.aclose()
        logger.info("Хранилище FSM: Redis")
        return RedisStorage.from_url(settings.REDIS_URL)
    except Exception as exc:
        logger.warning("Redis недоступен: %s. Используется память процесса для FSM.", exc)
        return MemoryStorage()


def register_middlewares(dp: Dispatcher, container: AppContainer) -> None:
    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware(UserContextMiddleware(container))
        observer.outer_middleware(LoggingMiddleware())


async def set_bot_commands(bot: Bot, admin_ids: list[int]) -> None:
    public_commands = [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="cart", description="Открыть корзину"),
        BotCommand(command="orders", description="Мои заказы"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="cancel", description="Отменить действие"),
    ]
    admin_commands = public_commands + [
        BotCommand(command="admin", description="Панель администратора"),
    ]

    await bot.set_my_commands(public_commands, scope=BotCommandScopeDefault())

    for admin_id in sorted({item for item in admin_ids if item > 0}):
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as exc:
            logger.warning("Не удалось установить команды администратора для %s: %s", admin_id, exc)


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)

    await init_db()

    storage = await build_storage(settings)
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=storage)

    container = await AppContainer.create(bot=bot, settings=settings)

    register_middlewares(dp, container)
    register_routers(dp)

    scheduler = setup_scheduler(container)
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=False)
    await set_bot_commands(bot, settings.ADMIN_IDS)

    logger.info("Бот ShopFlow запущен")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        scheduler.shutdown(wait=False)
        await container.close()
        await storage.close()
        await bot.session.close()
        logger.info("Бот ShopFlow остановлен")


if __name__ == "__main__":
    asyncio.run(main())