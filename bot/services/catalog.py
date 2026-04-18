from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.core.exceptions import NotFoundError
from bot.models.catalog import Category, Product


class CatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_categories(self) -> list[Category]:
        result = await self.session.execute(
            select(Category)
            .join(Product, Product.category_id == Category.id)
            .where(
                Category.is_active.is_(True),
                Product.is_active.is_(True),
            )
            .distinct()
            .order_by(Category.name.asc())
        )
        return list(result.scalars().all())

    async def get_category(self, category_id: int) -> Category:
        result = await self.session.execute(
            select(Category).where(
                Category.id == category_id,
                Category.is_active.is_(True),
            )
        )
        category = result.scalar_one_or_none()
        if category is None:
            raise NotFoundError("категория", category_id)
        return category

    async def get_products_by_category(self, category_id: int) -> list[Product]:
        result = await self.session.execute(
            select(Product)
            .where(
                Product.category_id == category_id,
                Product.is_active.is_(True),
            )
            .order_by(Product.title.asc())
        )
        return list(result.scalars().all())

    async def get_product(self, product_id: int) -> Product:
        result = await self.session.execute(
            select(Product)
            .options(selectinload(Product.category))
            .where(
                Product.id == product_id,
                Product.is_active.is_(True),
            )
        )
        product = result.scalar_one_or_none()
        if product is None:
            raise NotFoundError("товар", product_id)
        return product

    async def search_products(self, query: str) -> list[Product]:
        text = str(query or "").strip()
        if not text:
            return []

        result = await self.session.execute(
            select(Product)
            .where(
                Product.is_active.is_(True),
                or_(
                    Product.title.ilike(f"%{text}%"),
                    Product.description.ilike(f"%{text}%"),
                ),
            )
            .order_by(Product.title.asc())
            .limit(20)
        )
        return list(result.scalars().all())