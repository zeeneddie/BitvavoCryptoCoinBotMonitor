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

    def __init__(self, db, bitvavo_client, base_currency, quote_currency):
        self.base_currency = base_currency
        self.quote_currency = quote_currency
        self.analysis_pair = '{}-{}'.format(self.base_currency, self.quote_currency)
        self.signals = []
        # temp = pd.DataFrame(exchange.fetch_ohlcv(self.analysis_pair, '5m'))
        # temp.columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
        # l = temp.astype({'Time': 'datetime64[ms]'})          #to_datetime(self.ohlcv['Time'], unit='ms')
        # self.ohlcv = l
        self.bitvavo = bitvavo_client.bitvavo
        self.indicators = defaultdict(list)
        self.candles = defaultdict(list)
        self.latest_candle = defaultdict(list)  # allows for order simulations based on historical ohlcv data
        self.coin_position = db.get_coin_positions(self.analysis_pair)
        self.low = 9999999.0
        self.high = 0.0
        self.current_price = self.coin_position[4]
        self.amount = self.coin_position[3]
        self.var_sell = dict()
        self.var_buy = dict()
        #self.var['amountQuote'] = str(self.amount)
        # 'amountQuote' in sell = EURO - amount = crypto currency amount
        # 'amount' in buy = EURO
        self.var_sell['amountQuote'] = str(self.amount)
        self.var_buy['amountQuote'] = str(self.amount)
        self.gain = self.coin_position[5]
        self.trail = self.coin_position[6]
        self.stoploss= self.coin_position[7]
        self.buy_drempel = 0.0
        self.sell_drempel = 0.0
        self.buy_signal = False
        self.sell_signal = False
        self.stop_loss_buy = 0
        self.stop_loss_sell = 0
        self.trail_stop_buy_drempel = 0.0
        self.trail_stop_sell_drempel = 0.0
        if self.coin_position[2] == 'Y':
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
        return best['bids'][0][0]

    def get_best_ask(self):
        best = self.bitvavo.book(self.analysis_pair, {'depth': '1'})
        return best['asks'][0][0]

    def get_spread(self):
        ask = self.get_best_ask()
        bid = self.get_best_bid()
        spread = round(((ask - bid) / ask) * 100, 2)
        return spread



    def check_action(self, db):
        if self.position:               # we are going to sell
            if self.test:
                bid = float(self.get_next_test())
            else:
                bid = float(self.get_best_bid())

            if bid > self.high:
                self.high = bid
                self.sell_drempel = self.current_price * (1 + self.gain)
                self.trail_stop_sell_drempel = self.high * (1 - self.trail)
                print(get_timestamp())
                #print(f"Pair: {self.analysis_pair}, HIGH: {self.high}, DREMPEL: {self.trail_stop_sell_drempel}")
                print(f"SELL-PRICE UP: {self.analysis_pair}, HIGH: {self.high}, Trail_stop_sell_DREMPEL: "
                      f"{self.trail_stop_sell_drempel} = {round((bid/self.current_price)*100, 2)}")
                if  self.high >= self.sell_drempel:
                    self.sell_signal = True
                    print(f"SELL-SIGNAL: {self.analysis_pair}")
            elif self.sell_signal:
                if bid <=  self.trail_stop_sell_drempel:
                    print(get_timestamp())
                    result = self.bitvavo.placeOrder(self.analysis_pair, 'sell', 'market', self.var_sell)
                    print(result)
                    #print(f"PLACEORDER Price: {self.current_price}, bitvavo.placeOrder({self.analysis_pair}, "
                    # #     f"'sell', 'market', {'amount': {str(self.var_sell)}} "
                    #      f", Price: {bid} = {round((self.sell_drempel/self.current_price)*100, 2)})")
                    #order.create_market_sell_order(self.analysis_pair, self.amount)
                    db.write_order(self.analysis_pair, 'bid', self.amount, bid)
                    #db.update_position(self, result)
                    self.sell_signal = False
                    self.position = False
                    self.current_price = bid
                    self.low = self.current_price

            self.stop_loss_buy = self.current_price * (1 - self.stoploss)
            if bid < self.stop_loss_buy:
                print(get_timestamp())
                #print(f"StopLoss Sell: {bid}, StopLossBuy: {self.stop_loss_buy}, BuyPRice: {self.current_price}")
                print(f"stoploss Buy: bitvavo.create_market_buy_order({self.analysis_pair}, {self.amount}) Bid = {bid}, Stop_Loss: {self.stop_loss_buy}")
        else:                           # we are going to buy
            if self.test:
                ask = float(self.get_next_test())
            else:
                ask = float(self.get_best_ask())
                # print(get_timestamp())
                # r = self.bitvavo.placeOrder(self.analysis_pair, 'buy', 'market', self.var_buy)
                # print(r)
                # print(f" BUY: PLACEORDER({self.analysis_pair}, {self.var_buy}, Price: {self.current_price})")
                # exit()
            if ask < self.low:
                self.low = ask
                self.buy_drempel = self.current_price * (1 - self.gain)
                self.trail_stop_buy_drempel = self.low * (1 + self.trail)
                print(get_timestamp())
                print(f"BUY-PRICE DOWN: {self.analysis_pair}, LOW: {self.low}, Trail_stop_Buy_DREMPEL: "
                      f"{self.trail_stop_buy_drempel} = {round((ask/self.buy_drempel)*100, 2)}")
                if self.low < self.buy_drempel:
                    self.buy_signal = True
                    print(get_timestamp())
                    print(f"BUY-SIGNAL: {self.analysis_pair}")
            elif self.buy_signal:
                if self.trail_stop_buy_drempel <= ask:
                    self.buy_signal = False
                    self.position = True
                    self.current_price = ask
                    self.high = self. current_price
                    print(get_timestamp())
                    r = self.bitvavo.placeOrder(self.analysis_pair, 'buy', 'market', self.var_buy)
                    print(r)
                    print(f" BUY: PLACEORDER({self.analysis_pair}, {self.var_buy}, Price: {self.current_price})")
                    db.write_order(self.analysis_pair, 'ask', self.amount, self.current_price)

            self.stop_loss_sell = self.current_price * (1 + self.stoploss)
            if ask > self.stop_loss_sell:
                #print(f"Stoploss Buy: {ask}, StoplossSell: {self.stop_loss_sell}, SellPrice: {self.current_price}")
                print(f"stoploss Sell: bitvavo.create_market_sell_order({self.analysis_pair}, {self.amount}) Ask = {ask}, Stop_Loss: {self.stop_loss_sell}")

def get_timestamp():
    return datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')

if __name__ == '__main__':
    pass