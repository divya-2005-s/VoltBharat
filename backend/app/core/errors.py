class ApiError(Exception):
    """An error that is safe to show to API clients."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class DatabaseUnavailable(ApiError):
    def __init__(self, message: str = "The analytics database is unavailable. No figures can be served until it is reachable."):
        super().__init__(503, "database_unavailable", message)
