from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.core.exceptions import EmptyCartError, NotFoundError, OrderStateError, ProductUnavailableError, ValidationError
from bot.models.base import utcnow
from bot.models.catalog import CartItem
from bot.models.order import Order, OrderItem, OrderStatus, PaymentStatus
from config import Settings


class OrderService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def validate_contact_name(self, value: str | None) -> str:
        name = str(value or "").strip()
        if len(name) < 2:
            raise ValidationError("Введите корректное имя.")
        if len(name) > 255:
            raise ValidationError("Имя слишком длинное.")
        return name

    def validate_contact_info(self, value: str | None) -> str:
        contact = str(value or "").strip()
        if len(contact) < 3:
            raise ValidationError("Введите корректный контакт для связи.")
        if len(contact) > 255:
            raise ValidationError("Контакт слишком длинный.")
        return contact

    def normalize_comment(self, value: str | None) -> str | None:
        text = str(value or "").strip()
        if text.lower() in {"", "skip", "none", "-", "пропустить", "нет"}:
            return None
        if len(text) > 1000:
            raise ValidationError("Комментарий слишком длинный.")
        return text

    async def create_order_from_cart(
        self,
        user_id: int,
        contact_name: str,
        contact_info: str,
        comment: str | None,
    ) -> Order:
        validated_name = self.validate_contact_name(contact_name)
        validated_contact = self.validate_contact_info(contact_info)
        normalized_comment = self.normalize_comment(comment)
        now = utcnow()

        result = await self.session.execute(
            select(CartItem)
            .options(selectinload(CartItem.product))
            .where(CartItem.user_id == user_id)
            .order_by(CartItem.id.asc())
        )
        cart_items = list(result.scalars().all())

        if not cart_items:
            raise EmptyCartError("Корзина пуста.")

        total = Decimal("0.00")
        for item in cart_items:
            if item.product is None or not item.product.is_active:
                raise ProductUnavailableError("Один или несколько товаров больше недоступны.")
            total += item.product.price * item.quantity

        order = Order(
            user_id=user_id,
            total_price=total,
            contact_name=validated_name,
            contact_info=validated_contact,
            comment=normalized_comment,
            payment_status=PaymentStatus.unpaid,
            status=OrderStatus.pending,
            payment_instructions_sent_at=now,
            status_updated_at=now,
        )
        self.session.add(order)
        await self.session.flush()

        for item in cart_items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                product_title=item.product.title,
                quantity=item.quantity,
                unit_price=item.product.price,
                options=item.selected_options,
            )
            self.session.add(order_item)

        await self.session.execute(delete(CartItem).where(CartItem.user_id == user_id))
        await self.session.commit()

        return await self.get_admin_order(order.id)

    async def get_user_orders(self, user_id: int, limit: int = 20) -> list[Order]:
        result = await self.session.execute(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_order(self, order_id: int, user_id: int) -> Order:
        result = await self.session.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(
                Order.id == order_id,
                Order.user_id == user_id,
            )
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise NotFoundError("заказ", order_id)
        return order

    async def get_admin_orders(self, limit: int = 30) -> list[Order]:
        result = await self.session.execute(
            select(Order)
            .options(selectinload(Order.user))
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_admin_order(self, order_id: int) -> Order:
        result = await self.session.execute(
            select(Order)
            .options(
                selectinload(Order.user),
                selectinload(Order.items),
            )
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise NotFoundError("заказ", order_id)
        return order

    async def confirm_payment(self, order_id: int) -> Order:
        order = await self.get_admin_order(order_id)
        if order.status == OrderStatus.cancelled:
            raise OrderStateError("Нельзя подтвердить оплату для отменённого заказа.")

        if order.payment_status != PaymentStatus.paid:
            order.payment_status = PaymentStatus.paid
            order.paid_at = utcnow()

        if order.status == OrderStatus.pending:
            order.status = OrderStatus.confirmed
            order.status_updated_at = utcnow()

        await self.session.commit()
        return await self.get_admin_order(order_id)

    def _validate_transition(self, current: OrderStatus, new: OrderStatus, payment_status: PaymentStatus) -> None:
        if current == new:
            return

        allowed = {
            OrderStatus.pending: {OrderStatus.cancelled},
            OrderStatus.confirmed: {OrderStatus.shipped, OrderStatus.cancelled},
            OrderStatus.shipped: {OrderStatus.delivered, OrderStatus.cancelled},
            OrderStatus.delivered: set(),
            OrderStatus.cancelled: set(),
        }

        if new not in allowed[current]:
            raise OrderStateError(f"Нельзя изменить статус с «{current.value}» на «{new.value}».")

        if new in {OrderStatus.shipped, OrderStatus.delivered} and payment_status != PaymentStatus.paid:
            raise OrderStateError("Перед отправкой нужно подтвердить оплату.")

    async def update_status(self, order_id: int, new_status: OrderStatus) -> Order:
        order = await self.get_admin_order(order_id)
        self._validate_transition(order.status, new_status, order.payment_status)

        if order.status != new_status:
            order.status = new_status
            order.status_updated_at = utcnow()
            if new_status == OrderStatus.cancelled:
                order.cancelled_at = utcnow()

        await self.session.commit()
        return await self.get_admin_order(order_id)

    async def get_due_unpaid_orders(self, limit: int = 100) -> list[Order]:
        now = utcnow()
        due_from = now - timedelta(hours=self.settings.PAYMENT_REMINDER_AFTER_HOURS)
        interval_from = now - timedelta(hours=self.settings.PAYMENT_REMINDER_INTERVAL_HOURS)

        result = await self.session.execute(
            select(Order)
            .options(selectinload(Order.user))
            .where(
                Order.status == OrderStatus.pending,
                Order.payment_status == PaymentStatus.unpaid,
                Order.created_at <= due_from,
                or_(
                    Order.last_reminder_at.is_(None),
                    Order.last_reminder_at <= interval_from,
                ),
            )
            .order_by(Order.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_reminder_sent(self, order_id: int) -> None:
        order = await self.get_admin_order(order_id)
        order.last_reminder_at = utcnow()
        await self.session.commit()

    async def expire_unpaid_orders(self, limit: int = 100) -> list[Order]:
        now = utcnow()
        expired_before = now - timedelta(hours=self.settings.ORDER_EXPIRY_HOURS)

        result = await self.session.execute(
            select(Order)
            .options(selectinload(Order.user))
            .where(
                Order.status == OrderStatus.pending,
                Order.payment_status == PaymentStatus.unpaid,
                Order.created_at <= expired_before,
            )
            .order_by(Order.created_at.asc())
            .limit(limit)
        )
        orders = list(result.scalars().all())

        if not orders:
            return []

        for order in orders:
            order.status = OrderStatus.cancelled
            order.cancelled_at = now
            order.status_updated_at = now

        await self.session.commit()
        return orders