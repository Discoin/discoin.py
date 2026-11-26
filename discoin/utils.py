from .config import DOMAIN
from .errors import InternalServerError, BadRequest, RateLimited, InvalidMethod, WebTimeoutError
from .retry import DEFAULT_MAX_RETRIES, with_backoff
from aiohttp import ClientSession
from asyncio import TimeoutError

TOO_MANY_REQUESTS = 429
RETRY_AFTER_HEADER = "Retry-After"

async def api_request(session: ClientSession, method: str, url_path: str, headers: dict=None, json: dict=None, max_retries: int=DEFAULT_MAX_RETRIES):
    """
    Send a request to the discoin API, retrying a 5**, a 429, a timeout or a network error with exponential backoff (see `retry.with_backoff`).
    The response body is already read when it returns.

    *`session` = the aiohttp session
    *`method` = `GET`, `POST`, `PUT`, or `PATCH`
    *`url_path` = The api endpoint
    `headers` = headers for the api request
    `json` = json for the api request
    `max_retries` = the most retries after the first attempt, then the last error is raised. Default is 8, the retry after the first 128 second wait. ``None`` retries until it succeeds
    """

    return await with_backoff(lambda: send_request(session, method, url_path, headers=headers, json=json), max_retries)

async def send_request(session: ClientSession, method: str, url_path: str, headers: dict=None, json: dict=None):
    """
    Send one request to the discoin API, without retrying. The arguments are those of `api_request`
    """

    if method.upper() not in ("GET", "POST", "PUT", "PATCH"):
        raise InvalidMethod("Invalid method provided. Must be `GET`, `POST`, `PUT`, or `PATCH`")

    url = DOMAIN + url_path

    try:
        api_response = await session.request(method.upper(), url, headers=headers, json=json)
        # Reading the body here releases the connection, and a failure while reading it is retried like one while sending
        await api_response.read()
    except TimeoutError as error:
        # The cause tells `retry.never_reached_api` a timeout while connecting from one after the request was sent
        raise WebTimeoutError("Your request has timed out, most likely due to the discoin API being down.") from error

    if api_response.status >= 500:
        raise InternalServerError(*await _read_error_body(api_response))
    elif api_response.status == TOO_MANY_REQUESTS:
        raise RateLimited(*await _read_error_body(api_response), _read_retry_after(api_response))
    elif api_response.status >= 400:
        raise BadRequest(*await _read_error_body(api_response))

    return api_response

async def _read_error_body(api_response):
    if api_response.content_type != "application/json":
        return api_response.status, None, None

    error_body = await api_response.json()

    return error_body['status'], error_body['message'], error_body['field']

def _read_retry_after(api_response):
    retry_after = api_response.headers.get(RETRY_AFTER_HEADER)
    if retry_after is None or not retry_after.isdecimal():
        return None

    return int(retry_after)
