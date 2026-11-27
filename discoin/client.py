import aiohttp
import logging
from urllib.parse import quote, urlencode

from .classes import Transaction, Currency, TransactionStatus, TransactionEvent
from .feed import EventFeed
from .retry import DEFAULT_MAX_RETRIES, is_retryable, never_reached_api, with_backoff
from .utils import send_request

logger = logging.getLogger(__name__)


class Client():
    """
    Main used class for discoin
    """

    def __init__(self, token: str, me: str = None, max_retries: int = DEFAULT_MAX_RETRIES):
        """
        Init client.

        Every request is retried on a 5**, a 429, a timeout or a network error, with a wait that starts at 1 second and doubles up to 128 seconds.
        A 429 with a `Retry-After` header waits the seconds the header names instead. Other 4** are raised at once.
        `create_transaction` is the exception: it only retries when the connection to the API could not be made, so it never creates a transaction twice.

        :param token: (``str``) Your api token for discoin 
        :param me: (``str``) (Optional) Your 3 letter currency code, the default `code_from` of `create_transaction` and `fetch_quote`. Leave it out if your bot runs several currencies
        :param max_retries: (``int``) (Optional) The most retries of a request, after which its last error is raised. Default is 8, so a request gives up after the retry that follows the first 128 second wait. ``None`` retries until the request succeeds. It also applies to the claims and reports of the event feed, and not to the marks the feed sends
        """

        # Needed vars
        self._headers = {"Authorization": f"Bearer {token}"}
        self._me = me
        self._max_retries = max_retries
        self._session = None
        self._feed = EventFeed(self)

    @property
    def events_running(self):
        """
        (``bool``) If the event feed started by `start` is running. It stays ``False`` after `start` on a client that defines no handler method
        """

        return self._feed.running

    @property
    def events_error(self):
        """
        (``Exception``) The error that stopped the event feed. ``None`` if the feed was never stopped by an error. `start` clears it
        """

        return self._feed.error

    async def start(self):
        """
        Start the event feed. It returns at once, and the feed runs as a background task in the running loop.
        Calling it while the feed is running does nothing. After a stop it starts the feed again and clears `events_error`.
        A client that is never started makes no events request.

        The feed claims the bot's due events about every 2 seconds, and at once after a full batch of 100.
        It handles one event at a time, in ascending ID order: it awaits the handler, marks the transaction if the handler asked for it,
        then reports the event to the API as handled or unhandled. It claims the next batch after every event of the batch was reported.

        A handler is a coroutine method that gets one argument, the `discoin.TransactionEvent`, and returns a `discoin.EventStatus`.
        Its name is ``on_`` followed by the event name with every ``.`` replaced by ``_``, so ``transaction.created`` calls `on_transaction_created`.
        `on_event`, if defined, gets the events that have no named handler, and its return value is used the same way.
        An event that has neither is reported handled. `Client` itself defines no handler.
        An event name that has a character a method name cannot have, other than the ``.``, has no named handler and reaches `on_event`.
        So does an event named ``error``, since `on_error` is not a handler.

        ``EventStatus.COMPLETED`` makes the feed mark the transaction of the event `Completed` and report the event handled.
        ``EventStatus.REFUNDED`` does the same with `Refunded`. The feed sends that mark itself, under the rules below,
        and does not call `mark_completed` or `mark_refunded`. ``EventStatus.HANDLED`` reports the event handled and marks nothing.
        ``EventStatus.UNHANDLED`` reports it unhandled, and the API sends it again after a wait.
        The feed does not check the transaction before it calls a handler. When `attempt` of the event is above 1,
        an earlier try may already have run the handler and marked the transaction.

        The feed sends a mark up to 3 times, 1 second apart, on a 5**, a timeout or a network error, without the retries of `max_retries`.
        A 400 on the mark means the transaction is no longer `Pending`, and a 404 that it does not exist, which includes the transaction
        of a test event that expired. For both, `on_error` gets the `discoin.BadRequest` and the event is reported handled.
        A 429 on the mark that has a `Retry-After` header in whole seconds is waited out for those seconds, then the mark is sent again,
        as one of its 3 tries. A 429 without one is not retried.
        Any other mark that fails goes to `on_error`, and the event is reported unhandled.

        `on_error` is also called when a handler raises or returns anything that is not a `discoin.EventStatus`, ``None`` included,
        and when an event cannot be parsed. Those events are reported unhandled. A report the API answers with a 4** other than a 429
        goes to `on_error` too. The feed keeps running after each of them.

        `start` reads every attribute of the client whose name starts with ``on_``, other than `on_error`, as a handler, and checks them when it is called.
        On a client that has none, it starts no feed and makes no events request, and `events_running` stays ``False``.

        The claim and the report are retried like every other request of the client. The feed stops when one of them
        still fails after `max_retries` retries, and when the claim is answered with a 4** other than a 429.
        A claim answered with a body that has no ``events``, or with an event that has no ``id``, stops it too, since such an event cannot be reported.
        The feed logs the error once with the ``discoin.feed`` logger and keeps it in `events_error`.
        An event that has an ``id`` and cannot be parsed otherwise, for example for an ``attempt`` that is not an ``int`` or a ``test`` that is not a ``bool``,
        does not stop the feed: `on_error` gets the error with ``None`` as the event, and the event is reported unhandled.

        If the bot has a webhook URL, the API returns a 409 on the events routes. On a 409 for the claim the feed logs one warning and stops.
        It does not raise and does not retry, and `events_error` holds the 409.

        :raises TypeError: If an attribute of the client whose name starts with ``on_`` is not a coroutine function. The feed is then not started and `events_error` is not cleared
        """

        await self._feed.start()

    async def on_error(self, error, event):
        """
        Called by the event feed with an error that did not stop it. Override it in a `Client` subclass to handle these errors yourself.
        It is a coroutine method. As written here, it logs the error with its traceback with the ``discoin.client`` logger.
        If it raises, the feed logs that error with the ``discoin.feed`` logger and keeps running.

        It is called when a handler raises, when a handler returns anything that is not a `discoin.EventStatus`,
        when the mark asked by ``EventStatus.COMPLETED`` or ``EventStatus.REFUNDED`` fails, when an event cannot be parsed,
        and when the API answers the report of an event with a 4** other than a 429. See `start` for what is reported in each case

        :param error: (``Exception``) The error
        :param event: (``discoin.TransactionEvent``) The event the error is about. ``None`` if the event could not be parsed
        """

        logger.error("The event feed failed on %s.", "an event that could not be parsed" if event is None else event, exc_info=error)

    async def close(self):
        """
        Stop the event feed, if it was started, then close the aiohttp session, if one was opened. A later request opens a new session.
        A handler that is running is cancelled, and its event is not reported. The API sends it again once its lease and wait are over.

        Called from inside a handler or `on_error`, it cancels nothing: the session is closed, and the handler or `on_error` runs on to its end.
        The feed then stops without another request, so the event it was on is neither marked nor reported,
        and nothing is logged or put in `events_error`
        """

        await self._feed.stop()

        if self._session is None:
            return

        await self._session.close()
        self._session = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()

    async def fetch_pending_transactions(self, **kwargs):
        """
        Get a list of your bot's pending transactions, oldest first. It is recommended to run this every 5 minutes in a loop

        :param code: (``str``) (Optional) 3 letter code of one of your bot's currencies to only fetch transactions into it. Leave it out to fetch transactions into all of your bot's currencies

        :rtype: [discoin.Transaction]

        :raises TypeError: If any keyword argument other than `code` is given
        :raises discoin.InternalServerError: If the discoin API returns a 5** on every attempt `max_retries` allows
        :raises discoin.BadRequest: If the discoin API returns a 4**. A `code` your bot does not run returns a 403
        :raises discoin.WebTimeoutError: If the API times out on every attempt `max_retries` allows
        """

        code = kwargs.pop("code", None)

        if kwargs:
            raise TypeError(f"fetch_pending_transactions() got unexpected keyword arguments: {', '.join(kwargs)}")

        url_path = "/transactions/pending"

        if code is not None:
            currency_id = await self._fetch_currency_id(code.upper())
            url_path += f"?{urlencode({'currencyId': currency_id})}"

        return await self._fetch_transactions(url_path)

    async def fetch_undone_transactions(self, **kwargs):
        """
        Get a list of the undone transactions your bot has not marked handled, oldest undone first.
        A transaction is undone when it is `Refunded`, `Cancelled` or `Reversed`, and the list has those your bot sent and those it received.
        A `Refunded` transaction your bot received is not listed. `handled_at` of each one is when it was undone.
        A transaction stays listed until `mark_handled` is called for it

        :param code: (``str``) (Optional) 3 letter code of one of your bot's currencies. The API then only lists transactions where that currency is your bot's side. Leave it out to list them for all of your bot's currencies
        :param limit: (``int``) (Optional) The most transactions to return, from 1 to 100. Leave it out for the API's default of 50

        :rtype: [discoin.Transaction]

        :raises TypeError: If any keyword argument other than `code` and `limit` is given
        :raises discoin.InternalServerError: If the discoin API returns a 5** on every attempt `max_retries` allows
        :raises discoin.BadRequest: If the discoin API returns a 4**. A 400 if `limit` is not from 1 to 100, a 403 if your bot does not run `code`, a 404 if `code` does not exist or was removed
        :raises discoin.WebTimeoutError: If the API times out on every attempt `max_retries` allows
        """

        code = kwargs.pop("code", None)
        limit = kwargs.pop("limit", None)

        if kwargs:
            raise TypeError(f"fetch_undone_transactions() got unexpected keyword arguments: {', '.join(kwargs)}")

        currency_id = None if code is None else await self._fetch_currency_id(code.upper())

        return await self._fetch_transactions(_with_query("/transactions/undone", currencyId=currency_id, limit=limit))

    async def mark_handled(self, transaction_id: str):
        """
        Mark an undone transaction as handled, which takes it off the list of `fetch_undone_transactions` for your bot.
        Unlike `mark_completed` and `mark_refunded` it returns nothing, since the API answers with no body.
        Marking the same transaction again changes nothing and raises no error

        :param transaction_id: (``str``) The UUID of the transaction

        :raises discoin.InternalServerError: If the discoin API returns a 5** on every attempt `max_retries` allows
        :raises discoin.BadRequest: If the discoin API returns a 4**. A 400 if the transaction was not undone on your bot's side, a 403 if your bot runs neither of its currencies, a 404 if it does not exist
        :raises discoin.WebTimeoutError: If the API times out on every attempt `max_retries` allows
        """

        await self._request("PUT", f"/transactions/{transaction_id}/handled", headers=self._headers)

    async def claim_events(self, limit: int = None):
        """
        Claim your bot's due events from the event feed, in ascending ID order. It does not need `start`.
        The API leases each claimed event for 2 minutes and counts the claim as a try, so `attempt` of each event is 1 on its first claim.
        An event that is not reported with `report_event` is due again once its lease and the wait of that try are over.

        The claim is retried like any other request. When the answer to a claim is lost, the events of that claim stay leased,
        and the API sends them again after the lease and the wait, with `attempt` one higher

        :param limit: (``int``) (Optional) The most events to claim, from 1 to 100. Leave it out for the API's default of 100

        :rtype: [discoin.TransactionEvent]

        :raises discoin.InternalServerError: If the discoin API returns a 5** on every attempt `max_retries` allows
        :raises discoin.BadRequest: If the discoin API returns a 4**. A 409 if your bot has a webhook URL, a 422 if `limit` is not accepted
        :raises discoin.RateLimited: If the discoin API returns a 429 on every attempt `max_retries` allows
        :raises discoin.WebTimeoutError: If the API times out on every attempt `max_retries` allows
        """

        event_objs = await self._claim_event_objs(limit)

        return [TransactionEvent(event_obj) for event_obj in event_objs]

    async def report_event(self, event_id: int, handled: bool):
        """
        Report a claimed event of the event feed as handled or unhandled. It does not need `start`.
        A handled event is final, and reporting it handled again changes nothing and raises no error.
        An unhandled event is due again after a wait that starts at 1 minute and doubles. After 8 unhandled tries the event is dead and the API sends it no more.
        The 2 minute lease does not limit the report. A handled report is accepted whatever became of the event, also when it is already handled or dead.
        An unhandled report is answered with a 409 once the event is handled or dead

        :param event_id: (``int``) The ID of the event
        :param handled: (``bool``) ``True`` to report the event handled, ``False`` to report it unhandled

        :raises discoin.InternalServerError: If the discoin API returns a 5** on every attempt `max_retries` allows
        :raises discoin.BadRequest: If the discoin API returns a 4**. A 404 if the event does not exist, belongs to another bot or was deleted, a 409 if it was never claimed, if it is reported unhandled after it was handled or died, or if your bot has a webhook URL
        :raises discoin.RateLimited: If the discoin API returns a 429 on every attempt `max_retries` allows
        :raises discoin.WebTimeoutError: If the API times out on every attempt `max_retries` allows
        """

        json = {
            "handled": handled,
        }

        await self._request("POST", f"/events/{event_id}/result", headers=self._headers, json=json)

    async def create_transaction(self, code_to: str, amount: float, user_id: int, code_from: str = None):
        """
        Create a transaction

        :param code_to: (``str``) The 3 letter code to send a transaction to. 
        :param amount: (``float``) The amount of currency in original format. 
        :param user_id: (``int``) The Discord ID (17 to 20 digits) of the user who requested the transaction. Any other value returns a 400
        :param code_from: (``str``) (Optional) The 3 letter code of one of your bot's currencies to send a transaction from. Default is `me`.

        :rtype: discoin.Transaction

        Creating the transaction is only retried when the connection to the API could not be made, since the API may have created it
        before a 5**, a 429 or a timeout. On those, check `fetch_pending_transactions` of the receiving bot or your own records before calling it again.
        Looking up the currency IDs before it is retried like any other request.

        :raises TypeError: If `code_from` is not given and the client has no `me`
        :raises discoin.InternalServerError: If the discoin API returns a 5**, without a retry
        :raises discoin.BadRequest: If the discoin API returns a 4**, without a retry. A 403 if `code_from` is not run by your bot, or if the user is blocked from converting these currencies
        :raises discoin.WebTimeoutError: If the API times out after the request was sent, without a retry, or while connecting on every attempt `max_retries` allows
        :raises aiohttp.ClientConnectorError: If the connection to the API cannot be made on every attempt `max_retries` allows
        """

        from_currency_id, to_currency_id = await self._fetch_route_currency_ids(code_to, code_from)
        json = {
            "userId": str(user_id),
            "fromCurrencyId": from_currency_id,
            "toCurrencyId": to_currency_id,
            "amount": amount,
        }

        # A retry after the request reached the API could create the transaction twice
        api_response = await self._request("POST", "/transactions", headers=self._headers, json=json, should_retry=never_reached_api)
        api_response_json = await api_response.json()

        return Transaction(api_response_json)

    async def fetch_quote(self, code_to: str, amount: float, code_from: str = None):
        """
        Get the payout a transaction would have, without creating it

        :param code_to: (``str``) The 3 letter code the transaction would go to.
        :param amount: (``float``) The amount of currency in original format.
        :param code_from: (``str``) (Optional) The 3 letter code the transaction would come from. Default is `me`.

        :rtype: float

        :raises TypeError: If `code_from` is not given and the client has no `me`
        :raises discoin.InternalServerError: If the discoin API returns a 5** on every attempt `max_retries` allows
        :raises discoin.BadRequest: If the discoin API returns a 4**
        :raises discoin.WebTimeoutError: If the API times out on every attempt `max_retries` allows
        """

        from_currency_id, to_currency_id = await self._fetch_route_currency_ids(code_to, code_from)
        query = urlencode({
            "fromCurrencyId": from_currency_id,
            "toCurrencyId": to_currency_id,
            "amount": amount,
        })

        api_response = await self._request("GET", f"/quote?{query}")
        api_response_json = await api_response.json()

        return float(api_response_json['payout'])

    async def mark_completed(self, transaction_id: str):
        """
        Set the status of a transaction to `Completed`, which only marks it as handled.
        Only a `Pending` transaction into one of your bot's currencies can be marked.

        :param transaction_id: (``str``) The UUID of the transaction

        :rtype: discoin.Transaction

        :raises discoin.InternalServerError: If the discoin API returns a 5** on every attempt `max_retries` allows
        :raises discoin.BadRequest: If the discoin API returns a 4**. A 400 if the transaction is not `Pending`, a 403 if your bot does not receive it, a 404 if it does not exist
        :raises discoin.WebTimeoutError: If the API times out on every attempt `max_retries` allows
        """

        return await self._update_transaction_status(transaction_id, TransactionStatus.COMPLETED)

    async def mark_refunded(self, transaction_id: str):
        """
        Set the status of a transaction to `Refunded`, which reverts the currency reserves the transaction moved.
        Giving the user their coins back is up to your bot.
        Only a `Pending` transaction into one of your bot's currencies can be marked.

        :param transaction_id: (``str``) The UUID of the transaction

        :rtype: discoin.Transaction

        :raises discoin.InternalServerError: If the discoin API returns a 5** on every attempt `max_retries` allows
        :raises discoin.BadRequest: If the discoin API returns a 4**. A 400 if the transaction is not `Pending`, a 403 if your bot does not receive it, a 404 if it does not exist
        :raises discoin.WebTimeoutError: If the API times out on every attempt `max_retries` allows
        """

        return await self._update_transaction_status(transaction_id, TransactionStatus.REFUNDED)

    async def fetch_currencies(self):
        """
        This allows you to fetch the available currencies from the API

        :rtype: [discoin.Currency]

        :raises discoin.InternalServerError: If the discoin API returns a 5** on every attempt `max_retries` allows
        :raises discoin.WebTimeoutError: If the API times out on every attempt `max_retries` allows
        """

        api_response = await self._request("GET", "/currencies")
        api_response_json = await api_response.json()
        currencies = []

        for currency_obj in api_response_json:
            currencies.append(Currency(currency_obj))
        
        return currencies

    async def _fetch_transactions(self, url_path: str):
        api_response = await self._request("GET", url_path, headers=self._headers)
        api_response_json = await api_response.json()

        return [Transaction(transaction_obj) for transaction_obj in api_response_json]

    async def _claim_event_objs(self, limit: int = None):
        api_response = await self._request("POST", _with_query("/events/claim", limit=limit), headers=self._headers)
        api_response_json = await api_response.json()

        return api_response_json['events']

    async def _mark_once(self, transaction_id: str, status: TransactionStatus):
        await self._send_transaction_status(transaction_id, status, should_retry=_never_retry)

    async def _update_transaction_status(self, transaction_id: str, status: TransactionStatus):
        api_response = await self._send_transaction_status(transaction_id, status, should_retry=is_retryable)
        api_response_json = await api_response.json()

        return Transaction(api_response_json)

    async def _send_transaction_status(self, transaction_id: str, status: TransactionStatus, should_retry):
        json = {
            "status": status.value,
        }

        return await self._request("PATCH", f"/transactions/{transaction_id}", headers=self._headers, json=json, should_retry=should_retry)

    async def _fetch_route_currency_ids(self, code_to: str, code_from: str):
        from_currency_id = await self._fetch_currency_id(self._resolve_code_from(code_from))
        to_currency_id = await self._fetch_currency_id(code_to.upper())

        return from_currency_id, to_currency_id

    def _resolve_code_from(self, code_from: str):
        if code_from is not None:
            return code_from.upper()

        if self._me is None:
            raise TypeError("code_from is required when the client was created without me")

        return self._me

    def _open_session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()

        return self._session

    async def _request(self, method: str, url_path: str, headers: dict = None, json: dict = None, should_retry=is_retryable):
        # The session is looked up on each attempt, since `close` can drop it while a retry waits
        return await with_backoff(
            lambda: send_request(self._open_session(), method, url_path, headers=headers, json=json),
            self._max_retries,
            should_retry,
        )

    async def _fetch_currency_id(self, code: str):
        api_response = await self._request("GET", f"/currencies/{quote(code, safe='')}")
        api_response_json = await api_response.json()

        return api_response_json['id']


def _never_retry(error):
    return False


def _with_query(url_path: str, **parameters):
    sent_parameters = {name: value for name, value in parameters.items() if value is not None}
    if not sent_parameters:
        return url_path

    return f"{url_path}?{urlencode(sent_parameters)}"