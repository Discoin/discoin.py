import asyncio
import inspect
import logging

import aiohttp

from .classes import EventType, TransactionEvent
from .errors import BadRequest, InternalServerError, RateLimited, WebTimeoutError

POLL_INTERVAL_SECONDS = 2
FULL_BATCH_SIZE = 100
BACKOFF_START_SECONDS = 1
BACKOFF_CAP_SECONDS = 60
BACKOFF_FACTOR = 2
WEBHOOK_URL_SET_STATUS = 409
TRANSIENT_ERRORS = (InternalServerError, WebTimeoutError, asyncio.TimeoutError, aiohttp.ClientError)

logger = logging.getLogger(__name__)


class _FeedRefused(Exception):
    pass


class EventFeed():
    def __init__(self, fetch_event_objs, acknowledge_events):
        self._fetch_event_objs = fetch_event_objs
        self._acknowledge_events = acknowledge_events
        self._registrations = []
        self._has_listeners = None
        self._task = None
        self.error = None

    @property
    def running(self):
        return self._task is not None and not self._task.done()

    def add_listener(self, callback, event):
        if not inspect.iscoroutinefunction(callback):
            raise TypeError(f"{callback!r} is not a coroutine function")

        if event is not EventType.ALL and not isinstance(event, str):
            raise TypeError(f"{event!r} is not an event name or EventType.ALL")

        self._registrations.append((event, callback))
        self._signal_listeners()

    def remove_listener(self, callback, event):
        registration = (event, callback)
        if registration not in self._registrations:
            raise ValueError(f"{callback!r} is not registered for {event!r}")

        self._registrations.remove(registration)
        self._signal_listeners()

    async def start(self):
        if self.running:
            return

        self.error = None
        self._has_listeners = asyncio.Event()
        self._signal_listeners()
        self._task = asyncio.ensure_future(self._run())

    async def stop(self):
        if self._task is None:
            return

        self._task.cancel()
        await asyncio.wait([self._task])

    def _signal_listeners(self):
        if self._has_listeners is None:
            return

        if self._registrations:
            self._has_listeners.set()
        else:
            self._has_listeners.clear()

    async def _run(self):
        try:
            await self._deliver_forever()
        except _FeedRefused as refused:
            self._keep_first_error(refused.__cause__)
            logger.warning("%s The event feed stopped for this client.", refused.__cause__)
        # CancelledError is an Exception before Python 3.8, and a close is not a failure
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if error is not self.error:
                self._report_failure(error)

    def _report_failure(self, error):
        self._keep_first_error(error)
        logger.error("The event feed stopped for this client.", exc_info=error)

    def _keep_first_error(self, error):
        if self.error is None:
            self.error = error

    async def _deliver_forever(self):
        while True:
            await self._has_listeners.wait()
            event_objs = await self._request(self._fetch_event_objs)
            await self._deliver_batch(event_objs)

            if len(event_objs) < FULL_BATCH_SIZE:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _deliver_batch(self, event_objs):
        last_handled_id = None

        for event_obj in event_objs:
            try:
                event = TransactionEvent(event_obj)
                await self._dispatch(event)
            # CancelledError is an Exception before Python 3.8, and a close acknowledges nothing
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._report_failure(error)
                await self._acknowledge_up_to(last_handled_id)

                raise

            last_handled_id = event.id

        await self._acknowledge_up_to(last_handled_id)

    async def _dispatch(self, event):
        callbacks = [callback for key, callback in self._registrations if key in (event.event, EventType.ALL)]
        for callback in callbacks:
            await callback(event)

    async def _acknowledge_up_to(self, event_id):
        if event_id is None:
            return

        await self._request(lambda: self._acknowledge_events(event_id))

    async def _request(self, send):
        backoff = BACKOFF_START_SECONDS

        while True:
            try:
                return await send()
            except RateLimited as error:
                await _wait_out_rate_limit(error)
            except BadRequest as error:
                _raise_as_stop(error)
            except TRANSIENT_ERRORS as error:
                logger.warning("An event feed request failed, retrying in %s seconds: %r", backoff, error)
                await asyncio.sleep(backoff)
                backoff = min(backoff * BACKOFF_FACTOR, BACKOFF_CAP_SECONDS)


def _raise_as_stop(error):
    if error.status == WEBHOOK_URL_SET_STATUS:
        raise _FeedRefused() from error

    raise error


async def _wait_out_rate_limit(error):
    if error.retry_after is None:
        raise error

    logger.warning("The event feed is rate limited, retrying in %s seconds.", error.retry_after)
    await asyncio.sleep(error.retry_after)
