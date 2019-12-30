import aiohttp
import asyncio

from .classes import Transaction, Currency, Bot
from .utils import api_request


class Discoin():
    '''
    Main used class for discoin
    
    *`token` = Your api token for discoin (`string`)
    *`me` = Your 3 letter currency code (`string`)
    `loop` = Optional asyncio event loop
    '''

    def __init__(self, token: str, me: str, loop=None):
        # Needed vars
        self._headers = {"Authorization": f"Bearer {token}"}
        self._me = me

        # Event loop Init
        self._loop = loop or asyncio.get_event_loop()

        # aiohttp Session Init
        self._session = aiohttp.ClientSession(loop=self._loop)

    async def fetch_transactions(self, **kwargs):
        '''
        Get a list of transactions. It is recommended to run this every 5 minutes in a loop

        `code` = 3 letter currency code that you want to search for. `None` will just fetch all results. Default is `me`. (`string`)
        `handled` = Defaults to `False`. Will filter results to see if they are handled or not. `None` will fetch all ('bool')
        `advanced_filter` = Optionally, you can create your own filter. Not recommended (`string`)
        '''
        code = kwargs.pop("code", self._me)
        handled = kwargs.pop("handled", False)
        advanced_filter = kwargs.pop("advanced_filter", None)

        if advanced_filter:
            transaction_filter = advanced_filter
        else:
            transaction_filter = f"""{f"filter=to.id||eq||{code}&" if code else None}{f"filter=handled||eq||{handled}&" if handled != None else None}"""
        url_path = f"/transactions?{transaction_filter}"

        api_response = await api_request(self._session, "GET", url_path)
        api_response_json = await api_response.json()
        transactions = []

        for transaction_obj in api_response_json:
            transactions.append(Transaction(transaction_obj))
        
        return transactions

    async def create_transaction(self, code_to: str, amount: float, user_id: int):
        '''
        Create a transaction

        *`code_to` = The 3 letter code to send a transaction to. ('str')
        *`amount` = The amount of currency in original format. (`float`)
        '''

        code_to = code_to.upper()
        json = {
            "amount": amount,
            "toId": code_to,
            "user": str(user_id),
        }

        api_response = await api_request(self._session, "POST", "/transactions", headers=self._headers, json=json)
        api_response_json = await api_response.json()

        return Transaction(api_response_json)

    async def handle_transaction(self, transaction_id, handled: bool=True):
        '''
        Handling a transaction just marks it as handled, or processed.

        *`id` = the id of the transaction you want to handle
        `handled` = Defaults to `True`. If you want to mark a transaction as unhandled, then set this to `False`
        '''

        json = {
            "handled": handled,
        }

        api_response = await api_request(self._session, "PATCH", f"/transactions/{transaction_id}", headers=self._headers, json=json)
        api_response_json = await api_response.json()

        return Transaction(api_response_json)

    async def fetch_currencies(self):
        '''
        This allows you to fetch the available currencies from the API
        '''

        api_response = await api_request(self._session, "GET", f"/currencies")
        api_response_json = await api_response.json()
        currencies = []

        for currency_obj in api_response_json:
            currencies.append(Currency(currency_obj))
        
        return currencies
    
    async def fetch_bots(self):
        '''
        Fetch a list of bots compatible with discoin.
        '''

        api_response = await api_request(self._session, "GET", f"/bots")
        api_response_json = await api_response.json()
        bots = []

        for bot_obj in api_response_json:
            bots.append(Bot(bot_obj))
        
        return bots