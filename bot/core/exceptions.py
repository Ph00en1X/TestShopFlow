from __future__ import annotations


class ShopFlowError(Exception):
    pass


class ValidationError(ShopFlowError):
    pass


class NotFoundError(ShopFlowError):
    def __init__(self, entity: str, entity_id: int | str | None = None) -> None:
        label = f"{entity}{f' #{entity_id}' if entity_id is not None else ''}"
        super().__init__(f"Не найдено: {label}.")
        self.entity = entity
        self.entity_id = entity_id


class AccessDeniedError(ShopFlowError):
    def __init__(self, message: str = "Доступ запрещён.") -> None:
        super().__init__(message)


class CartLimitExceededError(ShopFlowError):
    pass


class ProductUnavailableError(ShopFlowError):
    pass


class EmptyCartError(ShopFlowError):
    pass


class OrderStateError(ShopFlowError):
    pass


class DuplicateReviewError(ShopFlowError):
    pass