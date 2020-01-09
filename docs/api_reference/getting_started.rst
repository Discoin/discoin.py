Getting Started
===============

Installing *discoin.py*
-----------------------

To start with *discoin.py* you will need to install it via pip/pypi with
the following command

::

    $ pip install discoin.py

Integrating discoin
-------------------

*discoin.py* configuration is the most important part of the process.
You will see and notice, it is really hard! So you will need 2
information to get it up and running. First is your Discoin token
provided by *PizzaFox#0075*. Second information is the 3 digits
character of your currency.

.. code:: py

    from discoin import Discoin

    client = Discoin("Bearer TOKEN", "ABC")

You can also create a new client using a loop
                                             

.. code:: py

    import asyncio
    from discoin import Discoin

    loop = asyncio.get_event_loop()
    client = Discoin("Bearer TOKEN", "ABC", loop=loop)

