from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.common.presenters import render_admin_order, render_admin_orders, render_admin_panel
from bot.core.container import AppServices
from bot.keyboards.user import MENU_ADMIN
from bot.models.order import OrderStatus
from bot.models.user import User

router = Router()


@router.message(Command("admin"))
async def cmd_admin(
    message: Message,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    await state.clear()
    await render_admin_panel(message, db_user, services, edit=False)


@router.message(F.text == MENU_ADMIN)
async def menu_admin(
    message: Message,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    await state.clear()
    await render_admin_panel(message, db_user, services, edit=False)


@router.callback_query(F.data == "admin:panel")
async def callback_admin_panel(
    call: CallbackQuery,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    if call.message is None:
        await call.answer()
        return

    await state.clear()
    await render_admin_panel(call.message, db_user, services, edit=True)
    await call.answer()


@router.callback_query(F.data == "admin:orders")
async def callback_admin_orders(
    call: CallbackQuery,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    if call.message is None:
        await call.answer()
        return

    await state.clear()
    await render_admin_orders(call.message, db_user, services, edit=True)
    await call.answer()


@router.callback_query(F.data.startswith("admin:order:"))
async def callback_admin_order_detail(
    call: CallbackQuery,
    db_user: User,
    services: AppServices,
) -> None:
    if call.message is None:
        await call.answer()
        return

    order_id = int(call.data.split(":")[2])
    await render_admin_order(call.message, db_user, services, order_id, edit=True)
    await call.answer()


@router.callback_query(F.data.startswith("admin:payment:"))
async def callback_admin_confirm_payment(
    call: CallbackQuery,
    db_user: User,
    services: AppServices,
) -> None:
    if call.message is None:
        await call.answer()
        return

    services.users.ensure_admin(db_user)
    order_id = int(call.data.split(":")[2])
    order = await services.orders.confirm_payment(order_id)
    await services.notifications.notify_user_payment_confirmed(order.user.telegram_id, order.id)
    await render_admin_order(call.message, db_user, services, order_id, edit=True)
    await call.answer("Оплата подтверждена.")


@router.callback_query(F.data.startswith("admin:status:"))
async def callback_admin_change_status(
    call: CallbackQuery,
    db_user: User,
    services: AppServices,
) -> None:
    if call.message is None:
        await call.answer()
        return

    services.users.ensure_admin(db_user)
    _, _, raw_order_id, raw_status = call.data.split(":")
    order = await services.orders.update_status(
        order_id=int(raw_order_id),
        new_status=OrderStatus(raw_status),
    )
    await services.notifications.notify_user_order_status(order.user.telegram_id, order)
    await render_admin_order(call.message, db_user, services, order.id, edit=True)
    await call.answer("Статус заказа обновлён.")