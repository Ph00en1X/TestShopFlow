from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from html import escape
from zoneinfo import ZoneInfo

from bot.models.catalog import CartItem, Product
from bot.models.order import Order, OrderItem, OrderStatus, PaymentStatus
from bot.models.review import Review


def escape_html(value: object | None) -> str:
    return escape(str(value or ""))


def to_decimal(value) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def money(value) -> str:
    return f"{to_decimal(value):,.2f}".replace(",", " ")


def truncate(value: str | None, limit: int = 60) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def format_datetime(value, timezone_name: str) -> str:
    return value.astimezone(ZoneInfo(timezone_name)).strftime("%Y-%m-%d %H:%M")


def order_status_label(status: OrderStatus) -> str:
    mapping = {
        OrderStatus.pending: "Ожидает подтверждения",
        OrderStatus.confirmed: "Подтверждён",
        OrderStatus.shipped: "Отправлен",
        OrderStatus.delivered: "Доставлен",
        OrderStatus.cancelled: "Отменён",
    }
    return mapping.get(status, status.value.title())


def payment_status_label(status: PaymentStatus) -> str:
    mapping = {
        PaymentStatus.unpaid: "Не оплачен",
        PaymentStatus.paid: "Оплачен",
        PaymentStatus.refunded: "Возврат",
    }
    return mapping.get(status, status.value.title())


def format_welcome_text(shop_name: str, full_name: str) -> str:
    return (
        f"👋 Добро пожаловать, <b>{escape_html(full_name)}</b>!\n\n"
        f"<b>{escape_html(shop_name or 'ShopFlow')}</b> — магазин прямо в Telegram.\n"
        f"Откройте каталог, добавьте товары в корзину, оформите заказ и отслеживайте его статус."
    )


def format_help_text() -> str:
    return (
        "<b>Как пользоваться ботом</b>\n\n"
        "1. Откройте каталог\n"
        "2. Выберите категорию и товар\n"
        "3. Добавьте товар в корзину\n"
        "4. Оформите заказ\n"
        "5. Получите инструкцию по оплате\n"
        "6. Дождитесь ручного подтверждения администратора\n\n"
        "<b>Команды</b>\n"
        "/start — главное меню\n"
        "/cart — открыть корзину\n"
        "/orders — мои заказы\n"
        "/help — помощь\n"
        "/cancel — отменить текущее действие"
    )


def format_product_text(product: Product, rating: float | None, review_count: int) -> str:
    lines = [f"<b>{escape_html(product.title)}</b>"]

    if product.description:
        lines.append("")
        lines.append(escape_html(product.description))

    lines.append("")
    lines.append(f"💰 <b>{money(product.price)}</b>")

    if product.category:
        lines.append(f"📁 Категория: <b>{escape_html(product.category.name)}</b>")

    if product.sizes:
        lines.append(f"📏 Размеры: <b>{escape_html(', '.join(map(str, product.sizes)))}</b>")

    if review_count > 0 and rating is not None:
        lines.append(f"⭐ Рейтинг: <b>{rating:.1f}</b> ({review_count})")
    else:
        lines.append("⭐ Отзывов пока нет")

    return "\n".join(lines)


def _option_text(options: dict | None) -> str:
    if not options:
        return ""
    parts: list[str] = []
    for key, value in options.items():
        if value in (None, ""):
            continue
        label = key.replace("_", " ").title()
        parts.append(f"{escape_html(label)}: {escape_html(value)}")
    if not parts:
        return ""
    return f" ({', '.join(parts)})"


def _cart_line(item: CartItem) -> str:
    title = escape_html(item.product.title)
    options = _option_text(item.selected_options)
    line_total = item.product.price * item.quantity
    return f"• {title}{options} ×{item.quantity} — {money(line_total)}"


def format_cart_text(items: list[CartItem], total: Decimal) -> str:
    lines = ["🛒 <b>Ваша корзина</b>", ""]
    lines.extend(_cart_line(item) for item in items)
    lines.append("")
    lines.append(f"💵 <b>Итого: {money(total)}</b>")
    return "\n".join(lines)


