class DiscoinError(Exception):
    """
    This is just a base incase we need to add anything here later
    """
    pass

class InternalServerError(DiscoinError):
    """
    This error is raised when the API returns a status code of 5**

    :param status: (``int``) The status code from the API's error body, or the HTTP status if the response carried no Discoin error body
    :param message: (``str``) The message from the API's error body. ``None`` if the response carried no Discoin error body
    :param field: (``str``) The field the error is about. ``None`` if the API did not name one, or if the response carried no Discoin error body
    """

    def __init__(self, status: int, message: str, field: str):
        super().__init__(_describe_error(status, message, field))
        self.status = status
        self.message = message
        self.field = field

class BadRequest(DiscoinError):
    """
    This error is raised when the API returns a status code of 4**

    :param status: (``int``) The status code from the API's error body, or the HTTP status if the response carried no Discoin error body
    :param message: (``str``) The message from the API's error body. ``None`` if the response carried no Discoin error body
    :param field: (``str``) The field the error is about. ``None`` if the API did not name one, or if the response carried no Discoin error body
    """

    def __init__(self, status: int, message: str, field: str):
        super().__init__(_describe_error(status, message, field))
        self.status = status
        self.message = message
        self.field = field

class RateLimited(BadRequest):
    """
    This error is raised when the API returns a status code of 429. The API allows 300 requests a minute per token

    :param status: (``int``) The status code from the API's error body, or the HTTP status if the response carried no Discoin error body
    :param message: (``str``) The message from the API's error body. ``None`` if the response carried no Discoin error body
    :param field: (``str``) The field the error is about. ``None`` if the API did not name one, or if the response carried no Discoin error body
    :param retry_after: (``int``) The seconds to wait before the next request, from the `Retry-After` header. ``None`` if the response carried no `Retry-After` header in whole seconds
    """

    def __init__(self, status: int, message: str, field: str, retry_after: int):
        super().__init__(status, message, field)
        self.retry_after = retry_after

class InvalidMethod(DiscoinError):
    """
    This error is raised when the user tries to use an incorrect method with `utils.api_request`
    """
    pass

class WebTimeoutError(DiscoinError):
    """
    This error is raised when `utils.api_request` times out
    """
    pass

def _describe_error(status: int, message: str, field: str):
    description = f"The Discoin API returned the status code {status}"

    if message is not None:
        description += f": {message}"

    if field is not None:
        description += f" (field: {field})"

    return description