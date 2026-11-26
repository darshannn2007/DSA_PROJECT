"""Custom application exceptions."""


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(404, "not_found", message)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(403, "forbidden", message)


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict"):
        super().__init__(409, "conflict", message)


class ValidationError(AppError):
    def __init__(self, message: str = "Validation error"):
        super().__init__(422, "validation_error", message)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Not authenticated"):
        super().__init__(401, "unauthorized", message)
