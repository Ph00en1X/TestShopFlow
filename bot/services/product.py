from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.core.exceptions import NotFoundError, ValidationError
from bot.models.base import utcnow
from bot.models.catalog import Category, Product


class ProductService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def validate_title(self, value: str) -> str:
        title = str(value or "").strip()
        if len(title) < 2:
            raise ValidationError("Название товара должно содержать минимум 2 символа.")
        if len(title) > 255:
            raise ValidationError("Название товара слишком длинное.")
        return title

    def normalize_description(self, value: str | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if text.lower() in {"skip", "none", "-", "пропустить", "нет"}:
            return None
        if len(text) > 3000:
            raise ValidationError("Описание слишком длинное.")
        return text or None

    def parse_price(self, value: str | int | float | Decimal) -> Decimal:
        raw = str(value).strip().replace(",", ".")
        try:
            amount = Decimal(raw)
        except InvalidOperation as exc:
            raise ValidationError("Некорректная цена.") from exc
        amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if amount <= 0:
            raise ValidationError("Цена должна быть больше нуля.")
        return amount

    def normalize_category_name(self, value: str | None) -> str:
        name = str(value or "").strip()
        if len(name) < 2:
            raise ValidationError("Название категории должно содержать минимум 2 символа.")
        if len(name) > 120:
            raise ValidationError("Название категории слишком длинное.")
        return name

    def parse_sizes(self, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []

        if isinstance(value, list):
            items = [str(item).strip() for item in value]
        else:
            raw = str(value).strip()
            if raw.lower() in {"", "skip", "none", "-", "пропустить", "нет"}:
                return []
            items = [item.strip() for item in raw.split(",")]

        result: list[str] = []
        for item in items:
            if not item:
                continue
            if len(item) > 32:
                raise ValidationError("Значение размера слишком длинное.")
            if item not in result:
                result.append(item)

        if len(result) > 20:
            raise ValidationError("Слишком много вариантов размеров.")
        return result

    def should_finish_image_collection(self, value: str | None) -> bool:
        return str(value or "").strip().lower() in {"готово", "done", "skip", "пропустить", "-", "стоп"}

    def _normalize_images(self, images: list[str] | None) -> list[str]:
        if not images:
            return []
        result: list[str] = []
        for item in images:
            text = str(item or "").strip()
            if not text:
                continue
            if text not in result:
                result.append(text)
        return result[:10]

    async def _get_or_create_category(self, category_name: str) -> Category:
        result = await self.session.execute(
            select(Category).where(func.lower(Category.name) == category_name.lower())
        )
        category = result.scalar_one_or_none()
        if category is not None:
            if not category.is_active:
                category.is_active = True
            return category

        category = Category(name=category_name, is_active=True)
        self.session.add(category)
        await self.session.flush()
        return category

    async def create_category(self, name: str, emoji: str | None = None) -> Category:
        category_name = self.normalize_category_name(name)
        category = await self._get_or_create_category(category_name)
        if emoji:
            category.emoji = str(emoji).strip()
        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def create_product(
        self,
        title: str,
        description: str | None,
        price: str | int | float | Decimal,
        category_name: str,
        sizes: str | list[str] | None = None,
        images: list[str] | None = None,
    ) -> Product:
        validated_title = self.validate_title(title)
        normalized_description = self.normalize_description(description)
        amount = self.parse_price(price)
        normalized_category_name = self.normalize_category_name(category_name)
        normalized_sizes = self.parse_sizes(sizes)
        normalized_images = self._normalize_images(images)

        category = await self._get_or_create_category(normalized_category_name)

        product = Product(
            title=validated_title,
            description=normalized_description,
            price=amount,
            category_id=category.id,
            sizes=normalized_sizes,
            images=normalized_images,
            is_active=True,
        )
        self.session.add(product)

        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ValidationError("Не удалось создать товар.") from exc

        return await self.get_product(product.id, include_inactive=True)

    async def update_product(self, product_id: int, **fields) -> Product:
        product = await self.get_product(product_id, include_inactive=True)

        if "title" in fields and fields["title"] is not None:
            product.title = self.validate_title(fields["title"])
        if "description" in fields:
            product.description = self.normalize_description(fields["description"])
        if "price" in fields and fields["price"] is not None:
            product.price = self.parse_price(fields["price"])
        if "category_name" in fields and fields["category_name"] is not None:
            category = await self._get_or_create_category(self.normalize_category_name(fields["category_name"]))
            product.category_id = category.id
        if "sizes" in fields:
            product.sizes = self.parse_sizes(fields["sizes"])
        if "images" in fields:
            product.images = self._normalize_images(fields["images"])
        if "is_active" in fields and fields["is_active"] is not None:
            product.is_active = bool(fields["is_active"])

        await self.session.commit()
        return await self.get_product(product.id, include_inactive=True)

    async def get_product(self, product_id: int, include_inactive: bool = False) -> Product:
        stmt = select(Product).options(selectinload(Product.category)).where(Product.id == product_id)
        if not include_inactive:
            stmt = stmt.where(Product.is_active.is_(True))

        result = await self.session.execute(stmt)
        product = result.scalar_one_or_none()
        if product is None:
            raise NotFoundError("товар", product_id)
        return product

    async def list_admin_products(self, limit: int = 30) -> list[Product]:
        result = await self.session.execute(
            select(Product)
            .options(selectinload(Product.category))
            .order_by(Product.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_product(self, product_id: int) -> Product:
        product = await self.get_product(product_id, include_inactive=True)
        product.is_active = False
        await self.session.commit()
        return product

    async def get_pending_broadcast_products(self, limit: int = 1) -> list[Product]:
        result = await self.session.execute(
            select(Product)
            .options(selectinload(Product.category))
            .where(
                Product.is_active.is_(True),
                Product.broadcasted_at.is_(None),
            )
            .order_by(Product.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_broadcasted(self, product_id: int) -> None:
        product = await self.get_product(product_id, include_inactive=True)
        product.broadcasted_at = utcnow()
        await self.session.commit()