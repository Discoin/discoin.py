import datetime

class Transaction():
    '''
    `id` = The ID or receipt of the transaction (`str`)
    `currency_from` = The currency object that the transaction is coming from (`Currency`)
    `currency_to` = The currency object that the transaction is going to (`Currency`)
    `amount` = The original amount of the transaction (`float`)
    `user_id` = the id of the user who requested the transaction (`int`)
    `handled` = if the transaction has been marked as proccessed (`bool`)
    `timestamp` = The timestamp for when the transaction took place (`datetime.datetime`)
    `payout` = The amount calculated to its final destination (`float`)
    '''

    def __init__(self, transaction_obj):
        self.id = transaction_obj['id']
        self.currency_from = Currency(transaction_obj['from'])
        self.currency_to = Currency(transaction_obj['to'])
        self.amount = float(transaction_obj['amount']) # This is the amount from the original source
        self.user_id = int(transaction_obj['user'])
        self.handled = transaction_obj['handled']
        self.timestamp = datetime.datetime.strptime(transaction_obj['timestamp'], "%Y-%m-%dT%H:%M:%S.%fZ")
        self.payout = float(transaction_obj['payout']) # This is the amount calculated to its final destination

    def __str__(self):
        return f"Transaction({self.id})"


class Currency():
    '''
    id = the 3 letter id of the currency
    name = the provided name of the currency
    value = the value the currency has
    reserve = the amount of currency trade left
    '''
    def __init__(self, currency_obj):
        self.id = currency_obj['id']
        self.name = currency_obj['name']
        self.value = currency_obj.get('value')
        self.reserve = currency_obj.get('reserve')

    def __str__(self):
        return f"Currency({self.id})"


class Bot():
    '''
    id = The id of the bot. Can contain letters (`string`)
    currency = the currency of the bot (`Currency`)
    '''
    def __init__(self, bot_obj):
        self.id = bot_obj['id']
        self.currency = Currency(bot_obj['currency'])

    def __str__(self):
        return f"Bot({self.id})"