import asyncio
import logging

import aiohttp

from .errors import InternalServerError, RateLimited, WebTimeoutError

BACKOFF_START_SECONDS = 1
BACKOFF_FACTOR = 2
BACKOFF_CAP_SECONDS = 128

# Errors after which the API may or may not have handled the request
RETRIED_ERRORS = (InternalServerError, RateLimited, WebTimeoutError, asyncio.TimeoutError, aiohttp.ClientError)

# aiohttp raises this for a timeout while connecting since 3.10. Before, it raised a ServerTimeoutError with this message,
# while a timeout after the request was sent is a ServerTimeoutError with another message or a bare asyncio.TimeoutError
_CONNECT_TIMEOUT_ERROR = getattr(aiohttp, "ConnectionTimeoutError", None)
_CONNECT_TIMEOUT_MESSAGE_PREFIX = "Connection timeout to host"

logger = logging.getLogger(__name__)


def backoff_delays():
    """
    Yield the waits between attempts: 1, 2, 4, ... seconds, doubling up to `BACKOFF_CAP_SECONDS` and staying there
    """

    delay = BACKOFF_START_SECONDS

    while True:
        yield delay
        delay = min(delay * BACKOFF_FACTOR, BACKOFF_CAP_SECONDS)


def _count_retries_to_cap():
    retries = 0

    for delay in backoff_delays():
        retries += 1

        if delay >= BACKOFF_CAP_SECONDS:
            return retries


# The retry after the first wait of `BACKOFF_CAP_SECONDS` is the last: 8 retries, after waits of 1, 2, 4, ... 128 seconds
DEFAULT_MAX_RETRIES = _count_retries_to_cap()


def is_retryable(error):
    """
    If `error` is one after which a request is retried: a 5**, a 429, a timeout or a network error
    """

    return isinstance(error, RETRIED_ERRORS)


def never_reached_api(error):
    """
    If `error` is one raised before the request was sent, so the API cannot have handled it: a failure or a timeout while connecting
    """

    if isinstance(error, WebTimeoutError):
        error = error.__cause__

    if isinstance(error, aiohttp.ClientConnectorError):
        return True

    if _CONNECT_TIMEOUT_ERROR is not None:
        return isinstance(error, _CONNECT_TIMEOUT_ERROR)

    return isinstance(error, aiohttp.ServerTimeoutError) and str(error).startswith(_CONNECT_TIMEOUT_MESSAGE_PREFIX)


async def with_backoff(send, max_retries: int = DEFAULT_MAX_RETRIES, should_retry=is_retryable):
    """
    Await `send()` until it succeeds, retrying the errors `should_retry` accepts with exponential backoff.
    A 429 with a `Retry-After` header waits the seconds the header names instead of the backoff.
    Any other error is raised at once.

    *`send` = a function that takes no argument and returns a new awaitable for each attempt
    `max_retries` = the most retries after the first attempt, then the last error is raised. ``None`` retries until it succeeds
    `should_retry` = a function that gets the error of a failed attempt and returns if it is retried. Default is `is_retryable`
    """

    delays = backoff_delays()
    retries = 0

    while True:
        try:
            return await send()
        # CancelledError is an Exception before Python 3.8
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if not should_retry(error) or (max_retries is not None and retries >= max_retries):
                raise

            retries += 1
            wait = _wait_for(error, delays)
            logger.warning("A Discoin API request failed, retrying in %s seconds: %r", wait, error)
            await asyncio.sleep(wait)


def _wait_for(error, delays):
    if isinstance(error, RateLimited) and error.retry_after is not None:
        return error.retry_after

    return next(delays)
