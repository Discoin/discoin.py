Getting Started
===============

Installing *discoin.py*
-----------------------

To start with *discoin.py* you will need to install it via pip/pypi with
the following command

::

    $ pip install discoin

|

Integrating discoin
-------------------

*discoin.py* configuration is the most important part of the process.
You will see and notice, it is really hard! So you will need 2
information to get it up and running. First is your Discoin token,
which you get from the bot owner page on Discoin. Tokens made for the
old Discoin API no longer work, so regenerate yours there. Second
information is the 3 digits character of your currency.

.. code:: py

    from discoin import Client

    client = Client("<TOKEN>", "ABC")

If your bot runs several currencies, leave the currency code out and
pass ``code_from`` to ``create_transaction`` and ``fetch_quote``

.. code:: py

    from discoin import Client

    client = Client("<TOKEN>")

You can also use the client as an async context manager, which closes
its session when the block ends

.. code:: py

    from discoin import Client

    async with Client("<TOKEN>", "ABC") as client:
        currencies = await client.fetch_currencies()

Every request the client makes is retried on a 5**, a 429, a timeout
or a network error. The wait starts at 1 second and doubles up to 128
seconds, and a 429 with a ``Retry-After`` header waits the seconds it
names instead. Other 4** are raised at once. By default a request gives
up after 8 retries, the one that follows the first wait of 128 seconds,
and raises the last error. Pass ``max_retries`` to change that, or
``None`` to retry until the request succeeds

``create_transaction`` only retries when the connection to the API
could not be made. After a 5**, a 429 or a timeout the API may already
have created the transaction, so it raises the error at once instead of
creating a second one

.. code:: py

    from discoin import Client

    client = Client("<TOKEN>", "ABC", max_retries=5)

|

Events
------

The API keeps a feed of events for each bot. *discoin.py* can read it in
the background and call the handler methods of a ``Client`` subclass

.. code:: py

    from discoin import Client

    class MyClient(Client):
        async def on_transaction_created(self, event):
            print(event.id, event.event, event.transaction.payout)

    client = MyClient("<TOKEN>", "ABC")

    await client.start()

``start()`` returns at once, and the feed runs as a background task in
the running loop. There is no ``run()``. ``close()`` stops the feed.
A client that was never started makes no events request. Defining
handlers on it is allowed, and nothing is called.

**Handlers**

- A handler is a coroutine method of a ``Client`` subclass that gets
  one argument, the ``TransactionEvent``.
- The method name is ``on_`` followed by the event name, with every
  ``.`` replaced by ``_``. ``transaction.created`` calls
  ``on_transaction_created``, ``transaction.cancelled`` calls
  ``on_transaction_cancelled``, ``transaction.reversed`` calls
  ``on_transaction_reversed`` and ``transaction.test`` calls
  ``on_transaction_test``. An event name the API adds later calls the
  method named the same way.
- ``on_event`` gets every event.
- An event name with a character that a method name cannot have, other
  than the ``.``, has no named handler and only reaches ``on_event``.
- ``Client`` itself defines no handler. A plain ``Client`` works for
  every other call.
- ``start()`` takes every attribute of the client whose name starts
  with ``on_`` as a handler. It raises a ``TypeError`` if one of them
  is not a coroutine function. On a client that has none, it starts no
  feed and ``client.events_running`` stays ``False``.
- Handlers run one at a time, the named handler first, then
  ``on_event``. The next event waits until every handler of the
  current one returned, so a slow handler delays the reads.
- ``event.event`` and ``event.triggered_by.kind`` are plain strings.
  ``EventType`` and ``TriggerKind`` list the values the API sends today,
  and other values can appear later.

**What the API sends**

- Only the bot that runs the currency a transaction goes to gets its
  events. The sending bot gets none.
- Event IDs are per bot. They start at 1, count up and are not used
  twice.
- ``transaction.created`` is also sent when the owner resends a
  transaction from the dashboard, with the same transaction ID and a
  new event ID.
- The transaction inside an event is a snapshot from when the event was
  written. It is a ``FeedTransaction``, which has the currency UUIDs
  but no currency labels, unlike ``Transaction``.
- The Test button of the bot owner page writes a real event,
  ``transaction.test``, with the next event ID. It is delivered to
  handlers and acknowledged like any other event. Its transaction ID
  exists nowhere else, both currency UUIDs are
  ``00000000-0000-0000-0000-000000000000``, the amount is 100.0, the
  payout is 10.0 and the status is ``Pending``. ``mark_completed`` and
  ``mark_refunded`` on it raise a 404.

**Reading and acknowledging**

- The feed reads about every 2 seconds, and at once after a full batch
  of 100 events. A client that defines no handler makes no events
  request.
- After the handlers of a whole batch returned, the feed acknowledges
  the highest event ID of the batch. The API sends acknowledged events
  no more.
- An event that has no handler is acknowledged with its batch all the
  same. A bot that only defines ``on_transaction_created`` does not see
  its cancelled or reversed events again.
- Delivery is at least once. A bot that stops between handling an event
  and acknowledging it gets that event again.
- The API allows 300 requests a minute per token and answers a 429 with
  a ``Retry-After`` header above that. The feed waits that long, then
  continues.
