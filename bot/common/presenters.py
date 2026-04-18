from __future__ import annotations

from aiogram.types import Message

from bot.core.container import AppServices
from bot.keyboards.admin import (
    admin_main_kb,
    admin_orders_kb,
    admin_product_detail_kb,
    admin_products_kb,
    order_management_kb,
)
from bot.keyboards.user import (
    back_to_catalog_kb,
    cart_kb,
    categories_kb,
    orders_kb,
    product_detail_kb,
)
from bot.models.user import User
from bot.utils.formatters import (
    escape_html,
    format_admin_product_text,
    format_cart_text,
    format_order_detail,
    format_product_text,
    format_reviews_text,
    money,
)
from bot.utils.telegram import edit_or_replace, safe_delete


async def render_catalog(message: Message, services: AppServices, edit: bool = False) -> Message:
    categories = await services.catalog.get_categories()

    if categories:
        text = "📦 <b>Каталог</b>\n\nВыберите категорию:"
        markup = categories_kb(categories)
    else:
        text = "📦 <b>Каталог</b>\n\nКатегории пока не добавлены."
        markup = None

    if edit:
        return await edit_or_replace(message, text, reply_markup=markup)
    return await message.answer(text, reply_markup=markup)


async def render_product(
    message: Message,
    services: AppServices,
    product_id: int,
    replace_source: bool = True,
) -> None:
    product = await services.catalog.get_product(product_id)
    rating, review_count = await services.reviews.get_product_rating_summary(product.id)
    text = format_product_text(product, rating, review_count)
    markup = product_detail_kb(product)

    if product.images:
        short_caption = (
            f"<b>{escape_html(product.title)}</b>\n"
            f"💰 <b>{money(product.price)}</b>"
        )
        try:
            if len(text) <= 1000:
                await message.answer_photo(
                    photo=product.images[0],
                    caption=text,
                    reply_markup=markup,
                )
            else:
                await message.answer_photo(photo=product.images[0], caption=short_caption)
                await message.answer(text, reply_markup=markup)
            if replace_source:
                await safe_delete(message)
            return
        except Exception:
            pass

    if replace_source:
        await edit_or_replace(message, text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


async def render_cart(
    message: Message,
    db_user: User,
    services: AppServices,
    edit: bool = False,
) -> Message:
    items, total = await services.cart.get_cart_snapshot(db_user.id)

    if not items:
        text = "🛒 <b>Корзина пуста</b>\n\nОткройте каталог и добавьте товары."
        if edit:
            return await edit_or_replace(message, text, reply_markup=back_to_catalog_kb())
        return await message.answer(text, reply_markup=back_to_catalog_kb())

    text = format_cart_text(items, total)
    markup = cart_kb(items)

    if edit:
        return await edit_or_replace(message, text, reply_markup=markup)
    return await message.answer(text, reply_markup=markup)


async def render_orders(
    message: Message,
    db_user: User,
    services: AppServices,
    edit: bool = False,
) -> Message:
    orders = await services.orders.get_user_orders(db_user.id)

    if not orders:
        text = "📦 <b>У вас пока нет заказов</b>\n\nОткройте каталог и оформите первый заказ."
        if edit:
            return await edit_or_replace(message, text, reply_markup=back_to_catalog_kb())
        return await message.answer(text, reply_markup=back_to_catalog_kb())

    text = "📦 <b>Ваши заказы</b>"
    markup = orders_kb(orders)

    if edit:
        return await edit_or_replace(message, text, reply_markup=markup)
    return await message.answer(text, reply_markup=markup)


async def render_recent_reviews(message: Message, services: AppServices) -> Message:
    reviews = await services.reviews.get_recent_reviews(limit=10)
    if not reviews:
        return await message.answer("⭐ <b>Отзывов пока нет</b>\n\nОставьте первый отзыв на странице товара.")
    return await message.answer(format_reviews_text(reviews, include_product_title=True))


async def render_admin_panel(
    message: Message,
    db_user: User,
    services: AppServices,
    edit: bool = False,
) -> Message:
    services.users.ensure_admin(db_user)
    text = "⚙️ <b>Панель администратора</b>\n\nВыберите действие:"
    if edit:
        return await edit_or_replace(message, text, reply_markup=admin_main_kb())
    return await message.answer(text, reply_markup=admin_main_kb())


async def render_admin_orders(
    message: Message,
    db_user: User,
    services: AppServices,
    edit: bool = False,
) -> Message:
    services.users.ensure_admin(db_user)
    orders = await services.orders.get_admin_orders(limit=30)

    if orders:
        text = "📋 <b>Последние заказы</b>"
    else:
        text = "📋 <b>Заказов пока нет</b>"

    markup = admin_orders_kb(orders)

    if edit:
        return await edit_or_replace(message, text, reply_markup=markup)
    return await message.answer(text, reply_markup=markup)


async def render_admin_order(
    message: Message,
    db_user: User,
    services: AppServices,
    order_id: int,
    edit: bool = False,
) -> Message:
    services.users.ensure_admin(db_user)
    order = await services.orders.get_admin_order(order_id)
    text = format_order_detail(order, services.settings.TIMEZONE, include_contact=True)
    markup = order_management_kb(order)

    if edit:
        return await edit_or_replace(message, text, reply_markup=markup)
    return await message.answer(text, reply_markup=markup)


async def render_admin_products(
    message: Message,
    db_user: User,
    services: AppServices,
    edit: bool = False,
) -> Message:
    services.users.ensure_admin(db_user)
    products = await services.products.list_admin_products(limit=30)

    if products:
        text = "📦 <b>Товары</b>\n\nПоследние товары:"
    else:
        text = "📦 <b>Товары пока не добавлены</b>"

    markup = admin_products_kb(products)

    if edit:
        return await edit_or_replace(message, text, reply_markup=markup)
    return await message.answer(text, reply_markup=markup)


async def render_admin_product(
    message: Message,
    db_user: User,
    services: AppServices,
    product_id: int,
    edit: bool = False,
) -> Message:
    services.users.ensure_admin(db_user)
    product = await services.products.get_product(product_id, include_inactive=True)
    text = format_admin_product_text(product, services.settings.TIMEZONE)
    markup = admin_product_detail_kb(product)

    if edit:
        return await edit_or_replace(message, text, reply_markup=markup)
    return await message.answer(text, reply_markup=markup)