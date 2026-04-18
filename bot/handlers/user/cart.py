from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.common.presenters import render_cart
from bot.core.container import AppServices
from bot.keyboards.user import MENU_CART
from bot.models.user import User

router = Router()


@router.message(Command("cart"))
async def cmd_cart(
    message: Message,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    await state.clear()
    await render_cart(message, db_user, services, edit=False)


@router.message(F.text == MENU_CART)
async def menu_cart(
    message: Message,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    await state.clear()
    await render_cart(message, db_user, services, edit=False)


@router.callback_query(F.data == "cart:open")
async def callback_cart_open(
    call: CallbackQuery,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    if call.message is None:
        await call.answer()
        return

    await state.clear()
    await render_cart(call.message, db_user, services, edit=True)
    await call.answer()


@router.callback_query(F.data.startswith("add_to_cart:"))
async def callback_add_to_cart(call: CallbackQuery, db_user: User, services: AppServices) -> None:
    _, product_id, raw_size_index = call.data.split(":")
    size_index = int(raw_size_index)
    await services.cart.add_item(
        user_id=db_user.id,
        product_id=int(product_id),
        size_index=None if size_index < 0 else size_index,
    )
    await call.answer("Товар добавлен в корзину.")


@router.callback_query(F.data.startswith("remove_from_cart:"))
async def callback_remove_from_cart(
    call: CallbackQuery,
    db_user: User,
    services: AppServices,
) -> None:
    if call.message is None:
        await call.answer()
        return

    item_id = int(call.data.split(":")[1])
    await services.cart.remove_item(db_user.id, item_id)
    await render_cart(call.message, db_user, services, edit=True)
    await call.answer("Товар удалён из корзины.")


@router.callback_query(F.data == "cart:clear")
async def callback_clear_cart(
    call: CallbackQuery,
    db_user: User,
    services: AppServices,
) -> None:
    if call.message is None:
        await call.answer()
        return

    await services.cart.clear_cart(db_user.id)
    await render_cart(call.message, db_user, services, edit=True)
    await call.answer("Корзина очищена.")