- The feed retries a 5**, a timeout, a network error and a 429 without
  a ``Retry-After`` header, with a wait that starts at 1 second and
  doubles up to 128 seconds. A request that still fails after
  ``max_retries`` retries, 8 by default, stops the feed.

**When the feed stops**

- A handler that raises stops the feed, and so does an event that
  cannot be parsed. The events handled before it are acknowledged, the
  error is logged with the ``discoin`` logger and kept in
  ``client.events_error``, and ``client.events_running`` turns
  ``False``. After the next ``start()`` the API sends the event again.
- A 4** other than a 429 stops the feed the same way, and so does a
  request that still fails after ``max_retries`` retries.

**Webhooks**

- A bot gets its events on one path. While the bot has a webhook URL,
  its events go to the webhook, and the API answers a 409 on the feed.
  Each event goes to the webhook or to the feed, never to both.
- Saving a webhook URL deletes the events stored in the feed.
- On a 409 the feed logs one warning and stops. It does not raise and
  does not retry, which is a choice of the library. The 409 is kept in
  ``client.events_error``, and ``start()`` starts the feed again once
  the URL is removed.

**Events are kept for 24 hours**

- The API deletes an event 24 hours after it was written, read or not.
  A bot that was offline for longer gets no notice of it.
- Deleted events leave a gap that the API skips without an error and
  without a marker, so the IDs of a read are ascending but not always
  consecutive. A bot whose events all expired reads an empty list.
- *discoin.py* does not detect gaps and logs nothing about skipped IDs.
- ``fetch_pending_transactions`` only lists ``Pending`` transactions,
  so a cancellation or reversal that was missed as an event is not in
  it. It is in the list of ``fetch_undone_transactions``, see below.
- *discoin.py* reads neither list by itself. When your bot calls them
  is your choice.

**Without the background feed**

``fetch_events`` and ``acknowledge_events`` map the two routes of the
feed, for a bot that reads it in its own loop. They do not need
``start()``, and they raise on every error, a 409 included. ``after``
of ``fetch_events`` does not move the acknowledged position.

The API outlines a pushed stream of the same events for later. It
would use the same event IDs and the same acknowledged position.

An example cog that uses the feed can be found `here <https://git.gami.app/Discoin/discoin.py/src/branch/master/examples/example_events_cog.py>`__.

|

Undone transactions
-------------------

A transaction is undone when it is ``Refunded``, ``Cancelled`` or
``Reversed``. ``fetch_undone_transactions`` returns every undone
transaction your bot has not marked handled, whichever side of it your
bot is on, and ``mark_handled`` takes one off the list

.. code:: py

    undone = await client.fetch_undone_transactions()

    await client.mark_handled("<TRANSACTION ID>")

Events are kept for 24 hours and gaps are silent, so the API keeps this
list for the reversals a bot missed. A sending bot gets no events at
all, so this list is the only place where it sees that a transaction it
sent was refunded, cancelled or reversed.

========= ============================== ==============================
Status    Your bot runs the currency     Your bot runs the currency
          the transaction goes to        the transaction comes from
========= ============================== ==============================
Refunded  not listed, your bot set it    listed
Cancelled listed                         listed
Reversed  listed                         listed
========= ============================== ==============================

- A transaction has no field for the side. ``currency_from_id`` and
  ``currency_to_id`` show which of the two currencies is your bot's.
- A bot that runs both currencies of a transaction gets it once, and
  one ``mark_handled`` clears it.
- A transaction stays listed until your bot marks it handled. There is
  no time window and no cursor. An event that was delivered or
  acknowledged does not clear it, so a cancelled or reversed
  transaction can reach a receiving bot twice, once as an event and
  once in this list.
- ``handled_at`` of an undone transaction is when it was undone. The
  list is ordered by it, oldest first.
- ``limit`` is from 1 to 100, and the API's default is 50. Any other
  value is a 400.
- Marking is what moves the list on. A full list means more can be
  waiting once these are marked. A transaction that is not marked comes
  back first on every call.
- Transactions of a removed currency are listed when no ``code`` is
  given, with ``removed`` set on that currency's label. With the
  ``code`` of a removed currency, the API answers a 404.
- Both calls work the same for a bot with a webhook and a bot on the
  event feed, and neither needs ``start()``.
- The marks belong to the transaction, not to the token or the owner.
  Unhandled transactions stay listed after a token is regenerated, the
  owner changes or the bot is removed.
- ``mark_handled`` returns nothing, and a repeat changes nothing. The
  API answers a 404 for an unknown transaction, a 403 when your bot
  runs neither currency, and a 400 when the transaction was not undone
  on your bot's side.
- *discoin.py* does not call either of them by itself.

|

Example
-------

An example cog for discord.py can be found `here <https://git.gami.app/Discoin/discoin.py/src/branch/master/examples/example_cog.py>`_. Just be sure to put your token and currency code at `L11 <https://git.gami.app/Discoin/discoin.py/src/branch/master/examples/example_cog.py#L11>`_, and be sure to add/remove currency at lines `L26 <https://git.gami.app/Discoin/discoin.py/src/branch/master/examples/example_cog.py#L26>`_, `L47 <https://git.gami.app/Discoin/discoin.py/src/branch/master/examples/example_cog.py#L47>`_ and `L49 <https://git.gami.app/Discoin/discoin.py/src/branch/master/examples/example_cog.py#L49>`_
