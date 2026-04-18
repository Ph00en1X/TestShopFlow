from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.exceptions import AccessDeniedError, NotFoundError
from bot.models.base import utcnow
from bot.models.user import User, UserRole
from config import Settings


class UserService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def get_or_create(
        self,
        telegram_id: int,
        full_name: str,
        username: str | None,
    ) -> tuple[User, bool]:
        now = utcnow()
        role = UserRole.admin if telegram_id in self.settings.ADMIN_IDS else UserRole.user
        created = False
        changed = False

        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=telegram_id,
                full_name=full_name.strip() or str(telegram_id),
                username=username,
                role=role,
                is_active=True,
                last_seen_at=now,
            )
            self.session.add(user)
            created = True
            changed = True
        else:
            if user.full_name != full_name:
                user.full_name = full_name
                changed = True
            if user.username != username:
                user.username = username
                changed = True
            if user.role != role:
                user.role = role
                changed = True
            if not user.is_active:
                user.is_active = True
                changed = True
            if user.last_seen_at is None or now - user.last_seen_at >= timedelta(minutes=5):
                user.last_seen_at = now
                changed = True

        if changed:
            try:
                await self.session.commit()
            except IntegrityError:
                await self.session.rollback()
                result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
                user = result.scalar_one()
                return user, False
            await self.session.refresh(user)

        return user, created

    async def get_profile(self, user_id: int) -> User:
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise NotFoundError("пользователь", user_id)
        return user

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    def ensure_admin(self, db_user: User) -> None:
        if db_user.role != UserRole.admin:
            raise AccessDeniedError()

    async def get_broadcast_recipients(self) -> list[int]:
        result = await self.session.execute(
            select(User.telegram_id).where(
                User.is_active.is_(True),
                User.receive_broadcasts.is_(True),
            )
        )
        return [int(item) for item in result.scalars().all()]