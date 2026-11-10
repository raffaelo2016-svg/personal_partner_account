from fastapi import HTTPException


class AppException(HTTPException):
    def __init__(self, status_code: int, detail: str, code: str):
        super().__init__(status_code=status_code, detail=detail, headers={"code": code})
        self.code = code


class BadRequest(AppException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=400, detail=detail, code="BAD_REQUEST")


class InvalidStatusTransition(AppException):
    def __init__(self, detail: str = "Invalid status transition"):
        super().__init__(status_code=400, detail=detail, code="INVALID_STATUS_TRANSITION")


class ValidationError(AppException):
    def __init__(self, detail: str = "Validation error"):
        super().__init__(status_code=400, detail=detail, code="VALIDATION_ERROR")


class TokenExpired(AppException):
    def __init__(self):
        super().__init__(status_code=401, detail="Token expired", code="TOKEN_EXPIRED")


class InvalidCredentials(AppException):
    def __init__(self):
        super().__init__(status_code=401, detail="Invalid credentials", code="INVALID_CREDENTIALS")


class PartnerPending(AppException):
    def __init__(self):
        super().__init__(
            status_code=403,
            detail="Ваш аккаунт находится на проверке. Пожалуйста, дождитесь подтверждения администратором.",
            code="PARTNER_PENDING",
        )


class PartnerBlocked(AppException):
    def __init__(self):
        super().__init__(
            status_code=403,
            detail="Ваш аккаунт заблокирован. Обратитесь к администратору для получения информации.",
            code="PARTNER_BLOCKED",
        )


class Forbidden(AppException):
    def __init__(self, detail: str = "Forbidden"):
        super().__init__(status_code=403, detail=detail, code="FORBIDDEN")


class NotFound(AppException):
    def __init__(self, detail: str = "Not found"):
        super().__init__(status_code=404, detail=detail, code="NOT_FOUND")


class DuplicateEmail(AppException):
    def __init__(self):
        super().__init__(status_code=409, detail="Email already registered", code="DUPLICATE_EMAIL")


class Conflict(AppException):
    def __init__(self, detail: str = "Conflict", code: str = "CONFLICT"):
        super().__init__(status_code=409, detail=detail, code=code)


class FileTooLarge(AppException):
    def __init__(self):
        super().__init__(status_code=413, detail="File too large", code="FILE_TOO_LARGE")


class UnsupportedFileType(AppException):
    def __init__(self):
        super().__init__(status_code=415, detail="Unsupported file type", code="UNSUPPORTED_FILE_TYPE")


class RateLimited(AppException):
    def __init__(self):
        super().__init__(status_code=429, detail="Too many requests", code="RATE_LIMITED")
