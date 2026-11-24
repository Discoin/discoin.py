from .config import DOMAIN
from .errors import InternalServerError, BadRequest, RateLimited, InvalidMethod, WebTimeoutError
from aiohttp import ClientSession
from asyncio import TimeoutError

TOO_MANY_REQUESTS = 429
RETRY_AFTER_HEADER = "Retry-After"

async def api_request(session: ClientSession, method: str, url_path: str, headers: dict=None, json: dict=None):
    """
    *`session` = the aiohttp session
    *`method` = `GET`, `POST`, `PUT`, or `PATCH`
    *`url_path` = The api endpoint
    `headers` = headers for the api request
    `json` = json for the api request
    """

    url = DOMAIN + url_path

    try:
        if method.upper() == "GET":
            api_response = await session.get(url, headers=headers, json=json)
        elif method.upper() == "POST":
            api_response = await session.post(url, headers=headers, json=json)
        elif method.upper() == "PUT":
            api_response = await session.put(url, headers=headers, json=json)
        elif method.upper() == "PATCH":
            api_response = await session.patch(url, headers=headers, json=json)
        else:
            raise InvalidMethod("Invalid method provided. Must be `GET`, `POST`, `PUT`, or `PATCH`")
    except TimeoutError:
        raise WebTimeoutError("Your request has timed out, most likely due to the discoin API being down.")

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
