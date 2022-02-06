from core.markets import market_watcher
from core.markets import market_simulator
from core.markets import market
from core.markets import position
from threading import Thread
from queue import Queue
import logging

logger = logging.getLogger(__name__)

class Strategy:

    def __init__(self, base_currency, quote_currency):
        self.running = False
        self.positions = []
        self.name = None
        self.order_quantity = 5
        self.position_limit = 1
        self.buy_signal = False
        self.buy_target_percent = 3 # 3% stijging leidt tot verkoop signaal - als trailing stoploss overschreden wordt gaan we echt verkopen
        self.sell_target_percent = 3 # 3% daling leidt tot koop - als trailing stoploss overschreden wordt gaan we echt kopen
        self.fixed_stoploss_percent = 10 # 10% daling van gekochte prijs leidt tot verkoop - stop the bleeding
        self.trailing_stoploss_percent = 1 # 1% speling voor de daadwerklijke koop / verkoop plaats vindt

    def warmup(self):
        pass

    def update(self, candle):
        """Run updates on all markets/indicators/signal generators running in strategy"""
        logger.info("Received new candle")
        self.market.update(self.interval, candle)
        self.update_positions()
        self.on_data(candle)
        logger.info("Simulation balance: " + str(self.market.get_wallet_balance()))


    def on_data(self, candle):
        """Will be called on each candle, this method is to be overriden by inheriting classes"""
        buy_condition = self.buy_signal.check_condition(candle)
        if self.get_open_position_count() >= self.position_limit:
            pass
        elif buy_condition:
            self.long(self.order_quantity, self.fixed_stoploss_percent, self.trailing_stoploss_percent,
                      self.profit_target_percent)

    def get_open_position_count(self):
        """Check how many positions this strategy has open"""
        count = len([p for p in self.positions if p.is_open])
        logger.info(str(count) + " long positions open")
        return count

    def update_positions(self):
        """Loop through all positions opened by the strategy"""
        for p in self.positions:
            if p.is_open:
                p.update()

    def long(self, order_quantity, fixed_stoploss_percent, trailing_stoploss_percent, profit_target_percent):
        """Open long position"""
        if self.is_simulated:
            """Open simulated long position"""
            logger.info("Going long on " + self.market.analysis_pair)
            logger.info("Simulation balance: " + str(self.market.get_wallet_balance()))

            self.positions.append(market_simulator.open_long_position_simulation(self.market, order_quantity,
                                                                                 self.market.latest_candle[
                                                                                     self.interval][3],
                                                                                 fixed_stoploss_percent,
                                                                                 trailing_stoploss_percent,
                                                                                 profit_target_percent))
        else:
            """LIVE long position"""
            logger.warning("Going long on " + self.market.analysis_pair)
            self.positions.append(position.open_long_position(self.market, order_quantity,
                                                          self.market.get_best_ask(),
                                                          fixed_stoploss_percent,
                                                          trailing_stoploss_percent,
                                                          profit_target_percent))

    def print_message(self, msg):
        """Add to a queue of messages that can be consumed by the UI"""
        logger.info(str("Strategy " + str(self.strategy_id) + ": " + msg))
        logger.info(msg)

