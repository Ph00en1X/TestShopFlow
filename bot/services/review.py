from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.core.exceptions import DuplicateReviewError, NotFoundError, ValidationError
from bot.models.catalog import Product
from bot.models.review import Review


class ReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def validate_text(self, value: str | None) -> str:
        text = str(value or "").strip()
        if len(text) < 5:
            raise ValidationError("Текст отзыва должен содержать минимум 5 символов.")
        if len(text) > 1000:
            raise ValidationError("Текст отзыва слишком длинный.")
        return text

    def validate_rating(self, value: int | str) -> int:
        rating = int(value)
        if rating < 1 or rating > 5:
            raise ValidationError("Оценка должна быть от 1 до 5.")
        return rating

    async def create_review(self, user_id: int, product_id: int, text: str, rating: int) -> Review:
        validated_text = self.validate_text(text)
        validated_rating = self.validate_rating(rating)

        product_result = await self.session.execute(select(Product.id).where(Product.id == product_id))
        if product_result.scalar_one_or_none() is None:
            raise NotFoundError("товар", product_id)

        duplicate_result = await self.session.execute(
            select(Review.id).where(
                Review.user_id == user_id,
                Review.product_id == product_id,
            )
        )
        if duplicate_result.scalar_one_or_none() is not None:
            raise DuplicateReviewError("Вы уже оставляли отзыв на этот товар.")

        review = Review(
            user_id=user_id,
            product_id=product_id,
            text=validated_text,
            rating=validated_rating,
        )
        self.session.add(review)

        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicateReviewError("Вы уже оставляли отзыв на этот товар.") from exc

        await self.session.refresh(review)
        return review

    async def get_product_rating_summary(self, product_id: int) -> tuple[float | None, int]:
        result = await self.session.execute(
            select(func.avg(Review.rating), func.count(Review.id)).where(Review.product_id == product_id)
        )
        avg_rating, count = result.one()
        return (float(avg_rating) if avg_rating is not None else None, int(count or 0))

    async def get_product_reviews(self, product_id: int, limit: int = 10) -> list[Review]:
        result = await self.session.execute(
            select(Review)
            .options(selectinload(Review.user))
            .where(Review.product_id == product_id)
            .order_by(Review.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_reviews(self, limit: int = 10) -> list[Review]:
        result = await self.session.execute(
            select(Review)
            .options(
                selectinload(Review.user),
                selectinload(Review.product),
            )
            .order_by(Review.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())