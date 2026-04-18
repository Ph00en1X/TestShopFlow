from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.common.presenters import render_admin_product, render_admin_products
from bot.core.container import AppServices
from bot.keyboards.admin import admin_main_kb, admin_product_detail_kb, cancel_admin_flow_kb
from bot.models.states import AdminProductFlow
from bot.models.user import User
from bot.utils.formatters import format_admin_product_text
from bot.utils.telegram import edit_or_replace

router = Router()


@router.callback_query(F.data == "admin:products")
async def callback_admin_products(
    call: CallbackQuery,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    if call.message is None:
        await call.answer()
        return

    await state.clear()
    await render_admin_products(call.message, db_user, services, edit=True)
    await call.answer()


@router.callback_query(F.data.startswith("admin:product:"))
async def callback_admin_product_detail(
    call: CallbackQuery,
    db_user: User,
    services: AppServices,
) -> None:
    if call.message is None:
        await call.answer()
        return

    product_id = int(call.data.split(":")[2])
    await render_admin_product(call.message, db_user, services, product_id, edit=True)
    await call.answer()


@router.callback_query(F.data == "admin:add_product")
async def callback_admin_add_product_start(
    call: CallbackQuery,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    if call.message is None:
        await call.answer()
        return

    services.users.ensure_admin(db_user)
    await state.clear()
    await state.set_state(AdminProductFlow.adding_title)
    await edit_or_replace(
        call.message,
        "Введите название товара:",
        reply_markup=cancel_admin_flow_kb(),
    )
    await call.answer()


@router.message(AdminProductFlow.adding_title)
async def admin_product_title(
    message: Message,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    services.users.ensure_admin(db_user)
    title = services.products.validate_title(message.text)
    await state.update_data(title=title)
    await state.set_state(AdminProductFlow.adding_description)
    await message.answer("Введите описание или напишите <b>пропустить</b>.", reply_markup=cancel_admin_flow_kb())


@router.message(AdminProductFlow.adding_description)
async def admin_product_description(
    message: Message,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    services.users.ensure_admin(db_user)
    description = services.products.normalize_description(message.text)
    await state.update_data(description=description)
    await state.set_state(AdminProductFlow.adding_price)
    await message.answer(
        "Введите цену, например <b>1990</b> или <b>1990.50</b>.",
        reply_markup=cancel_admin_flow_kb(),
    )


@router.message(AdminProductFlow.adding_price)
async def admin_product_price(
    message: Message,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    services.users.ensure_admin(db_user)
    price = services.products.parse_price(message.text)
    await state.update_data(price=str(price))
    await state.set_state(AdminProductFlow.adding_category)
    await message.answer("Введите название категории.", reply_markup=cancel_admin_flow_kb())


@router.message(AdminProductFlow.adding_category)
async def admin_product_category(
    message: Message,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    services.users.ensure_admin(db_user)
    category_name = services.products.normalize_category_name(message.text)
    await state.update_data(category_name=category_name)
    await state.set_state(AdminProductFlow.adding_sizes)
    await message.answer(
        "Введите размеры через запятую или напишите <b>пропустить</b>.",
        reply_markup=cancel_admin_flow_kb(),
    )


@router.message(AdminProductFlow.adding_sizes)
async def admin_product_sizes(
    message: Message,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    services.users.ensure_admin(db_user)
    sizes = services.products.parse_sizes(message.text)
    await state.update_data(sizes=sizes, images=[])
    await state.set_state(AdminProductFlow.adding_images)
    await message.answer(
        "Отправьте фото товара по одному или напишите <b>готово</b>.",
        reply_markup=cancel_admin_flow_kb(),
    )


@router.message(AdminProductFlow.adding_images, F.photo)
async def admin_product_images_photo(
    message: Message,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    services.users.ensure_admin(db_user)
    data = await state.get_data()
    images = list(data.get("images", []))
    images.append(message.photo[-1].file_id)
    await state.update_data(images=images)
    await message.answer(
        "Изображение добавлено. Отправьте ещё одно фото или напишите <b>готово</b>.",
        reply_markup=cancel_admin_flow_kb(),
    )


@router.message(AdminProductFlow.adding_images, F.text)
async def admin_product_images_done(
    message: Message,
    state: FSMContext,
    db_user: User,
    services: AppServices,
) -> None:
    services.users.ensure_admin(db_user)

    if not services.products.should_finish_image_collection(message.text):
        await message.answer(
            "Отправьте фото товара или напишите <b>готово</b>.",
            reply_markup=cancel_admin_flow_kb(),
        )
        return

    data = await state.get_data()
    product = await services.products.create_product(
        title=data["title"],
        description=data.get("description"),
        price=data["price"],
        category_name=data["category_name"],
        sizes=data.get("sizes"),
        images=data.get("images"),
    )
    await state.clear()
    await message.answer(
        format_admin_product_text(product, services.settings.TIMEZONE),
        reply_markup=admin_product_detail_kb(product),
    )


@router.callback_query(F.data.startswith("admin:delete_product:"))
async def callback_admin_delete_product(
    call: CallbackQuery,
    db_user: User,
    services: AppServices,
) -> None:
    if call.message is None:
        await call.answer()
        return

    services.users.ensure_admin(db_user)
    product_id = int(call.data.split(":")[2])
    await services.products.delete_product(product_id)
    await render_admin_product(call.message, db_user, services, product_id, edit=True)
    await call.answer("Товар деактивирован.")


@router.callback_query(F.data.startswith("admin:activate_product:"))
async def callback_admin_activate_product(
    call: CallbackQuery,
    db_user: User,
    services: AppServices,
) -> None:
    if call.message is None:
        await call.answer()
        return

    services.users.ensure_admin(db_user)
    product_id = int(call.data.split(":")[2])
    await services.products.update_product(product_id, is_active=True)
    await render_admin_product(call.message, db_user, services, product_id, edit=True)
    await call.answer("Товар активирован.")


@router.callback_query(F.data == "admin:cancel_flow")
async def callback_admin_cancel_flow(call: CallbackQuery, state: FSMContext) -> None:
    if call.message is not None:
        await edit_or_replace(call.message, "Операция отменена.", reply_markup=admin_main_kb())
    await state.clear()
    await call.answer()