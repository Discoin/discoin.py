import datetime
import re
from enum import Enum

_TIMESTAMP_PATTERN = re.compile(
    r"(?P<moment>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
    r"(?:\.(?P<microsecond>\d{6}))?"
    r"(?:Z|(?P<offset_sign>[+-])(?P<offset_hours>\d{2}):(?P<offset_minutes>[0-5]\d))",
    re.ASCII,
)
_MOMENT_FORMAT = "%Y-%m-%dT%H:%M:%S"


def _parse_timestamp(timestamp: str):
    match = _TIMESTAMP_PATTERN.fullmatch(timestamp)
    if match is None:
        raise ValueError(f"{timestamp!r} is not a timestamp in the format the Discoin API sends")

    moment = datetime.datetime.strptime(match.group('moment'), _MOMENT_FORMAT)
    microsecond = 0 if match.group('microsecond') is None else int(match.group('microsecond'))

    return moment.replace(microsecond=microsecond, tzinfo=_parse_offset(match)).astimezone(datetime.timezone.utc)


def _parse_offset(match):
    if match.group('offset_sign') is None:
        return datetime.timezone.utc

    offset = datetime.timedelta(hours=int(match.group('offset_hours')), minutes=int(match.group('offset_minutes')))

    return datetime.timezone(-offset if match.group('offset_sign') == '-' else offset)


class TransactionStatus(str, Enum):
    """
    The status of a transaction. Members compare equal to the API's status strings, e.g. ``TransactionStatus.COMPLETED == "Completed"``

    ``CANCELLED`` and ``REVERSED`` are only set by the API, when a currency is removed or deactivated or a user is blocked, never by a bot
    """

    PENDING = "Pending"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    REFUNDED = "Refunded"
    REVERSED = "Reversed"


class _TransactionFields():
    def __init__(self, transaction_obj):
        self.id = transaction_obj['id']
        self.currency_from_id = transaction_obj['fromCurrencyId']
        self.currency_to_id = transaction_obj['toCurrencyId']
        self.amount = float(transaction_obj['amount'])
        self.payout = float(transaction_obj['payout'])
        self.user_id = int(transaction_obj['userId'])
        self.status = TransactionStatus(transaction_obj['status'])
        self.submitted_at = _parse_timestamp(transaction_obj['submittedAt'])

        handled_at = transaction_obj['handledAt']
        self.handled_at = None if handled_at is None else _parse_timestamp(handled_at)

    def __str__(self):
        return f"{type(self).__name__}({self.id})"


class Transaction(_TransactionFields):
    """
    Transaction object

    :param id: (``str``) The UUID or receipt of the transaction
    :param currency_from_id: (``str``) The UUID of the currency that the transaction is coming from
    :param currency_to_id: (``str``) The UUID of the currency that the transaction is going to
    :param currency_from: (``discoin.CurrencyLabel``) The label of the currency that the transaction is coming from
    :param currency_to: (``discoin.CurrencyLabel``) The label of the currency that the transaction is going to
    :param amount: (``float``) The original amount of the transaction
    :param user_id: (``int``) the id of the user who requested the transaction
    :param status: (``discoin.TransactionStatus``) The status of the transaction
    :param submitted_at: (``datetime.datetime``) When the transaction was submitted, in UTC
    :param handled_at: (``datetime.datetime``) When the transaction was handled, in UTC. ``None`` if it has not been handled
    :param payout: (``float``) The amount calculated to its final destination
    """

    def __init__(self, transaction_obj):
        super().__init__(transaction_obj)
        self.currency_from = CurrencyLabel(transaction_obj['fromCurrency'])
        self.currency_to = CurrencyLabel(transaction_obj['toCurrency'])


class FeedTransaction(_TransactionFields):
    """
    The transaction inside an event of the event feed. The API sends no currency labels there, so it carries the currency UUIDs only, unlike `discoin.Transaction`

    :param id: (``str``) The UUID or receipt of the transaction
    :param currency_from_id: (``str``) The UUID of the currency that the transaction is coming from
    :param currency_to_id: (``str``) The UUID of the currency that the transaction is going to
    :param amount: (``float``) The original amount of the transaction
    :param user_id: (``int``) the id of the user who requested the transaction
    :param status: (``discoin.TransactionStatus``) The status of the transaction when the event was written
    :param submitted_at: (``datetime.datetime``) When the transaction was submitted, in UTC
    :param handled_at: (``datetime.datetime``) When the transaction was handled, in UTC. ``None`` if it has not been handled
    :param payout: (``float``) The amount calculated to its final destination
    """


