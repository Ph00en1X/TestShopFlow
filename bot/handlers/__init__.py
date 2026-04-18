from __future__ import annotations

from aiogram import Dispatcher

from bot.handlers.admin.panel import router as admin_panel_router
from bot.handlers.admin.products import router as admin_products_router
from bot.handlers.common.errors import router as errors_router
from bot.handlers.common.start import router as start_router
from bot.handlers.user.cart import router as cart_router
from bot.handlers.user.catalog import router as catalog_router
from bot.handlers.user.checkout import router as checkout_router
from bot.handlers.user.orders import router as orders_router
from bot.handlers.user.reviews import router as reviews_router


def register_routers(dp: Dispatcher) -> None:
    dp.include_router(start_router)
    dp.include_router(catalog_router)
    dp.include_router(cart_router)
    dp.include_router(checkout_router)
    dp.include_router(orders_router)
    dp.include_router(reviews_router)
    dp.include_router(admin_panel_router)
    dp.include_router(admin_products_router)
    dp.include_router(errors_router)