from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.common.presenters import render_catalog, render_product
from bot.core.container import AppServices
from bot.keyboards.user import MENU_CATALOG, products_kb
from bot.utils.formatters import escape_html
from bot.utils.telegram import edit_or_replace

router = Router()


@router.message(F.text == MENU_CATALOG)
async def menu_catalog(message: Message, state: FSMContext, services: AppServices) -> None:
    await state.clear()
    await render_catalog(message, services, edit=False)


@router.callback_query(F.data == "catalog:open")
async def callback_catalog_open(call: CallbackQuery, state: FSMContext, services: AppServices) -> None:
    if call.message is None:
        await call.answer()
        return
    await state.clear()
    await render_catalog(call.message, services, edit=True)
    await call.answer()


@router.callback_query(F.data.startswith("category:"))
async def callback_category_select(call: CallbackQuery, state: FSMContext, services: AppServices) -> None:
    if call.message is None:
        await call.answer()
        return

    await state.clear()
    category_id = int(call.data.split(":")[1])
    category = await services.catalog.get_category(category_id)
    products = await services.catalog.get_products_by_category(category_id)

    if not products:
        await call.answer("В этой категории пока нет товаров.", show_alert=True)
        return

    await edit_or_replace(
        call.message,
        f"📁 <b>{escape_html(category.name)}</b>\n\nВыберите товар:",
        reply_markup=products_kb(products),
    )
    await call.answer()


@router.callback_query(F.data.startswith("product:"))
async def callback_product_view(call: CallbackQuery, state: FSMContext, services: AppServices) -> None:
    if call.message is None:
        await call.answer()
        return

    await state.clear()
    product_id = int(call.data.split(":")[1])
    await render_product(call.message, services, product_id, replace_source=True)
    await call.answer()