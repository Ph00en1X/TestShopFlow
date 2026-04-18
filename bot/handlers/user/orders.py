from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.common.presenters import render_orders
from bot.core.container import AppServices
from bot.keyboards.user import MENU_ORDERS, order_detail_kb
from bot.models.user import User
from bot.utils.formatters import format_order_detail
from bot.utils.telegram import edit_or_replace

router = Router()


@router.message(Command("orders"))
async def cmd_orders(
    message: Message,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    await state.clear()
    await render_orders(message, db_user, services, edit=False)


@router.message(F.text == MENU_ORDERS)
async def menu_orders(
    message: Message,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    await state.clear()
    await render_orders(message, db_user, services, edit=False)


@router.callback_query(F.data == "orders:list")
async def callback_orders_list(
    call: CallbackQuery,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    if call.message is None:
        await call.answer()
        return

    await state.clear()
    await render_orders(call.message, db_user, services, edit=True)
    await call.answer()


@router.callback_query(F.data.startswith("order:"))
async def callback_order_detail(
    call: CallbackQuery,
    db_user: User,
    services: AppServices,
) -> None:
    if call.message is None:
        await call.answer()
        return

    order_id = int(call.data.split(":")[1])
    order = await services.orders.get_user_order(order_id, db_user.id)

    await edit_or_replace(
        call.message,
        format_order_detail(order, services.settings.TIMEZONE, include_contact=False),
        reply_markup=order_detail_kb(),
    )
    await call.answer()