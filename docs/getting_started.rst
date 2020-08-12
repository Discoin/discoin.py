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
information to get it up and running. First is your Discoin token
provided by *PizzaFox#0075*. Second information is the 3 digits
character of your currency.

.. code:: py

    from discoin import Client

    client = Client("<TOKEN>", "ABC")

You can also create a new client using a loop
                                             

.. code:: py

    import asyncio
    from discoin import Client

    loop = asyncio.get_event_loop()
    client = Client("<TOKEN>", "ABC", loop=loop)

|

Example
-------

An example cog for discord.py can be found `here <https://git.gami.app/Discoin/discoin.py/src/branch/master/examples/example_cog.py>`_. Just be sure to put your token and currency code at `L11 <https://git.gami.app/Discoin/discoin.py/src/branch/master/examples/example_cog.py#L11>`_, and be sure to add/remove currency at lines `L25 <https://git.gami.app/Discoin/discoin.py/src/branch/master/examples/example_cog.py#L25>`_, `L45 <https://git.gami.app/Discoin/discoin.py/src/branch/master/examples/example_cog.py#L45>`_, `L47 <https://git.gami.app/Discoin/discoin.py/src/branch/master/examples/example_cog.py#L47>`_, and `L57 <https://git.gami.app/Discoin/discoin.py/src/branch/master/examples/example_cog.py#L57>`_