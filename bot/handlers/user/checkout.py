from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.core.container import AppServices
from bot.keyboards.user import confirm_checkout_kb
from bot.models.states import CheckoutFlow
from bot.models.user import User
from bot.utils.formatters import format_checkout_preview
from bot.utils.telegram import edit_or_replace

router = Router()


@router.callback_query(F.data == "checkout:start")
async def callback_checkout_start(
    call: CallbackQuery,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    items, _ = await services.cart.get_cart_snapshot(db_user.id)
    if not items:
        await call.answer("Корзина пуста.", show_alert=True)
        return

    await state.clear()
    await state.set_state(CheckoutFlow.waiting_name)
    await call.message.answer("Введите ваше имя:")
    await call.answer()


@router.message(CheckoutFlow.waiting_name)
async def checkout_waiting_name(
    message: Message,
    state: FSMContext,
    services: AppServices,
) -> None:
    contact_name = services.orders.validate_contact_name(message.text)
    await state.update_data(contact_name=contact_name)
    await state.set_state(CheckoutFlow.waiting_contact)
    await message.answer("Введите телефон или другой контакт для связи:")


@router.message(CheckoutFlow.waiting_contact)
async def checkout_waiting_contact(
    message: Message,
    state: FSMContext,
    services: AppServices,
) -> None:
    raw_contact = message.contact.phone_number if message.contact else message.text
    contact_info = services.orders.validate_contact_info(raw_contact)
    await state.update_data(contact_info=contact_info)
    await state.set_state(CheckoutFlow.waiting_comment)
    await message.answer("Добавьте комментарий к заказу или напишите <b>пропустить</b>.")


@router.message(CheckoutFlow.waiting_comment)
async def checkout_waiting_comment(
    message: Message,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    comment = services.orders.normalize_comment(message.text)
    data = await state.get_data()
    contact_name = data.get("contact_name")
    contact_info = data.get("contact_info")

    if not contact_name or not contact_info:
        await state.clear()
        await message.answer("Сессия оформления истекла. Начните заново.")
        return

    await state.update_data(comment=comment)

    items, total = await services.cart.get_cart_snapshot(db_user.id)
    if not items:
        await state.clear()
        await message.answer("Корзина пуста. Сначала добавьте товары.")
        return

    await message.answer(
        format_checkout_preview(contact_name, contact_info, comment, items, total),
        reply_markup=confirm_checkout_kb(),
    )


@router.callback_query(F.data == "checkout:confirm")
async def callback_checkout_confirm(
    call: CallbackQuery,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    if call.message is None:
        await call.answer()
        return

    data = await state.get_data()
    contact_name = data.get("contact_name")
    contact_info = data.get("contact_info")
    comment = data.get("comment")

    if not contact_name or not contact_info:
        await state.clear()
        await call.answer("Сессия оформления истекла. Начните заново.", show_alert=True)
        return

    order = await services.orders.create_order_from_cart(
        user_id=db_user.id,
        contact_name=contact_name,
        contact_info=contact_info,
        comment=comment,
    )
    await state.clear()

    await edit_or_replace(
        call.message,
        services.payment.generate_instructions(order),
    )
    await services.notifications.notify_admins_new_order(order)
    await call.answer("Заказ создан.")


@router.callback_query(F.data == "checkout:cancel")
async def callback_checkout_cancel(call: CallbackQuery, state: FSMContext) -> None:
    if call.message is not None:
        await edit_or_replace(call.message, "Оформление заказа отменено.")
    await state.clear()
    await call.answer()