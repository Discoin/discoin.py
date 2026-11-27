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
the background, call the handler methods of a ``Client`` subclass and
tell the API what became of each event

.. code:: py

    from discoin import Client, EventStatus

    class MyClient(Client):
        async def on_transaction_created(self, event):
            print(event.id, event.event, event.transaction.payout)

            return EventStatus.COMPLETED

    client = MyClient("<TOKEN>", "ABC")

    await client.start()

``start()`` returns at once, and the feed runs as a background task in
the running loop. There is no ``run()``. ``close()`` stops the feed.
A client that was never started makes no events request. Defining
handlers on it is allowed, and nothing is called.

**Handlers**

- A handler is a coroutine method of a ``Client`` subclass that gets
  one argument, the ``TransactionEvent``, and returns an
  ``EventStatus``.
- The method name is ``on_`` followed by the event name, with every
  ``.`` replaced by ``_``. ``transaction.created`` calls
  ``on_transaction_created``, ``transaction.cancelled`` calls
  ``on_transaction_cancelled`` and ``transaction.reversed`` calls
  ``on_transaction_reversed``. An event name the API adds later calls
  the method named the same way.
- ``on_event`` gets the events that have no named handler. Its return
  value is used like that of a named handler.
- An event that has neither a named handler nor ``on_event`` is
  reported handled. A bot that only defines ``on_transaction_created``
  does not see its cancelled or reversed events again.
- An event name with a character that a method name cannot have, other
  than the ``.``, has no named handler and reaches ``on_event``. So
  does an event named ``error``, since ``on_error`` is not a handler.
- ``Client`` itself defines no handler. A plain ``Client`` works for
  every other call.
- ``start()`` takes every attribute of the client whose name starts
  with ``on_``, other than ``on_error``, as a handler. It raises a
  ``TypeError`` if one of them, or ``on_error``, is not a coroutine
  function. On a client that has no handler, it starts no feed and
  ``client.events_running`` stays ``False``.
- Events are handled one at a time, in ascending ID order. The next
  event waits until the current one was reported, so a slow handler
  delays the events after it.
- ``event.event`` and ``event.triggered_by.kind`` are plain strings.
  ``EventType`` and ``TriggerKind`` list the values the API sends today,
  and other values can appear later.

**What a handler returns**

=========================  ===================================================
Return value               What the feed does
=========================  ===================================================
``EventStatus.COMPLETED``  marks the transaction of the event
                           ``Completed``, then reports the event handled
``EventStatus.REFUNDED``   marks the transaction of the event
                           ``Refunded``, then reports the event handled
``EventStatus.HANDLED``    reports the event handled and marks nothing
``EventStatus.UNHANDLED``  reports the event unhandled, and the API sends
                           it again after a wait
=========================  ===================================================

- Any other return value is an error, ``None`` included, so a handler
  without a ``return`` has its events reported unhandled. ``on_error``
  gets a ``TypeError``.
- The feed sends the mark itself and does not call ``mark_completed``
  or ``mark_refunded``, so overriding them does not change what the
  feed does.
- The feed sends the mark up to 3 times, 1 second apart, on a 5**, a
  timeout or a network error. ``max_retries`` does not apply to it.
- A 400 on the mark means the transaction is no longer ``Pending``,
  and a 404 that it does not exist, which includes the transaction of
  a test event that expired. For both, ``on_error`` gets the
  ``BadRequest``, and the event is reported handled.
- A 429 on the mark that has a ``Retry-After`` header in whole seconds
  is waited out for those seconds, then the mark is sent again, as one
  of its 3 tries. A 429 without one is not retried.
- Any other mark that fails goes to ``on_error``, and the event is
  reported unhandled.

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
- ``event.attempt`` counts how many times the API has handed the event
  out, this time included. It is 1 on the first claim.
- ``event.test`` is ``True`` on the event the Test button of the bot
  owner page sends, and ``False`` on every other event. The test event
  is a ``transaction.created`` with the next event ID, claimed and
  reported like any other event. ``mark_completed`` and
  ``mark_refunded`` on its transaction record the status and return
  the transaction, and no real transaction changes.

**Claiming and reporting**

- The feed claims the bot's due events about every 2 seconds, and at
  once after a full batch of 100 events. A client that defines no
  handler makes no events request.
- The API leases a claimed event for 2 minutes. During the lease no
  claim returns it.
- After the handler of an event returned, and after the mark if there
  is one, the feed reports the event to the API as handled or
  unhandled. It claims the next batch after every event of the batch
  was reported.
- A handled event is final. The API sends it no more.
- An unhandled event is due again after a wait that starts at 1 minute
  and doubles. An event that is claimed and not reported is due again
  once its lease and that wait are over, and counts as a try the same
  way.
- After 8 tries that were not reported handled, the event is dead. The
  API sends a dead event no more.
