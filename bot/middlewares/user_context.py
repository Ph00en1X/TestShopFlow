from __future__ import annotations

from aiogram import BaseMiddleware

from bot.core.container import AppContainer


class UserContextMiddleware(BaseMiddleware):
    def __init__(self, container: AppContainer) -> None:
        self.container = container

    async def __call__(self, handler, event, data):
        from_user = getattr(event, "from_user", None)
        if from_user is None:
            return await handler(event, data)

        async with self.container.request_context() as services:
            db_user, _ = await services.users.get_or_create(
                telegram_id=from_user.id,
                full_name=from_user.full_name,
                username=from_user.username,
            )
            data["services"] = services
            data["db_user"] = db_user
            return await handler(event, data)