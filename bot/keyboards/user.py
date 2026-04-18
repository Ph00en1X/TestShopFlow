from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from bot.models.catalog import CartItem, Category, Product
from bot.models.order import Order, OrderStatus
from bot.models.user import UserRole
from bot.utils.formatters import money, truncate

MENU_CATALOG = "📦 Каталог"
MENU_CART = "🛒 Корзина"
MENU_ORDERS = "📦 Заказы"
MENU_REVIEWS = "⭐ Отзывы"
MENU_ADMIN = "⚙️ Админ"


def _status_emoji(status: OrderStatus) -> str:
    mapping = {
        OrderStatus.pending: "⏳",
        OrderStatus.confirmed: "✅",
        OrderStatus.shipped: "🚚",
        OrderStatus.delivered: "📦",
        OrderStatus.cancelled: "❌",
    }
    return mapping.get(status, "•")


def main_menu_kb(role: UserRole = UserRole.user) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text=MENU_CATALOG)
    builder.button(text=MENU_CART)
    builder.button(text=MENU_ORDERS)
    builder.button(text=MENU_REVIEWS)
    if role == UserRole.admin:
        builder.button(text=MENU_ADMIN)
        builder.adjust(2, 2, 1)
    else:
        builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True, is_persistent=True, input_field_placeholder="Выберите действие")


def categories_kb(categories: list[Category]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        prefix = f"{category.emoji} " if category.emoji else ""
        builder.button(text=f"{prefix}{category.name}", callback_data=f"category:{category.id}")
    builder.adjust(2)
    return builder.as_markup()


def products_kb(products: list[Product]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for product in products:
        builder.button(
            text=f"{truncate(product.title, 36)} · {money(product.price)}",
            callback_data=f"product:{product.id}",
        )
    builder.button(text="⬅️ Все категории", callback_data="catalog:open")
    builder.adjust(1)
    return builder.as_markup()


def product_detail_kb(product: Product) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if product.sizes:
        for index, size in enumerate(product.sizes):
            builder.button(
                text=f"➕ Добавить {size}",
                callback_data=f"add_to_cart:{product.id}:{index}",
            )
    else:
        builder.button(text="➕ В корзину", callback_data=f"add_to_cart:{product.id}:-1")

    builder.button(text="🛒 Открыть корзину", callback_data="cart:open")
    builder.button(text="⭐ Отзывы", callback_data=f"reviews:list:{product.id}")
    builder.button(text="✍️ Оставить отзыв", callback_data=f"reviews:start:{product.id}")
    builder.button(
        text="⬅️ Назад",
        callback_data=f"category:{product.category_id}" if product.category_id else "catalog:open",
    )
    builder.adjust(1)
    return builder.as_markup()


def cart_kb(items: list[CartItem]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(
            text=f"❌ {truncate(item.product.title, 28)} ×{item.quantity}",
            callback_data=f"remove_from_cart:{item.id}",
        )
    builder.button(text="✅ Оформить заказ", callback_data="checkout:start")
    builder.button(text="🗑 Очистить корзину", callback_data="cart:clear")
    builder.button(text="📦 Продолжить покупки", callback_data="catalog:open")
    builder.adjust(1)
    return builder.as_markup()


def back_to_catalog_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Открыть каталог", callback_data="catalog:open")
    builder.adjust(1)
    return builder.as_markup()


def orders_kb(orders: list[Order]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for order in orders:
        builder.button(
            text=f"{_status_emoji(order.status)} #{order.id} · {money(order.total_price)}",
            callback_data=f"order:{order.id}",
        )
    builder.adjust(1)
    return builder.as_markup()


def order_detail_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад к заказам", callback_data="orders:list")
    builder.adjust(1)
    return builder.as_markup()


def confirm_checkout_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить заказ", callback_data="checkout:confirm")
    builder.button(text="❌ Отменить", callback_data="checkout:cancel")
    builder.adjust(1, 1)
    return builder.as_markup()


def review_rating_kb(product_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for rating in range(1, 6):
        builder.button(text=f"{rating} ⭐", callback_data=f"reviews:rate:{product_id}:{rating}")
    builder.adjust(5)
    return builder.as_markup()