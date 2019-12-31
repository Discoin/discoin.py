from .config import DOMAIN
from .errors import InternalServerError, BadRequest, InvalidMethod, WebTimeoutError
from aiohttp import ClientSession
from asyncio import TimeoutError

async def api_request(session: ClientSession, method: str, url_path: str, headers: dict=None, json: dict=None):
    '''
    *`session` = the aiohttp session
    *`method` = `GET`, `POST`, or `PATCH`
    *`url_path` = The api endpoint
    `headers` = headers for the api request
    `json` = json for the api request
    '''

    url = DOMAIN + url_path

    try:
        if method.upper() == "GET":
            api_response = await session.get(url, headers=headers, json=json)
        elif method.upper() == "POST":
            api_response = await session.post(url, headers=headers, json=json)
        elif method.upper() == "PATCH":
            api_response = await session.patch(url, headers=headers, json=json)
        else:
            raise InvalidMethod("Invalid method provided. Must be `GET`, `POST`, or `PATCH`")
    except TimeoutError:
        raise WebTimeoutError("Your request has timed out, most likely due to the discoin API being down.")
        
    if api_response.status >= 500: 
        raise InternalServerError(f"The Discoin API returned the status code {api_response.status}")
    elif api_response.status >= 400: 
        raise BadRequest(f"The Discoin API returned the status code {api_response.status}")

    return api_response