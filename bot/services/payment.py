from __future__ import annotations

from bot.models.order import Order
from config import Settings


class PaymentService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate_instructions(self, order: Order) -> str:
        return (
            f"💳 <b>Инструкция по оплате</b>\n\n"
            f"Заказ: <b>#{order.id}</b>\n"
            f"Сумма: <b>{order.total_price:.2f}</b>\n\n"
            f"Переведите деньги на карту:\n"
            f"<code>{self.settings.PAYMENT_CARD}</code>\n"
            f"Получатель: <b>{self.settings.PAYMENT_HOLDER}</b>\n\n"
            f"В комментарии к переводу укажите <b>заказ #{order.id}</b>.\n"
            f"После оплаты дождитесь ручного подтверждения администратора."
        )