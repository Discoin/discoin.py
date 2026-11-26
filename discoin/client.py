import aiohttp
from urllib.parse import quote, urlencode

from .classes import Transaction, Currency, TransactionStatus, TransactionEvent
from .feed import EventFeed
from .utils import api_request


class Client():
    """
    Main used class for discoin
    """

    def __init__(self, token: str, me: str = None):
        """
        Init client.

        :param token: (``str``) Your api token for discoin 
        :param me: (``str``) (Optional) Your 3 letter currency code, the default `code_from` of `create_transaction` and `fetch_quote`. Leave it out if your bot runs several currencies
        """

        # Needed vars
        self._headers = {"Authorization": f"Bearer {token}"}
        self._me = me
        self._session = None
        self._feed = EventFeed(self, self._fetch_event_objs, self.acknowledge_events)

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

        The feed reads the bot's events about every 2 seconds, and at once after a full batch of 100.
        It awaits the handler methods of a `Client` subclass one event at a time, in ascending ID order.
        After the handlers of a whole batch returned, it acknowledges the highest ID of the batch, events without a handler included.

        A handler is a coroutine method that gets one argument, the `discoin.TransactionEvent`. Its name is ``on_`` followed by
        the event name with every ``.`` replaced by ``_``, so ``transaction.created`` calls `on_transaction_created`.
        `on_event`, if defined, gets every event, after the named handler of that event. `Client` itself defines no handler.
        An event name that has a character a method name cannot have, other than the ``.``, has no named handler and only reaches `on_event`.
        An event named ``event`` calls `on_event` once.

        `start` reads every attribute of the client whose name starts with ``on_`` as a handler, and checks them when it is called.
        On a client that has none, it starts no feed and makes no events request, and `events_running` stays ``False``.

        The feed stops when a handler raises or an event cannot be parsed. It acknowledges the events handled before that one,
        logs the error once and keeps it in `events_error`. The API sends the other events again after the next `start`.
        A 4** other than a 429 stops it the same way. A 429 is waited out for the seconds of its `Retry-After` header,
        and a 5**, a timeout or a network error is retried with a growing wait, up to 60 seconds.
        A 429 without a `Retry-After` header in whole seconds stops the feed.

        If the bot has a webhook URL, the API returns a 409 on the events routes. The feed then logs one warning and stops.
        It does not raise and does not retry, and `events_error` holds the 409.

        :raises TypeError: If an attribute of the client whose name starts with ``on_`` is not a coroutine function. The feed is then not started and `events_error` is not cleared
        """

        await self._feed.start()

    async def close(self):
        """
        Stop the event feed, if it was started, then close the aiohttp session, if one was opened. A later request opens a new session.
        A handler that is running is cancelled, and its event is not acknowledged
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
        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.BadRequest: If the discoin API returns a 4**. A `code` your bot does not run returns a 403
        :raises discoin.WebTimeoutError: If the API times out
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
        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.BadRequest: If the discoin API returns a 4**. A 400 if `limit` is not from 1 to 100, a 403 if your bot does not run `code`, a 404 if `code` does not exist or was removed
        :raises discoin.WebTimeoutError: If the API times out
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

        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.BadRequest: If the discoin API returns a 4**. A 400 if the transaction was not undone on your bot's side, a 403 if your bot runs neither of its currencies, a 404 if it does not exist
        :raises discoin.WebTimeoutError: If the API times out
        """

        await api_request(self._open_session(), "PUT", f"/transactions/{transaction_id}/handled", headers=self._headers)

    async def fetch_events(self, after: int = None, limit: int = None):
        """
        Get a list of your bot's events from the event feed, in ascending ID order. It does not need `start`

        :param after: (``int``) (Optional) Only fetch events with an ID above this one. Leave it out to start after the last acknowledged event. Giving it does not move the acknowledged position
        :param limit: (``int``) (Optional) The most events to return, from 1 to 100. Leave it out for the API's default of 100

        :rtype: [discoin.TransactionEvent]

        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.BadRequest: If the discoin API returns a 4**. A 409 if your bot has a webhook URL, a 422 if `after` or `limit` is not accepted
        :raises discoin.RateLimited: If the discoin API returns a 429
        :raises discoin.WebTimeoutError: If the API times out
        """

        event_objs = await self._fetch_event_objs(after=after, limit=limit)

        return [TransactionEvent(event_obj) for event_obj in event_objs]

    async def acknowledge_events(self, event_id: int):
        """
        Acknowledge every event of the event feed up to and including `event_id`, so the API stops sending them. It does not need `start`.
        Acknowledging an ID at or below the last acknowledged one changes nothing and raises no error.
        Acknowledging the ID of an event the API already deleted works, as long as it is not above your bot's newest event

        :param event_id: (``int``) The ID of the newest event to acknowledge

        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.BadRequest: If the discoin API returns a 4**. A 400 with the field `id` if `event_id` is above your bot's newest event, a 409 if your bot has a webhook URL
        :raises discoin.RateLimited: If the discoin API returns a 429
        :raises discoin.WebTimeoutError: If the API times out
        """

        json = {
            "id": event_id,
        }

        await api_request(self._open_session(), "POST", "/events/ack", headers=self._headers, json=json)

    async def create_transaction(self, code_to: str, amount: float, user_id: int, code_from: str = None):
        """
        Create a transaction

        :param code_to: (``str``) The 3 letter code to send a transaction to. 
        :param amount: (``float``) The amount of currency in original format. 
        :param user_id: (``int``) The Discord ID (17 to 20 digits) of the user who requested the transaction. Any other value returns a 400
        :param code_from: (``str``) (Optional) The 3 letter code of one of your bot's currencies to send a transaction from. Default is `me`.

        :rtype: discoin.Transaction

        :raises TypeError: If `code_from` is not given and the client has no `me`
        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.BadRequest: If the discoin API returns a 4**. A 403 if `code_from` is not run by your bot, or if the user is blocked from converting these currencies
        :raises discoin.WebTimeoutError: If the API times out
        """

        from_currency_id, to_currency_id = await self._fetch_route_currency_ids(code_to, code_from)
        json = {
            "userId": str(user_id),
            "fromCurrencyId": from_currency_id,
            "toCurrencyId": to_currency_id,
            "amount": amount,
        }

        api_response = await api_request(self._open_session(), "POST", "/transactions", headers=self._headers, json=json)
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
        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.BadRequest: If the discoin API returns a 4**
        :raises discoin.WebTimeoutError: If the API times out
        """

        from_currency_id, to_currency_id = await self._fetch_route_currency_ids(code_to, code_from)
        query = urlencode({
            "fromCurrencyId": from_currency_id,
            "toCurrencyId": to_currency_id,
            "amount": amount,
        })

        api_response = await api_request(self._open_session(), "GET", f"/quote?{query}")
        api_response_json = await api_response.json()

        return float(api_response_json['payout'])

    async def mark_completed(self, transaction_id: str):
        """
        Set the status of a transaction to `Completed`, which only marks it as handled.
        Only a `Pending` transaction into one of your bot's currencies can be marked.

        :param transaction_id: (``str``) The UUID of the transaction

        :rtype: discoin.Transaction

        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.BadRequest: If the discoin API returns a 4**. A 400 if the transaction is not `Pending`, a 403 if your bot does not receive it, a 404 if it does not exist
        :raises discoin.WebTimeoutError: If the API times out
        """

        return await self._update_transaction_status(transaction_id, TransactionStatus.COMPLETED)

    async def mark_refunded(self, transaction_id: str):
        """
        Set the status of a transaction to `Refunded`, which reverts the currency reserves the transaction moved.
        Giving the user their coins back is up to your bot.
        Only a `Pending` transaction into one of your bot's currencies can be marked.

        :param transaction_id: (``str``) The UUID of the transaction

        :rtype: discoin.Transaction

        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.BadRequest: If the discoin API returns a 4**. A 400 if the transaction is not `Pending`, a 403 if your bot does not receive it, a 404 if it does not exist
        :raises discoin.WebTimeoutError: If the API times out
        """

        return await self._update_transaction_status(transaction_id, TransactionStatus.REFUNDED)

    async def fetch_currencies(self):
        """
        This allows you to fetch the available currencies from the API

        :rtype: [discoin.Currency]

        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.WebTimeoutError: If the API times out
        """

        api_response = await api_request(self._open_session(), "GET", f"/currencies")
        api_response_json = await api_response.json()
        currencies = []

        for currency_obj in api_response_json:
            currencies.append(Currency(currency_obj))
        
        return currencies

    async def _fetch_transactions(self, url_path: str):
        api_response = await api_request(self._open_session(), "GET", url_path, headers=self._headers)
        api_response_json = await api_response.json()

        return [Transaction(transaction_obj) for transaction_obj in api_response_json]

    async def _fetch_event_objs(self, **query):
        api_response = await api_request(self._open_session(), "GET", _with_query("/events", **query), headers=self._headers)
        api_response_json = await api_response.json()

        return api_response_json['events']

    async def _update_transaction_status(self, transaction_id: str, status: TransactionStatus):
        json = {
            "status": status.value,
        }

        api_response = await api_request(self._open_session(), "PATCH", f"/transactions/{transaction_id}", headers=self._headers, json=json)
        api_response_json = await api_response.json()

        return Transaction(api_response_json)

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

    async def _fetch_currency_id(self, code: str):
        api_response = await api_request(self._open_session(), "GET", f"/currencies/{quote(code, safe='')}")
        api_response_json = await api_response.json()

        return api_response_json['id']


def _with_query(url_path: str, **parameters):
    sent_parameters = {name: value for name, value in parameters.items() if value is not None}
    if not sent_parameters:
        return url_path

    return f"{url_path}?{urlencode(sent_parameters)}"