def format_checkout_preview(
    contact_name: str,
    contact_info: str,
    comment: str | None,
    items: list[CartItem],
    total: Decimal,
) -> str:
    lines = [
        "📋 <b>Сводка заказа</b>",
        "",
        f"👤 <b>{escape_html(contact_name)}</b>",
        f"📞 <b>{escape_html(contact_info)}</b>",
    ]

    if comment:
        lines.append(f"💬 {escape_html(comment)}")

    lines.append("")
    lines.extend(_cart_line(item) for item in items)
    lines.append("")
    lines.append(f"💵 <b>Итого: {money(total)}</b>")
    return "\n".join(lines)


def _order_item_line(item: OrderItem) -> str:
    title = escape_html(item.product_title)
    options = _option_text(item.options)
    line_total = item.unit_price * item.quantity
    return f"• {title}{options} ×{item.quantity} — {money(line_total)}"


def format_order_detail(order: Order, timezone_name: str, include_contact: bool = False) -> str:
    lines = [
        f"📦 <b>Заказ #{order.id}</b>",
        "",
        f"Статус: <b>{order_status_label(order.status)}</b>",
        f"Оплата: <b>{payment_status_label(order.payment_status)}</b>",
        f"Создан: <b>{format_datetime(order.created_at, timezone_name)}</b>",
    ]

    if include_contact:
        lines.extend(
            [
                f"Имя: <b>{escape_html(order.contact_name)}</b>",
                f"Контакт: <b>{escape_html(order.contact_info)}</b>",
            ]
        )
        if order.comment:
            lines.append(f"Комментарий: {escape_html(order.comment)}")

    lines.append("")
    lines.extend(_order_item_line(item) for item in order.items)
    lines.append("")
    lines.append(f"💵 <b>Итого: {money(order.total_price)}</b>")
    return "\n".join(lines)


def format_admin_order_notification(order: Order, timezone_name: str) -> str:
    return f"🛍 <b>Новый заказ</b>\n\n{format_order_detail(order, timezone_name, include_contact=True)}"


def format_reviews_text(reviews: list[Review], include_product_title: bool = False) -> str:
    if not reviews:
        return "⭐ <b>Отзывов пока нет</b>"

    lines = ["⭐ <b>Отзывы</b>", ""]
    for review in reviews:
        header = f"⭐ {review.rating}/5 — <b>{escape_html(review.user.full_name)}</b>"
        if include_product_title and review.product:
            header += f" · <b>{escape_html(review.product.title)}</b>"
        lines.append(header)
        lines.append(escape_html(truncate(review.text, 500)))
        lines.append("")
    return "\n".join(lines).strip()


def format_admin_product_text(product: Product, timezone_name: str) -> str:
    category_name = product.category.name if product.category else "Без категории"
    status = "Активен" if product.is_active else "Неактивен"
    sizes = ", ".join(map(str, product.sizes)) if product.sizes else "—"
    images_count = len(product.images or [])
    broadcast_state = "в очереди" if product.is_active and product.broadcasted_at is None else "отправлена"

    return (
        f"📦 <b>{escape_html(product.title)}</b>\n\n"
        f"Статус: <b>{status}</b>\n"
        f"Категория: <b>{escape_html(category_name)}</b>\n"
        f"Цена: <b>{money(product.price)}</b>\n"
        f"Размеры: <b>{escape_html(sizes)}</b>\n"
        f"Изображений: <b>{images_count}</b>\n"
        f"Рассылка: <b>{broadcast_state}</b>\n"
        f"Создан: <b>{format_datetime(product.created_at, timezone_name)}</b>\n\n"
        f"{escape_html(product.description or 'Описание отсутствует')}"
    )


def format_broadcast_product_text(product: Product) -> str:
    description = truncate(product.description, 220) if product.description else None
    lines = [
        "🆕 <b>Новый товар</b>",
        "",
        f"<b>{escape_html(product.title)}</b>",
        f"💰 <b>{money(product.price)}</b>",
    ]
    if description:
        lines.extend(["", escape_html(description)])
    return "\n".join(lines)