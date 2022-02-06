import ccxt
import logging
import os
from core.markets import order
from collections import defaultdict
import core.database.ohlcv_functions as ohlcv
from ccxt import BaseError
import pandas as pd
import core.database.database as db
import core.markets.position as pos
import random

logger = logging.getLogger(__name__)

markets = []


class Coin:
    """An object that allows a specific strategy to interface with an exchange,
    This includes functionality to contain and update TA indicators as well as the latest OHLCV data
    This also handles the API key for authentication, as well as methods to place orders"""

    def __init__(self, exchange, base_currency, quote_currency):
        self.base_currency = base_currency
        self.quote_currency = quote_currency
        self.analysis_pair = '{}/{}'.format(self.base_currency, self.quote_currency)
        self.signals = []
        # temp = pd.DataFrame(exchange.fetch_ohlcv(self.analysis_pair, '5m'))
        # temp.columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
        # l = temp.astype({'Time': 'datetime64[ms]'})          #to_datetime(self.ohlcv['Time'], unit='ms')
        # self.ohlcv = l
        self.exchange = exchange
        self.indicators = defaultdict(list)
        self.candles = defaultdict(list)
        self.latest_candle = defaultdict(list)  # allows for order simulations based on historical ohlcv data
        self.coin_position = db.get_coin_positions(self.analysis_pair)
        self.low = 9999999.0
        self.high = 0.0
        self.current_price = self.coin_position[4]
        self.amount = self.coin_position[3]
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
        self.test = True
        self.testdata = self.current_price

    def get_next_test(self):
        change = round(random.uniform(0, 0.05), 4)
        pos_neg = random.randint(0,1)
        if pos_neg == 0:
            pos_neg = -1
        self.testdata = self.testdata + (self.testdata * (change * pos_neg))
        return self.testdata



    def update(self, interval, candle):
        """Notify all indicators subscribed to the interval of a new candle"""
        self.latest_candle[interval] = candle
        self.candles[interval].append(candle)
        self.do_ta_calculations(interval, candle)

    def do_ta_calculations(self, interval, candle):
        """update TA indicators applied to market"""
        for indicator in self.indicators[interval]:
            indicator.next_calculation(candle)

    def apply_indicator(self, indicator):
        """Add indicator to list of indicators listening to market's candles"""
        self.indicators[indicator.interval].append(indicator)

    def limit_buy(self, quantity, price):
        """Place a limit buy order"""
        try:
            self.strategy.send_message(
                "Executed limit buy of " + str(quantity) + " " + self.base_currency + " for " + str(
                    price) + " " + self.quote_currency)
            return order.Order(self, "buy", "limit", quantity, price)
        except BaseError:
            self.strategy.send_message("Error creating limit buy order")
            logger.error("Error creating limit buy order")

    def market_buy(self, quantity):
        """Place a market buy order"""
        try:
            self.strategy.send_message(
                "Executed market buy of " + str(quantity) + " " + self.base_currency
                     + self.quote_currency)
            return order.Order(self, "buy", "market", quantity, price)
        except BaseError:
            self.strategy.send_message("Error creating market buy order")
            logger.error("Error creating market buy order")

    def limit_sell(self, quantity, price):
        """Place a limit sell order"""
        try:
            self.strategy.send_message(
                "Executed limit sell of " + str(quantity) + " " + self.base_currency + " for " + str(
                    price) + " " + self.quote_currency)
            return order.Order(self, "sell", "limit", quantity, price)
        except BaseError:
            self.strategy.send_message("Error creating limit sell order")
            logger.error("Error creating limit sell order")

    def market_sell(self, analysis_pair, quantity):
        """Place a market sell order"""
        try:
            self.strategy.send_message(
                "Executed market sell of " + str(quantity) + " " + self.base_currency +
                     " " + self.quote_currency)
            return order.Order(self, "sell", "market", quantity)
        except BaseError:
            self.strategy.send_message("Error creating market sell order")
            logger.error("Error creating market sell order")

    def get_wallet_balance(self):
        """Get wallet balance for quote currency"""
        try:
            logger.info(self.exchange.fetch_balance())
            return self.exchange.fetch_balance()
        except BaseError:
            logger.error("Not logged in properly")

    def get_best_bid(self):
        orderbook = self.exchange.fetch_order_book(self.analysis_pair)
        return orderbook['bids'][0][0] if len(orderbook['bids']) > 0 else None

    def get_best_ask(self):
        orderbook = self.exchange.fetch_order_book(self.analysis_pair)
        return orderbook['asks'][0][0] if len(orderbook['asks']) > 0 else None

    def get_spread(self):
        ask = self.get_best_ask()
        bid = self.get_best_bid()
        spread = round(((ask - bid) / ask) * 100, 2)
        return spread

    def get_historical_candles(self, interval, candle_limit=None):
        if len(self.candles[interval]) == 0:
            self.candles[interval] = ohlcv.get_historical_candles()
        if candle_limit is None:
            return self.candles[interval]
        else:
            return self.candles[interval][-candle_limit:]

    def sync_historical(self):
        """Load all missing historical candles to database"""
        logger.info('Syncing market candles with DB...')
        latest_db_candle = ohlcv.get_latest_candle(1, self.analysis_pair, self.interval)
        data = self.exchange.fetch_ohlcv(self.analysis_pair, self.interval)
        if latest_db_candle is None:
            logger.info("No historical data for market, adding all available OHLCV data")
            for entry in data:
                ohlcv.insert_data_into_ohlcv_table(1, self.analysis_pair, self.interval, entry, self.PairID)
                print('Writing candle ' + str(entry[0]) + ' to database')
        else:
            for entry in data:
                if not latest_db_candle[10] >= entry[0]:
                    ohlcv.insert_data_into_ohlcv_table(1, self.analysis_pair, self.interval, entry, self.PairID)
                    logger.warning('Writing missing candle ' + str(entry[0]) + ' to database')
        self.historical_synced = True
        logger.warning('Market data has been synced: ' + str(self.topic) + " + " + "historical")

    def check_action(self):
        if self.position:               # we are going to sell
            if self.test:
                bid = self.get_next_test()
            else:
                bid = self.get_best_bid()
            if bid > self.high:
                self.high = bid
                self.sell_drempel = self.current_price * (1 + self.gain)
                self.trail_stop_sell_drempel = self.high * (1 - self.trail)
                print(db.get_timestamp())
                #print(f"Pair: {self.analysis_pair}, HIGH: {self.high}, DREMPEL: {self.trail_stop_sell_drempel}")
                print(f"SELL-PRICE UP: {self.analysis_pair}, HIGH: {self.high}, Trail_stop_sell_DREMPEL: {self.trail_stop_sell_drempel}")
                if  self.high >= self.sell_drempel:
                    self.sell_signal = True
                    #print(db.get_timestamp())
                    #print(f"SELL-SIGNAL: {self.analysis_pair}")
            elif self.sell_signal:
                if bid <=  self.trail_stop_sell_drempel:
                    #print(f"BuyPrice: {self.current_price}, SellPrice: {bid}, TrailStopsellDrempel: {self.trail_stop_sell_drempel}, High: {self.high}")
                    self.sell_signal = False
                    self.position = False
                    self.current_price = bid
                    self.low = self.current_price
                    print(db.get_timestamp())
                    self.market_sell(self.analysis_pair, self.amount)
                    print(f"SELL-ACTION Price: {self.current_price}, bitvavo.create_market_sell_order({self.analysis_pair}, {self.amount}, Price: {self.current_price}")
                    #order.create_market_sell_order(self.analysis_pair, self.amount)
                    pos.write_order_to_db(self.analysis_pair, 'bid', self.amount, self.current_price, )

            self.stop_loss_buy = self.current_price * (1 - self.stoploss)
            if bid < self.stop_loss_buy:
                print(db.get_timestamp())
                #print(f"StopLoss Sell: {bid}, StopLossBuy: {self.stop_loss_buy}, BuyPRice: {self.current_price}")
                print(f"stoploss Buy: bitvavo.create_market_buy_order({self.analysis_pair}, {self.amount}) Bid = {bid}, Stop_Loss: {self.stop_loss_buy}")
        else:                           # we are going to buy
            if self.test:
                ask = self.get_next_test()
            else:
                ask = self.get_best_ask()
            if ask < self.low:
                self.low = ask
                self.buy_drempel = self.current_price * (1 - self.gain)
                self.trail_stop_buy_drempel = self.low * (1 + self.trail)
                print(db.get_timestamp())
                print(f"BUY-PRICE DOWN: {self.analysis_pair}, LOW: {self.low}, Trail_stop_Buy_DREMPEL: {self.trail_stop_buy_drempel}")
                if self.low < self.buy_drempel:
                    self.buy_signal = True
                    print(db.get_timestamp())
                    print(f"BUY-SIGNAL: {self.analysis_pair}")
            elif self.buy_signal:
                if self.trail_stop_buy_drempel <= ask:
                    self.buy_signal = False
                    self.position = True
                    self.current_price = ask
                    self.high = self. current_price
                    print(db.get_timestamp())
                    #order.create_market_buy_order(self.analysis_pair, self.amount)
                    self.market_buy(self.analysis_pair, self.amount)
                    print(f" BUY: bitvavo.create_market_buy_order({self.analysis_pair}, {self.amount}, Price: {self.current_price}")
                    pos.write_order_to_db(self.analysis_pair, 'ask', self.amount, self.current_price)
            self.stop_loss_sell = self.current_price * (1 + self.stoploss)
            if ask > self.stop_loss_sell:
                #print(f"Stoploss Buy: {ask}, StoplossSell: {self.stop_loss_sell}, SellPrice: {self.current_price}")
                print(f"stoploss Sell: bitvavo.create_market_sell_order({self.analysis_pair}, {self.amount}) Ask = {ask}, Stop_Loss: {self.stop_loss_sell}")

if __name__ == '__main__':
    pass