from __future__ import annotations

from contextlib import suppress

from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.common.presenters import render_product
from bot.core.container import AppServices
from bot.keyboards.user import main_menu_kb
from bot.models.user import User
from bot.utils.formatters import format_help_text, format_welcome_text

router = Router()


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    command: CommandObject,
    services: AppServices,
    db_user: User,
) -> None:
    await state.clear()
    await message.answer(
        format_welcome_text(services.settings.SHOP_NAME, db_user.full_name),
        reply_markup=main_menu_kb(db_user.role),
    )

    if command.args and command.args.startswith("product_"):
        with suppress(Exception):
            product_id = int(command.args.split("_", 1)[1])
            await render_product(message, services, product_id, replace_source=False)


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext, db_user: User) -> None:
    await state.clear()
    await message.answer(
        format_help_text(),
        reply_markup=main_menu_kb(db_user.role),
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, db_user: User) -> None:
    await state.clear()
    await message.answer(
        "Текущее действие отменено.",
        reply_markup=main_menu_kb(db_user.role),
    )