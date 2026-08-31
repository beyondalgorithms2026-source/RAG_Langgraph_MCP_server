from __future__ import annotations


class BackendError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, payload: object | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload


class ValidationError(Exception):
    pass

