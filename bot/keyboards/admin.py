from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.models.catalog import Product
from bot.models.order import Order, OrderStatus, PaymentStatus
from bot.utils.formatters import money, order_status_label, truncate


def admin_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Последние заказы", callback_data="admin:orders")
    builder.button(text="📦 Товары", callback_data="admin:products")
    builder.button(text="➕ Добавить товар", callback_data="admin:add_product")
    builder.adjust(1)
    return builder.as_markup()


def admin_orders_kb(orders: list[Order]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for order in orders:
        user_name = truncate(order.user.full_name, 18) if order.user else "Неизвестно"
        builder.button(
            text=f"#{order.id} · {order_status_label(order.status)} · {money(order.total_price)} · {user_name}",
            callback_data=f"admin:order:{order.id}",
        )
    builder.button(text="⬅️ Назад", callback_data="admin:panel")
    builder.adjust(1)
    return builder.as_markup()


def order_management_kb(order: Order) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if order.payment_status == PaymentStatus.unpaid and order.status != OrderStatus.cancelled:
        builder.button(text="✅ Подтвердить оплату", callback_data=f"admin:payment:{order.id}")

    if order.status == OrderStatus.confirmed:
        builder.button(text="🚚 Отметить как отправленный", callback_data=f"admin:status:{order.id}:{OrderStatus.shipped.value}")

    if order.status == OrderStatus.shipped:
        builder.button(text="📦 Отметить как доставленный", callback_data=f"admin:status:{order.id}:{OrderStatus.delivered.value}")

    if order.status not in {OrderStatus.cancelled, OrderStatus.delivered}:
        builder.button(text="❌ Отменить заказ", callback_data=f"admin:status:{order.id}:{OrderStatus.cancelled.value}")

    builder.button(text="⬅️ К заказам", callback_data="admin:orders")
    builder.adjust(1)
    return builder.as_markup()


def admin_products_kb(products: list[Product]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for product in products:
        status = "🟢" if product.is_active else "⚪"
        builder.button(
            text=f"{status} {truncate(product.title, 28)} · {money(product.price)}",
            callback_data=f"admin:product:{product.id}",
        )
    builder.button(text="➕ Добавить товар", callback_data="admin:add_product")
    builder.button(text="⬅️ Назад", callback_data="admin:panel")
    builder.adjust(1)
    return builder.as_markup()


def admin_product_detail_kb(product: Product) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if product.is_active:
        builder.button(text="🗑 Деактивировать", callback_data=f"admin:delete_product:{product.id}")
    else:
        builder.button(text="✅ Активировать", callback_data=f"admin:activate_product:{product.id}")
    builder.button(text="⬅️ К товарам", callback_data="admin:products")
    builder.adjust(1)
    return builder.as_markup()


def cancel_admin_flow_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отменить", callback_data="admin:cancel_flow")
    builder.adjust(1)
    return builder.as_markup()