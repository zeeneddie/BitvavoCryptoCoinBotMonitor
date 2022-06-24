from python_bitvavo_api.bitvavo import Bitvavo
import os

class Bitvavo_client():
    def __init__(self):
        APIKEY=os.environ.get('BITVAVOAPIKEY')
        APISECRET = os.environ.get('BITVAVOSECKEY')
        self.bitvavo = Bitvavo({
          'APIKEY': APIKEY,
          'APISECRET': APISECRET#,
          # 'RESTURL': 'https://api.bitvavo.com/v2',
          # 'WSURL': 'wss://ws.bitvavo.com/v2/',
          # 'ACCESSWINDOW': 10000,
          # 'DEBUGGING': False
        })


if __name__ == "__main__":
    bitvavo = Bitvavo_client()
    response = bitvavo.bitvavo.book('BTC-EUR', {'depth':'1'})
    for item in response['bids']:
        print('Bids', item)
    for item in response['asks']:
        print('Asks', item)
    result = bitvavo.bitvavo.placeOrder("BTC-EUR", 'sell', 'market', {'amountQuote':'2'})
    print(result)