class _AllEvents():
    def __repr__(self):
        return "EventType.ALL"


class EventType():
    """
    The event names the API sends today, and the catch-all key for `Client.listen` and `Client.add_listener`.
    `TransactionEvent.event` is always a plain string, so a name that is not listed here passes through unchanged

    ``CREATED`` is ``"transaction.created"``, ``CANCELLED`` is ``"transaction.cancelled"``, ``REVERSED`` is ``"transaction.reversed"`` and ``TEST`` is ``"transaction.test"``

    ``ALL`` is not a string and equals no event name. A handler registered under it receives every event, listed here or not
    """

    CREATED = "transaction.created"
    CANCELLED = "transaction.cancelled"
    REVERSED = "transaction.reversed"
    TEST = "transaction.test"
    ALL = _AllEvents()


class TriggerKind():
    """
    The values of `EventTrigger.kind` the API sends today.
    `EventTrigger.kind` is always a plain string, so a value that is not listed here passes through unchanged

    ``ADMINS`` is ``"admins"`` and ``OWNER`` is ``"owner"``
    """

    ADMINS = "admins"
    OWNER = "owner"


class EventTrigger():
    """
    Who caused an event, on events caused by a block

    :param kind: (``str``) Who blocked the user. See `discoin.TriggerKind`
    :param bot_id: (``str``) The UUID of the bot whose owner blocked the user. ``None`` if the API sent none
    """

    def __init__(self, trigger_obj):
        self.kind = _require_type(trigger_obj['kind'], str)
        self.bot_id = trigger_obj.get('botId')

    def __str__(self):
        return f"EventTrigger({self.kind})"


class TransactionEvent():
    """
    An event of the event feed

    :param id: (``int``) The ID of the event. IDs count up per bot, start at 1 and are never used twice
    :param event: (``str``) The name of the event. See `discoin.EventType`
    :param transaction: (``discoin.FeedTransaction``) The transaction as it was when the event was written
    :param triggered_by: (``discoin.EventTrigger``) Who caused the event. ``None`` if the API sent none
    """

    def __init__(self, event_obj):
        self.id = _require_type(event_obj['id'], int)
        self.event = _require_type(event_obj['event'], str)
        self.transaction = FeedTransaction(event_obj['transaction'])

        trigger_obj = event_obj.get('triggeredBy')
        self.triggered_by = None if trigger_obj is None else EventTrigger(trigger_obj)

    def __str__(self):
        return f"TransactionEvent({self.id})"


def _require_type(value, expected_type):
    if not isinstance(value, expected_type):
        raise TypeError(f"{value!r} is not of the type {expected_type.__name__} the Discoin API sends")

    return value


class CurrencyLabel():
    """
    The label of a currency inside a transaction

    :param abbreviation: (``str``) The 3 letter code of the currency
    :param name: (``str``) The provided name of the currency
    :param removed: (``bool``) If the currency has been removed from Discoin
    """

    def __init__(self, label_obj):
        self.abbreviation = label_obj['abbreviation']
        self.name = label_obj['name']
        self.removed = label_obj['removed']

    def __str__(self):
        return f"CurrencyLabel({self.abbreviation})"


class Currency():
    """
    Currency Object

    :param id: (``str``) The UUID of the currency
    :param abbreviation: (``str``) The 3 letter code of the currency
    :param name: (``str``) The provided name of the currency
    :param value: (``float``) The latest recorded value, the last entry of ``value_history``. Raises ``ValueError`` if ``value_history`` is empty
    :param value_history: (``List[float]``) Up to 8 daily values of the currency, oldest first
    :param reserve: (``float``) The amount of currency trade left
    :param active: (``bool``) If the currency is active
    :param change24h: (``float``) The change of the currency in the last 24 hours
    """

    def __init__(self, currency_obj):
        self.id = currency_obj['id']
        self.abbreviation = currency_obj['abbreviation']
        self.name = currency_obj['name']
        self.value_history = [float(value) for value in currency_obj['valueHistory']]
        self.reserve = float(currency_obj['reserve'])
        self.active = currency_obj['active']
        self.change24h = float(currency_obj['change24h'])

    @property
    def value(self):
        if not self.value_history:
            raise ValueError(f"{self} has no value history")

        return self.value_history[-1]

    def __str__(self):
        return f"Currency({self.abbreviation})"
