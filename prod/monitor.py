import logging
import os
import time
import threading
import queue
import datetime
from typing import List

from config import config
from database import db
from coin import Coin
from bitvavo_client import Bitvavo_client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)


logger = logging.getLogger(__name__)

def time_ms() -> int:
    return int(time.time() * 1000)

def read_kbd_input(input_queue):
    print("Ready for keyboard input!!")
    while (True):
        input_str = input()
        input_queue.put(input_str)

# Global instances
bitvavo_client = Bitvavo_client()
coinlist: List[Coin] = []

def create_coin_list() -> List[Coin]:
    """Create coin list from database"""
    global coinlist
    coinlist = []
    
    # Load coins from database
    coin_data_list = db.get_all_coins()
    
    if not coin_data_list:
        logger.warning("No coins found in database. Run migrate_csv.py first!")
        return []
    
    logger.info(f"Loading {len(coin_data_list)} coins from database")
    
    for coin_data in coin_data_list:
        try:
            # Load coin with minimal logging
            position = coin_data['position']
            current_price = coin_data['current_price']
            gain = coin_data['gain']
            trail = coin_data['trail']
            temp_high = coin_data['temp_high']
            temp_low = coin_data['temp_low']

            # Calculate triggers
            if position == 'Y':
                sell_trigger = current_price * (1 + gain)
                trail_stop = temp_high * (1 - trail)
                trigger_active = temp_high >= sell_trigger
                logger.info(f"Loading #{coin_data['index_num']} {coin_data['base_currency']}-{coin_data['quote_currency']} [OWNED] "
                           f"price={current_price:.2f}, sell_trigger={sell_trigger:.2f}, "
                           f"active={'YES' if trigger_active else 'NO'}")
            else:
                buy_trigger = current_price * (1 - gain)
                trail_stop = temp_low * (1 + trail)
                trigger_active = temp_low < buy_trigger
                logger.info(f"Loading #{coin_data['index_num']} {coin_data['base_currency']}-{coin_data['quote_currency']} [WATCHING] "
                           f"price={current_price:.2f}, buy_trigger={buy_trigger:.2f}, "
                           f"active={'YES' if trigger_active else 'NO'}")

            coin = Coin(bitvavo_client, coin_data, coin_id=coin_data['id'])
            coinlist.append(coin)

        except Exception as e:
            logger.error(f"Failed to load coin {coin_data.get('index_num', 'unknown')}: {e}")
    
    # Count positions
    buy_positions = sum(1 for c in coin_data_list if c['position'] == 'Y')
    sell_positions = len(coin_data_list) - buy_positions
    total_transactie_bedrag = sum(c['transactie_bedrag'] for c in coin_data_list)

    logger.info(f"Successfully loaded {len(coinlist)} coins: {buy_positions} owned, {sell_positions} watching, total EUR{total_transactie_bedrag:.2f}")
    return coinlist


def print_test(coin_list):
        coin_list.sort(key = lambda b: b.base_currency)
        for coin in coin_list:
            if coin.position:
                print(
                f"{coin.index}, {coin.last_update}, {coin.number_deals}, {coin.transactie_bedrag}: {coin.base_currency}, \t{coin.position}, \tS: {coin.current_price}, \tC: {coin.bid} = {round((coin.bid / coin.current_price) * 100, 2)}, \tH: {coin.high} = {round((coin.high / coin.current_price) * 100, 2)}, \tD: {coin.gain}/{coin.trail}")
            else:
                print(
                    f"{coin.index}, {coin.last_update}, {coin.number_deals}, {coin.transactie_bedrag}: {coin.base_currency}, \t{coin.position}, \tS: {coin.current_price}, \tC: {coin.ask} = {round((coin.ask / coin.current_price) * 100, 2)}, \tL: {coin.low} = {round((coin.low / coin.current_price) * 100, 2)}, \tD: {coin.gain}/{coin.trail}")



def start_trading(coin_list: List[Coin]):
    """Main trading loop with database persistence and test mode support"""
    logger.info(f"Starting {config.get_mode_description()}")
    logger.info(f"Monitoring {len(coin_list)} coins")
    
    if not config.is_test_mode():
        logger.warning("⚠️  LIVE TRADING MODE - Real money at risk!")
    
    cycle_count = 0
    
    while True:
        cycle_count += 1
        start_time = time_ms()
        start_dt = datetime.datetime.fromtimestamp(start_time / 1000.0, tz=datetime.timezone.utc)
        
        logger.info(f"Trading cycle {cycle_count} started at {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Start new cycle for optimized caching
        bitvavo_client.start_new_cycle(cycle_count)
        
        for coin in coin_list:
            try:
                # Check if coin is in sleep mode
                current_time = time_ms()
                
                if coin.sleep_till > current_time:
                    sleep_dt = datetime.datetime.fromtimestamp(coin.sleep_till / 1000.0, tz=datetime.timezone.utc)
                    logger.debug(f"Coin {coin.analysis_pair} sleeping until {sleep_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                    continue
                
                # Store old state for change detection
                old_position = coin.get_position()
                old_temp_high = coin.high
                old_temp_low = coin.low
                
                # Execute trading logic
                coin.check_action()  # Uses global test mode from config
                
                # Check for significant changes and log them
                new_position = coin.get_position()
                
                if new_position != old_position:
                    logger.info(f"Position change: {coin.analysis_pair} "
                               f"{'BOUGHT' if new_position else 'SOLD'}")
                
                # Log significant price movements
                if not new_position and coin.low < old_temp_low:
                    logger.info(f"New low: {coin.analysis_pair} {coin.low} (was {old_temp_low})")
                
                if new_position and coin.high > old_temp_high:
                    logger.info(f"New high: {coin.analysis_pair} {coin.high} (was {old_temp_high})")
                
                # Small delay between coins to prevent API rate limiting
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing coin {coin.analysis_pair}: {e}")
                continue
        
        # Calculate cycle time
        end_time = time_ms()
        cycle_duration = (end_time - start_time) / 1000.0
        
        logger.info(f"Trading cycle {cycle_count} completed in {cycle_duration:.2f}s")
        
        # Brief pause between cycles
        time.sleep(2)

if __name__ == '__main__':
    # Display startup information with configuration validation
    logger.info("=== Crypto Trading Bot Monitor ===")

    try:
        # Validate configuration on startup
        logger.info(f"Configuration Summary:\n{config.get_configuration_summary()}")
        
        # Check for configuration warnings
        warnings = config.validate_runtime_settings()
        if warnings:
            for warning in warnings:
                logger.warning(warning)

        if config.is_test_mode():
            logger.info("SAFE mode - no real trades will be executed")
        else:
            logger.warning("LIVE TRADING MODE - real money at risk!")
            if not config.BITVAVO_API_KEY:
                logger.error("API keys not configured for live trading")
                exit(1)

    except ValueError as e:
        logger.error(f"CONFIGURATION ERROR: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"STARTUP ERROR: {e}")
        exit(1)
    
    # Load coins and start trading
    coin_list = create_coin_list()

    if not coin_list:
        logger.error("No coins loaded. Run migrate_csv.py first!")
        exit(1)

    try:
        start_trading(coin_list)
    except KeyboardInterrupt:
        logger.info("Trading stopped by user")
    except Exception as e:
        logger.error(f"Trading failed: {e}")
        exit(1)
