from aiogram.fsm.state import State, StatesGroup


class CheckoutFlow(StatesGroup):
    waiting_name = State()
    waiting_contact = State()
    waiting_comment = State()


class AdminProductFlow(StatesGroup):
    adding_title = State()
    adding_description = State()
    adding_price = State()
    adding_category = State()
    adding_sizes = State()
    adding_images = State()


class ReviewFlow(StatesGroup):
    waiting_text = State()
    waiting_rating = State()