import datetime
import time
import logging
import os
from collections import defaultdict

logger = logging.getLogger(__name__)

markets = []


class Coinlist:

    def __init__(self, coin_info):
        self.coins = []

        self.base_currency = coin_info[1]
        self.base_currency = self.base_currency.strip()
        self.ask = 0
        self.bid = 0

    def Coin_exist(self, coin_info):
        pass

    def get_book(self):
        best = self.bitvavo.book(self.analysis_pair, {'depth': '1'})
        if 'error' in best.keys():
            while 'error' in best.keys():
                print(best['error'])
                best = self.bitvavo.book(self.analysis_pair, {'depth': '1'})
        return best['bids'][0][0]

def get_timestamp():
    return datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')

if __name__ == '__main__':
    pass