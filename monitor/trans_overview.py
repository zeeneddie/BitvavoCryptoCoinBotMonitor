import logging
import os
from python_bitvavo_api.bitvavo import Bitvavo
import datetime

logger = logging.getLogger(__name__)
APIKEY = os.environ.get('BITVAVOAPIKEY')
APISECRET = os.environ.get('BITVAVOSECKEY')

bitvavo = Bitvavo({
    'APIKEY': APIKEY,
    'APISECRET': APISECRET  # ,
    # 'RESTURL': 'https://api.bitvavo.com/v2',
    # 'WSURL': 'wss://ws.bitvavo.com/v2/',
    # 'ACCESSWINDOW': 10000,
    # 'DEBUGGING': False
})

response = bitvavo.balance({})
for item in response:
    #print(f"{item['symbol']}  \t{item['available']}")
    if item['symbol'] != "EUR":
        tradepair = item['symbol']+"-EUR"
        response = bitvavo.trades(tradepair, {})
        count = 1;
        sum = 0;
        for item in response:

            #print(item)
            #dt = datetime.datetime.fromtimestamp(item['timestamp'] / 1000.0, tz=datetime.timezone.utc).strftime('%d-%m-%Y %H:%M:%S')
            dt = datetime.datetime.fromtimestamp(item['timestamp'] / 1000.0, tz=datetime.timezone.utc).strftime('%Y%m')
            if (int(dt) > 202203):
                sum = float(item['amount']) * float(item['price'])
                if item['side'] == 'sell':
                    sum = -1 * sum
                #print(f"{count}, {dt}, {item['market']}, {item['side']}, {item['amount']}, {item['price']}, {item['fee']}")
                count = count + 1
        print(f"TOTAL voor {item['market']}: aantal {count} = som {sum}")