- The lease does not limit the report. A handled report is accepted
  whatever became of the event, also when it is already handled or
  dead. An unhandled report is answered with a 409 once the event is
  handled or dead.
- An event that is waiting does not hold back the events after it.
  They are claimed and handled while it waits, so events are not
  always handled in the order they were written.
- Delivery is at least once. When ``event.attempt`` is above 1, an
  earlier try may already have run the handler and marked the
  transaction. A handler that pays the user pays twice in that case,
  unless it recognises the transaction ID it already paid.
- *discoin.py* does not check the transaction before it calls a
  handler.
- The claim is retried like every other request. When the answer to a
  claim is lost, the events of that claim stay leased, and the API
  sends them again after the lease and the wait, with ``attempt`` one
  higher.
- The API allows 1200 requests a minute per IP address, shared by
  every bot on that address, and answers a 429 with a ``Retry-After``
  header above that. The feed waits that long, then continues.
- The claim and the report are retried on a 5**, a timeout, a network
  error and a 429 without a ``Retry-After`` header, with a wait that
  starts at 1 second and doubles up to 128 seconds.

**Errors that do not stop the feed**

``on_error(error, event)`` is a coroutine method of ``Client`` that a
subclass can override. As it comes, it logs the error with its
traceback with the ``discoin.client`` logger. The feed calls it and
keeps running when

- a handler raises. The event is reported unhandled.
- a handler returns anything that is not an ``EventStatus``. The event
  is reported unhandled.
- a mark fails, as described above.
- an event cannot be parsed. ``event`` is then ``None``, and the event
  is reported unhandled.
- the API answers the report of an event with a 4** other than a 429,
  for example a 404 for an event that was deleted in the meantime.

If ``on_error`` itself raises, the feed logs that error with the
``discoin.feed`` logger and keeps running.

.. code:: py

    class MyClient(Client):
        async def on_error(self, error, event):
            print(event, repr(error))

**When the feed stops**

- A 4** other than a 429 on the claim stops the feed. The error is
  logged with the ``discoin.feed`` logger and kept in
  ``client.events_error``, and ``client.events_running`` turns
  ``False``.
- A claim or a report that still fails after ``max_retries`` retries, 8
  by default, stops the feed the same way.
- A claim answered with a body that has no ``events``, or with an
  event that has no ``id``, stops the feed the same way, since such an
  event cannot be reported.
- An event that has an ``id`` and cannot be parsed otherwise, for
  example for an ``attempt`` that is not an ``int`` or a ``test`` that
  is not a ``bool``, does not stop the feed. ``on_error`` gets the
  error with ``None`` as the event, and the event is reported
  unhandled.
- ``close()`` called from inside a handler or ``on_error`` cancels
  nothing. The session is closed, the handler or ``on_error`` runs on
  to its end, and the feed then stops without another request. The
  event it was on is neither marked nor reported, so the API sends it
  again once its lease and wait are over. Nothing is logged or put in
  ``client.events_error``.
- After the next ``start()`` the API sends the events that were not
  reported again, once their lease and wait are over.

**Webhooks**

- A bot gets its events on one path. While the bot has a webhook URL,
  its events go to the webhook, and the API answers a 409 on the feed.
  Each event goes to the webhook or to the feed, never to both.
- Saving a webhook URL deletes the events stored in the feed.
- On a 409 for the claim the feed logs one warning and stops. It does
  not raise and does not retry, which is a choice of the library. The
  409 is kept in ``client.events_error``, and ``start()`` starts the
  feed again once the URL is removed.

**Events are kept for 24 hours**

- The API deletes an event 24 hours after it was written, whatever
  became of it: handled, waiting for its next try or dead. A bot that
  was offline for longer gets no notice of it.
- A report for a deleted event is answered with a 404.
- Deleted events leave a gap that the API skips without an error and
  without a marker, so the IDs of a claim are ascending but not always
  consecutive. A bot whose events all expired claims an empty list.
- *discoin.py* does not detect gaps and logs nothing about skipped IDs.
- ``fetch_pending_transactions`` only lists ``Pending`` transactions,
  so a cancellation or reversal that was missed as an event is not in
  it. It is in the list of ``fetch_undone_transactions``, see below.
- *discoin.py* reads neither list by itself. When your bot calls them
  is your choice.

**Without the background feed**

``claim_events`` and ``report_event`` map the two routes of the feed,
for a bot that reads it in its own loop. They do not need ``start()``,
and they raise on every error, a 409 included. ``claim_events`` calls
no handler and marks nothing, and each event it returns is leased
until ``report_event`` is called for it or the lease runs out.

.. code:: py

    events = await client.claim_events(limit=10)

    await client.report_event(events[0].id, True)

The API outlines a pushed stream of the same events for later. It
would use the same event IDs.

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
  no time window and no cursor. An event that was reported handled
  does not clear it, so a cancelled or reversed transaction can reach a
  receiving bot twice, once as an event and once in this list.
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
