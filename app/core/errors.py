"""Domain errors. Services raise these; main.py maps them to the error format."""


class AppError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, *, status_code: int | None = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class NotFoundError(AppError):
    status_code = 404


class ProductNotFound(NotFoundError):
    code = "PRODUCT_NOT_FOUND"

    def __init__(self, product_id: int):
        super().__init__(f"Product {product_id} not found")


class CustomerNotFound(NotFoundError):
    code = "CUSTOMER_NOT_FOUND"

    def __init__(self, customer_id: int):
        super().__init__(f"Customer {customer_id} not found")


class OrderNotFound(NotFoundError):
    code = "ORDER_NOT_FOUND"

    def __init__(self, order_id: int):
        super().__init__(f"Order {order_id} not found")


class ConflictError(AppError):
    status_code = 409


class EmailAlreadyExists(ConflictError):
    code = "EMAIL_ALREADY_EXISTS"

    def __init__(self, email: str):
        super().__init__(f"Email {email} already exists")


class InsufficientStock(ConflictError):
    code = "INSUFFICIENT_STOCK"

    def __init__(self, product_id: int, available: int):
        super().__init__(f"Product {product_id} has only {available} in stock")


class InvalidStatusTransition(ConflictError):
    code = "INVALID_STATUS_TRANSITION"

    def __init__(self, current: str, new: str):
        super().__init__(f"Cannot change order status from {current} to {new}")


class ProductInUse(ConflictError):
    code = "PRODUCT_IN_USE"

    def __init__(self, product_id: int):
        super().__init__(f"Product {product_id} is referenced by orders")
