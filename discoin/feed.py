import asyncio
import inspect
import logging

from .classes import EventStatus, TransactionEvent, TransactionStatus
from .errors import BadRequest, RateLimited
from .retry import RETRIED_ERRORS

HANDLER_PREFIX = "on_"
UNNAMED_EVENT_HANDLER_NAME = "on_event"
ERROR_HANDLER_NAME = "on_error"
POLL_INTERVAL_SECONDS = 2
FULL_BATCH_SIZE = 100
WEBHOOK_URL_SET_STATUS = 409
NO_LONGER_PENDING_STATUS = 400
TRANSACTION_NOT_FOUND_STATUS = 404
NOTHING_LEFT_TO_MARK_STATUSES = (NO_LONGER_PENDING_STATUS, TRANSACTION_NOT_FOUND_STATUS)
MARK_TRIES = 3
MARK_RETRY_WAIT_SECONDS = 1
MARKED_STATUSES = {
    EventStatus.COMPLETED: TransactionStatus.COMPLETED,
    EventStatus.REFUNDED: TransactionStatus.REFUNDED,
}

logger = logging.getLogger(__name__)

# asyncio.current_task is new in Python 3.7, and Task.current_task is gone since Python 3.9
_current_task = getattr(asyncio, "current_task", None) or asyncio.Task.current_task


class _FeedRefused(Exception):
    pass


class EventFeed():
    def __init__(self, client):
        self._client = client
        self._task = None
        self._stopped_from_inside = False
        self.error = None

    @property
    def running(self):
        return self._task is not None and not self._task.done()

    async def start(self):
        if self.running:
            return

        handler_names = self._find_handler_names()
        self._require_coroutine_functions(handler_names + [ERROR_HANDLER_NAME])
        self.error = None
        self._stopped_from_inside = False

        if handler_names:
            self._task = asyncio.ensure_future(self._run())

    async def stop(self):
        if self._task is None:
            return

        if self._task is _current_task():
            self._stopped_from_inside = True

            return

        self._task.cancel()
        await asyncio.wait([self._task])

    def _end_if_stopped_from_inside(self):
        # The task ends as a stop from outside ends it, since every guard of the feed lets a CancelledError through
        if self._stopped_from_inside:
            raise asyncio.CancelledError()

    def _find_handler_names(self):
        return [name for name in dir(self._client) if name.startswith(HANDLER_PREFIX) and name != ERROR_HANDLER_NAME]

    def _require_coroutine_functions(self, handler_names):
        for handler_name in handler_names:
            if not inspect.iscoroutinefunction(getattr(self._client, handler_name)):
                raise TypeError(f"{handler_name} of {type(self._client).__name__} is not a coroutine function")

    async def _run(self):
        try:
            await self._deliver_forever()
        except _FeedRefused as refused:
            self.error = refused.__cause__
            logger.warning("%s The event feed stopped for this client.", refused.__cause__)
        # CancelledError is an Exception before Python 3.8, and a close is not a failure
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.error = error
            logger.error("The event feed stopped for this client.", exc_info=error)

    async def _deliver_forever(self):
        while True:
            event_objs = await self._claim()
            for event_obj in event_objs:
                await self._deliver(event_obj)

            if len(event_objs) < FULL_BATCH_SIZE:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _claim(self):
        try:
            return await self._client._claim_event_objs()
        except BadRequest as error:
            if error.status == WEBHOOK_URL_SET_STATUS:
                raise _FeedRefused() from error

            raise

    async def _deliver(self, event_obj):
        event_id = event_obj['id']
        event = await self._parse(event_obj)
        handled = event is not None and await self._handle(event)

        await self._report(event_id, handled, event)

    async def _parse(self, event_obj):
        try:
            return TransactionEvent(event_obj)
        except Exception as error:
            await self._call_on_error(error, None)

            return None

    async def _handle(self, event):
        try:
            return await self._settle(event)
        # CancelledError is an Exception before Python 3.8, and a close reports nothing
        except asyncio.CancelledError:
            raise
        except Exception as error:
            await self._call_on_error(error, event)

            return False

    async def _settle(self, event):
        handler_name = self._find_handler_name(event)
        if handler_name is None:
            return True

        status = await getattr(self._client, handler_name)(event)
        self._end_if_stopped_from_inside()

        if not isinstance(status, EventStatus):
            raise TypeError(f"{handler_name} of {type(self._client).__name__} returned {status!r}, which is not a discoin.EventStatus")

        if status in MARKED_STATUSES:
            await self._mark(event, MARKED_STATUSES[status])

        return status is not EventStatus.UNHANDLED

    def _find_handler_name(self, event):
        named_handler_name = HANDLER_PREFIX + event.event.replace(".", "_")
        if named_handler_name != ERROR_HANDLER_NAME and hasattr(self._client, named_handler_name):
            return named_handler_name

        if hasattr(self._client, UNNAMED_EVENT_HANDLER_NAME):
            return UNNAMED_EVENT_HANDLER_NAME

        return None

    async def _mark(self, event, transaction_status):
        try:
            await self._mark_with_retries(event.transaction.id, transaction_status)
        except BadRequest as error:
            if error.status not in NOTHING_LEFT_TO_MARK_STATUSES:
                raise

            await self._call_on_error(error, event)

    async def _mark_with_retries(self, transaction_id, transaction_status):
        for _ in range(MARK_TRIES - 1):
            try:
                await self._client._mark_once(transaction_id, transaction_status)

                return
            except RETRIED_ERRORS as error:
                wait = _seconds_before_mark_retry(error)
                logger.warning("Marking transaction %s failed, retrying in %s seconds: %r", transaction_id, wait, error)
                await asyncio.sleep(wait)

        await self._client._mark_once(transaction_id, transaction_status)

    async def _report(self, event_id, handled, event):
        try:
            await self._client.report_event(event_id, handled)
        # A 429 that outlasted the client's retries stops the feed like a 5**, unlike the other 4**
        except RateLimited:
            raise
        except BadRequest as error:
            await self._call_on_error(error, event)

    async def _call_on_error(self, error, event):
        try:
            await self._client.on_error(error, event)
        # CancelledError is an Exception before Python 3.8
        except asyncio.CancelledError:
            raise
        except Exception as on_error_failure:
            logger.error("on_error raised while it handled %r.", error, exc_info=on_error_failure)

        self._end_if_stopped_from_inside()


def _seconds_before_mark_retry(error):
    if not isinstance(error, RateLimited):
        return MARK_RETRY_WAIT_SECONDS

    if error.retry_after is None:
        raise error

    return error.retry_after
