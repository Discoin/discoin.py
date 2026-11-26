# Discoin for Python

This is the official discoin library for python. Here is discoin's [API documentation](https://discoin.dev/api/docs)

## Requirements
* Python 3.6 or up
* aiohttp

## Installation
```bash
$ pip install discoin
```

Documentation can be found [here](https://discoinpy.readthedocs.io)

## Events and undone transactions
`Client.start()` reads your bot's event feed in the background and calls the handler methods of your `Client` subclass, such as `on_transaction_created`. `Client.fetch_undone_transactions()` lists the refunded, cancelled and reversed transactions your bot has not marked handled, and `Client.mark_handled()` marks one. Both are described in the [getting started guide](https://discoinpy.readthedocs.io/en/latest/getting_started.html).

## Credits
* [Dr_Ari_Gami](https://github.com/Dr-Ari-Gami/) (Main Developer)
* [DeveloperAnonymous](https://github.com/DeveloperAnonymous) (Collaborator)
* [Theelgirl](https://github.com/Theelgirl) (Collaborator)
* [Jonah Snider](https://github.com/jonahsnider) (Main developer of Discoin)
* [Austin Huang](https://github.com/austinhuang0131) (Owner of Discoin)
