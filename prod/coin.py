import datetime
import time
import logging
import os
from collections import defaultdict

#from core.database.database import Database
import random

logger = logging.getLogger(__name__)

markets = []

def time_ms() -> int:
    return int(time.time() * 1000)


class Coin:
    """An object that allows a specific strategy to interface with an exchange,
    This includes functionality to contain and update TA indicators as well as the latest OHLCV data
    This also handles the API key for authentication, as well as methods to place orders"""

    def __init__(self, bitvavo_client, coin_info):
        self.index = coin_info[0]
        self.base_currency = coin_info[1] #base_currency
        self.quote_currency = coin_info[2] #quote_currency
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
        self.current_price = float(coin_info[5])
        self.amount = float(coin_info[4])
        self.var_sell = dict()
        self.var_buy = dict()
        self.var_sell['amountQuote'] = str(self.amount)
        self.var_buy['amountQuote'] = str(self.amount)
        self.gain = float(coin_info[6])
        self.trail = float(coin_info[7])
        self.stoploss= float(coin_info[8])
        self.temp_high = float(coin_info[9])
        self.high = self.temp_high
        self.temp_low = float(coin_info[10])
        self.low = self.temp_low
        self.number_deals = int(coin_info[11])
        self.last_update = str(coin_info[12])
        self.sleep_till = int(coin_info[13])
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
        coin_positie = coin_info[3].strip()
        if coin_positie == 'Y':
            self.position = True
            self.sell_drempel = self.current_price * (1 + self.gain)
            if self.temp_high >= self.sell_drempel:
                self.sell_signal = True
                print(get_timestamp())
                print(f"START SELL-SIGNAL: {self.analysis_pair}, {self.temp_high} >= {self.sell_drempel}")
            else:
                self.sell_signal = False
                print(f"GEEN START SELL-SIGNAL: {self.analysis_pair}, {self.temp_high} < {self.sell_drempel}")
        else:
            self.position = False
            self.buy_drempel = self.current_price * (1 - self.gain)
            if self.temp_low < self.buy_drempel:
                self.buy_signal = True
                self.trail_stop_buy_drempel = self.low * (1 + self.trail)
                print(get_timestamp())
                print(f"BUY-SIGNAL: {self.analysis_pair}, tijdelijk: {self.temp_low} < {self.buy_drempel}")
            else:
                self.buy_signal = False
                print(f"GEEN BUY-SIGNAL: {self.analysis_pair}, tijdelijk: {self.temp_low} >= {self.buy_drempel}")
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

    def get_temp_high(self):
        return self.temp_high

    def get_temp_low(self):
        return self.temp_low

    def check_action(self):
        if self.position:               # we are going to sell
            bid = float(self.get_best_bid())
            self.bid = bid
                #print(self.analysis_pair)
            if bid > self.high:
                self.high = bid
                self.sell_drempel = self.current_price * (1 + self.gain)
                self.trail_stop_sell_drempel = self.high * (1 - self.trail)
                self.temp_high = self.high
                if  self.high >= self.sell_drempel:
                    self.sell_signal = True
                    print(get_timestamp())
                    print(f"SELL-SIGNAL: {self.analysis_pair}, {bid}")
            elif self.sell_signal:
                if bid <=  self.trail_stop_sell_drempel:
                    result = self.bitvavo.placeOrder(self.analysis_pair, 'sell', 'market', self.var_sell)
                    if 'errorCode' in result.keys():
                        print(get_timestamp())
                        print(result)
                        print("Next cycle new try")
                    else:
                        print(get_timestamp())
                        print(result)
                        self.sell_signal = False
                        self.position = False
                        #self.current_price = bid
                        self.low = self.current_price
                        self.temp_low = self.low
                        self.last_update = get_timestamp()
                        self.number_deals = int(self.number_deals) + 1

            self.stop_loss_buy = self.current_price * (1 - self.stoploss)
            if bid < self.stop_loss_buy:
                pass
                #print("STOP LOSS: ", get_timestamp())
                #print(self.analysis_pair, " bid", bid, " stop loss: ", self.stop_loss_buy);
                #result = self.bitvavo.placeOrder(self.analysis_pair, 'sell', 'market', self.var_sell)
                #self.position = False
                #self.current_price = self.current_price * 0.85
                #self.last_update = get_timestamp()
                #self.sleep_till = time_ms() + 86400000  # dag in millisecondenh

                #print(get_timestamp())
                #print(result)
        else:                           # we are going to buy
            ask = float(self.get_best_ask())
            self.ask = ask
                #print(self.analysis_pair)
            if ask < self.low:
                self.low = ask
                self.buy_drempel = self.current_price * (1 - self.gain)
                self.temp_low = self.low
                if self.low < self.buy_drempel:
                    self.buy_signal = True
                    self.trail_stop_buy_drempel = self.low * (1 + self.trail)
                    print(get_timestamp())
                    print(f"BUY-SIGNAL: {self.analysis_pair}, {ask}")
                    print(f"Current: {self.current_price} Drempel: {self.buy_drempel}")
            elif self.buy_signal:
                if self.trail_stop_buy_drempel <= ask:

                    result = self.bitvavo.placeOrder(self.analysis_pair, 'buy', 'market', self.var_buy)

                    if 'errorCode' in result.keys():
                        print(get_timestamp())
                        print(result)
                        print("Next cycle new try")
                    else:
                        print(get_timestamp())
                        print(result)
                        self.buy_signal = False
                        self.position = True
                        #self.current_price = ask
                        self.high = self. current_price
                        self.temp_high = self.high
                        self.last_update = get_timestamp()
                        self.number_deals = int(self.number_deals) + 1


            self.stop_loss_sell = self.current_price * (1 + self.stoploss)
            if ask > self.stop_loss_sell:
                #print("RESET Bottom Price / Current_price: ", get_timestamp())
                #print(self.analysis_pair, " " , self.current_price, " ", ask, " ", self.stop_loss_sell)
                #self.current_price = self.current_price + (self.current_price * (self.stoploss-0.035))
                #print(self.analysis_pair , " " , self.current_price, " ", self.stoploss, " " , (self.stoploss - 0.02))
                #self.position = False
                pass


def get_timestamp():
    return datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')

if __name__ == '__main__':
    pass