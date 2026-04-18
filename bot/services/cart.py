from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.core.exceptions import CartLimitExceededError, NotFoundError, ProductUnavailableError, ValidationError
from bot.models.catalog import CartItem, Product
from config import Settings


class CartService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def _options_key(self, options: dict | None) -> str:
        if not options:
            return ""
        return json.dumps(options, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    def _build_selected_options(self, product: Product, size_index: int | None) -> dict | None:
        if product.sizes:
            if size_index is None or size_index < 0 or size_index >= len(product.sizes):
                raise ValidationError("Выберите корректный размер.")
            return {"size": str(product.sizes[size_index])}
        return None

    async def get_cart(self, user_id: int) -> list[CartItem]:
        result = await self.session.execute(
            select(CartItem)
            .options(selectinload(CartItem.product))
            .where(CartItem.user_id == user_id)
            .order_by(CartItem.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_item(self, user_id: int, item_id: int) -> CartItem:
        result = await self.session.execute(
            select(CartItem)
            .options(selectinload(CartItem.product))
            .where(
                CartItem.id == item_id,
                CartItem.user_id == user_id,
            )
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise NotFoundError("позиция корзины", item_id)
        return item

    async def count_items(self, user_id: int) -> int:
        result = await self.session.execute(
            select(func.count(CartItem.id)).where(CartItem.user_id == user_id)
        )
        return int(result.scalar_one() or 0)

    async def get_cart_snapshot(self, user_id: int) -> tuple[list[CartItem], Decimal]:
        items = await self.get_cart(user_id)
        total = sum((item.product.price * item.quantity for item in items), Decimal("0.00"))
        return items, total

    async def add_item(
        self,
        user_id: int,
        product_id: int,
        quantity: int = 1,
        size_index: int | None = None,
    ) -> CartItem:
        if quantity <= 0:
            raise ValidationError("Количество должно быть больше нуля.")
        if quantity > 99:
            raise ValidationError("Максимальное количество одного товара — 99.")

        product_result = await self.session.execute(
            select(Product).where(
                Product.id == product_id,
                Product.is_active.is_(True),
            )
        )
        product = product_result.scalar_one_or_none()
        if product is None:
            raise ProductUnavailableError("Этот товар сейчас недоступен.")

        selected_options = self._build_selected_options(product, size_index)
        options_key = self._options_key(selected_options)

        result = await self.session.execute(
            select(CartItem).where(
                CartItem.user_id == user_id,
                CartItem.product_id == product_id,
                CartItem.options_key == options_key,
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            if existing.quantity + quantity > 99:
                raise ValidationError("Максимальное количество одного товара — 99.")
            existing.quantity += quantity
            await self.session.commit()
            return await self.get_item(user_id, existing.id)

        if await self.count_items(user_id) >= self.settings.MAX_CART_ITEMS:
            raise CartLimitExceededError(f"Достигнут лимит корзины: {self.settings.MAX_CART_ITEMS} позиций.")

        item = CartItem(
            user_id=user_id,
            product_id=product_id,
            quantity=quantity,
            selected_options=selected_options,
            options_key=options_key,
        )
        self.session.add(item)

        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            result = await self.session.execute(
                select(CartItem).where(
                    CartItem.user_id == user_id,
                    CartItem.product_id == product_id,
                    CartItem.options_key == options_key,
                )
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                raise ValidationError("Не удалось добавить товар в корзину.")
            if existing.quantity + quantity > 99:
                raise ValidationError("Максимальное количество одного товара — 99.")
            existing.quantity += quantity
            await self.session.commit()
            return await self.get_item(user_id, existing.id)

        return await self.get_item(user_id, item.id)

    async def remove_item(self, user_id: int, item_id: int) -> None:
        await self.session.execute(
            delete(CartItem).where(
                CartItem.id == item_id,
                CartItem.user_id == user_id,
            )
        )
        await self.session.commit()

    async def clear_cart(self, user_id: int) -> None:
        await self.session.execute(delete(CartItem).where(CartItem.user_id == user_id))
        await self.session.commit()