from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.models.base import AsyncSessionLocal
from bot.services.cart import CartService
from bot.services.catalog import CatalogService
from bot.services.notification import NotificationService
from bot.services.order import OrderService
from bot.services.payment import PaymentService
from bot.services.product import ProductService
from bot.services.review import ReviewService
from bot.services.user import UserService
from config import Settings


@dataclass(slots=True)
class AppServices:
    bot: Bot
    settings: Settings
    session: AsyncSession

    users: UserService = field(init=False)
    catalog: CatalogService = field(init=False)
    products: ProductService = field(init=False)
    cart: CartService = field(init=False)
    orders: OrderService = field(init=False)
    payment: PaymentService = field(init=False)
    notifications: NotificationService = field(init=False)
    reviews: ReviewService = field(init=False)

    def __post_init__(self) -> None:
        self.users = UserService(self.session, self.settings)
        self.catalog = CatalogService(self.session)
        self.products = ProductService(self.session)
        self.cart = CartService(self.session, self.settings)
        self.orders = OrderService(self.session, self.settings)
        self.payment = PaymentService(self.settings)
        self.notifications = NotificationService(self.bot, self.settings)
        self.reviews = ReviewService(self.session)


class AppContainer:
    def __init__(
        self,
        bot: Bot,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
    ) -> None:
        self.bot = bot
        self.settings = settings
        self.session_factory = session_factory

    @classmethod
    async def create(cls, bot: Bot, settings: Settings) -> "AppContainer":
        return cls(bot=bot, settings=settings)

    @asynccontextmanager
    async def request_context(self):
        async with self.session_factory() as session:
            services = AppServices(
                bot=self.bot,
                settings=self.settings,
                session=session,
            )
            try:
                yield services
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def close(self) -> None:
        return None