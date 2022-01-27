from ta import simple_moving_average
from ta import volume_change_monitor
from signal_generators.base_signal_generator import BaseSignalGenerator
import logging

logger = logging.getLogger(__name__)

class SmaCrossoverSignal(BaseSignalGenerator):
    """"This signal generator represents a simple sma crossover algorithm
    For each new candle the fma and sma will be compared
    When the fma crosses the sma, the high of the candle is cached
    When the price passes that cached high, the signal will return True then go back to waiting for another crossover
    If the fma goes back below sma the cached high is forgotten and the strategy waits for another crossover"""
    def __init__(self, market, interval, sma_short, sma_long, strategy):
        super().__init__(market, interval, strategy)
        self.fma = simple_moving_average.SimpleMovingAverage(self.market, interval, sma_short)
        self.sma = simple_moving_average.SimpleMovingAverage(self.market, interval, sma_long)
        self.vol_change = volume_change_monitor.VolumeChangeMonitor(self.market, interval)
        self.cached_high = None

    def check_condition(self, new_candle):
        """will run every time a new candle is pulled"""
        logger.info("GETTING SMA CROSSOVER SIGNAL")
        if (self.sma.value is not None) & (self.fma.value is not None) & (self.vol_change.value is not None):
            logger.info("SMA: " + str(self.sma.value))
            logger.info("FMA: " + str(self.fma.value))
            logger.info("VOL Change: " + str(self.vol_change.value) + "%")
            # if we already have a closing high saved, we need to check whether were still crossed over, and if we need to open a trade
            if self.cached_high is not None:
                logger.info("Checking if current price is greater than cached high")
                if not self.fma.value > self.sma.value: # if we're no longer fma > sma, forget about saved high
                    logger.info("FMA has gone below SMA, forgetting cached high")
                    self.cached_high = None
                    return False
                if new_candle[2] > self.cached_high: # open a trade if the latest high is greater than the cached high
                    logger.warning("Current high of " + str(new_candle[2]) + " has exceeded cached high of " + str(self.cached_high) + ", buy signal generated")
                    self.cached_high = None
                    return True
                else:
                    return False

            # if fma is not already above sma, and has now crossed, and volume is up 5% from last period, send trade signal
            elif self.cached_high is None and\
                    self.fma.value > self.sma.value and\
                    self.vol_change.value > 5:
                logger.info(f"FMA {self.fma.value} has crossed SMA{self.sma.value}, caching current high of " + str(new_candle[2]))
                self.cached_high = new_candle[2]
                return False
            else:
                return False
        else:
            return False
