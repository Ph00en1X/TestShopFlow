from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.common.presenters import render_recent_reviews
from bot.core.container import AppServices
from bot.keyboards.user import MENU_REVIEWS, review_rating_kb
from bot.models.states import ReviewFlow
from bot.models.user import User
from bot.utils.formatters import format_reviews_text

router = Router()


@router.message(F.text == MENU_REVIEWS)
async def menu_reviews(
    message: Message,
    state: FSMContext,
    services: AppServices,
) -> None:
    await state.clear()
    await render_recent_reviews(message, services)


@router.callback_query(F.data.startswith("reviews:list:"))
async def callback_product_reviews(
    call: CallbackQuery,
    state: FSMContext,
    services: AppServices,
) -> None:
    if call.message is None:
        await call.answer()
        return

    await state.clear()
    product_id = int(call.data.split(":")[2])
    reviews = await services.reviews.get_product_reviews(product_id, limit=10)

    if not reviews:
        await call.answer("Отзывов пока нет.", show_alert=True)
        return

    await call.message.answer(format_reviews_text(reviews, include_product_title=False))
    await call.answer()


@router.callback_query(F.data.startswith("reviews:start:"))
async def callback_review_start(
    call: CallbackQuery,
    state: FSMContext,
    services: AppServices,
) -> None:
    product_id = int(call.data.split(":")[2])
    await services.catalog.get_product(product_id)

    await state.clear()
    await state.set_state(ReviewFlow.waiting_text)
    await state.update_data(product_id=product_id)
    await call.message.answer("Напишите текст отзыва:")
    await call.answer()


@router.message(ReviewFlow.waiting_text)
async def review_waiting_text(
    message: Message,
    state: FSMContext,
    services: AppServices,
) -> None:
    review_text = services.reviews.validate_text(message.text)
    data = await state.get_data()
    product_id = data.get("product_id")

    if not product_id:
        await state.clear()
        await message.answer("Сессия отзыва истекла. Начните заново.")
        return

    await state.update_data(review_text=review_text)
    await state.set_state(ReviewFlow.waiting_rating)
    await message.answer(
        "Выберите оценку:",
        reply_markup=review_rating_kb(int(product_id)),
    )


@router.callback_query(F.data.startswith("reviews:rate:"), ReviewFlow.waiting_rating)
async def callback_review_rate(
    call: CallbackQuery,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    if call.message is None:
        await call.answer()
        return

    parts = call.data.split(":")
    rating = int(parts[3])

    data = await state.get_data()
    product_id = data.get("product_id")
    review_text = data.get("review_text")

    if not product_id or not review_text:
        await state.clear()
        await call.answer("Сессия отзыва истекла. Начните заново.", show_alert=True)
        return

    await services.reviews.create_review(
        user_id=db_user.id,
        product_id=int(product_id),
        text=review_text,
        rating=services.reviews.validate_rating(rating),
    )
    await state.clear()
    await call.message.edit_text("✅ Отзыв отправлен. Спасибо!")
    await call.answer()