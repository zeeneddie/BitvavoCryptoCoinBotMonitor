import datetime
import time
import logging
import os
from collections import defaultdict

from core.database.database import Database
import random

logger = logging.getLogger(__name__)

markets = []


class Coin:
    """An object that allows a specific strategy to interface with an exchange,
    This includes functionality to contain and update TA indicators as well as the latest OHLCV data
    This also handles the API key for authentication, as well as methods to place orders"""

    def __init__(self, bitvavo_client, coin_info):
        self.base_currency = coin_info[0] #base_currency
        self.quote_currency = coin_info[1] #quote_currency
        self.base_currency = self.base_currency.strip()
        self.quote_currency = self.quote_currency.strip()
        self.analysis_pair = '{}-{}'.format(self.base_currency, self.quote_currency)
        self.signals = []
        self.bitvavo = bitvavo_client.bitvavo
        self.indicators = defaultdict(list)
        self.candles = defaultdict(list)
        self.latest_candle = defaultdict(list)  # allows for order simulations based on historical ohlcv data
        self.low = 9999999.0
        self.high = 0.0
        self.current_price = float(coin_info[4])
        self.amount = float(coin_info[3])
        self.var_sell = dict()
        self.var_buy = dict()
        self.var_sell['amountQuote'] = str(self.amount)
        self.var_buy['amountQuote'] = str(self.amount)
        self.gain = float(coin_info[5])
        self.trail = float(coin_info[6])
        self.stoploss= float(coin_info[7])
        self.buy_drempel = 0.0
        self.sell_drempel = 0.0
        self.buy_signal = False
        self.sell_signal = False
        self.stop_loss_buy = 0
        self.stop_loss_sell = 0
        self.trail_stop_buy_drempel = 0.0
        self.trail_stop_sell_drempel = 0.0
        self.ask = 0
        self.bid = 0
        coin_positie = coin_info[2].strip()
        if coin_positie == 'Y':
            self.position = True
        else:
            self.position = False
        self.test = False
        self.testdata = self.current_price

    def get_next_test(self):
        change = round(random.uniform(0, 0.05), 4)
        pos_neg = random.randint(0,1)
        if pos_neg == 0:
            pos_neg = -1
        self.testdata = self.testdata + (self.testdata * (change * pos_neg))
        return self.testdata



    def get_best_bid(self):
        best = self.bitvavo.book(self.analysis_pair, {'depth': '1'})
        if 'error' in best.keys():
            while 'error' in best.keys():
                print(best['error'])
                best = self.bitvavo.book(self.analysis_pair, {'depth': '1'})
        return best['bids'][0][0]

    def get_best_ask(self):
        best = self.bitvavo.book(self.analysis_pair, {'depth': '1'})
        if 'error' in best.keys():
            while 'error' in best.keys():
                print(best['error'])
                best = self.bitvavo.book(self.analysis_pair, {'depth': '1'})
        return best['asks'][0][0]

    def get_best(self):
        best = self.bitvavo.book(self.analysis_pair, {'depth': '1'})
        if 'error' in best.keys():
            while 'error' in best.keys():
                print(best['error'])
                best = self.bitvavo.book(self.analysis_pair, {'depth': '1'})
        return best['asks'][0][0], best['bid'][0][0]

    def get_spread(self):
        ask = self.get_best_ask()
        bid = self.get_best_bid()
        spread = round(((ask - bid) / ask) * 100, 2)
        return spread

    def get_position(self):
        return self.position

    def check_action(self):
        if self.position:               # we are going to sell
            bid = float(self.get_best_bid())
            self.bid = bid
                #print(self.analysis_pair)
            if bid > self.high:
                self.high = bid
                self.sell_drempel = self.current_price * (1 + self.gain)
                self.trail_stop_sell_drempel = self.high * (1 - self.trail)
                if  self.high >= self.sell_drempel:
                    self.sell_signal = True
                    print(get_timestamp())
                    print(f"SELL-SIGNAL: {self.analysis_pair}, {bid}")
            elif self.sell_signal:
                if bid <=  self.trail_stop_sell_drempel:
                    result = self.bitvavo.placeOrder(self.analysis_pair, 'sell', 'market', self.var_sell)
                    print(get_timestamp())
                    print(result)
                    self.sell_signal = False
                    self.position = False
                    self.current_price = bid
                    self.low = self.current_price

            self.stop_loss_buy = self.current_price * (1 - self.stoploss)
            if bid < self.stop_loss_buy:
                pass
        else:                           # we are going to buy
            ask = float(self.get_best_ask())
            self.ask = ask
                #print(self.analysis_pair)
            if ask < self.low:
                self.low = ask
                self.buy_drempel = self.current_price * (1 - self.gain)
                self.trail_stop_buy_drempel = self.low * (1 + self.trail)
                if self.low < self.buy_drempel:
                    self.buy_signal = True
                    print(get_timestamp())
                    print(f"BUY-SIGNAL: {self.analysis_pair}, {ask}")
            elif self.buy_signal:
                if self.trail_stop_buy_drempel <= ask:
                    self.buy_signal = False
                    self.position = True
                    self.current_price = ask
                    self.high = self. current_price
                    r = self.bitvavo.placeOrder(self.analysis_pair, 'buy', 'market', self.var_buy)
                    print(r)
            self.stop_loss_sell = self.current_price * (1 + self.stoploss)
            if ask > self.stop_loss_sell:
                pass

def get_timestamp():
    return datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')

if __name__ == '__main__':
    pass