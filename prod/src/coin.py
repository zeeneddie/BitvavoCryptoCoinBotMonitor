import datetime
import time
import logging
import os
from collections import defaultdict
from decimal import Decimal
from typing import Optional, Dict, Any

from config import config
from database import db
from reporting.trade_discord_notifier import send_sell_notification, send_buy_notification
from services.proceeds_calculator import proceeds_calculator, ProceedsResult

logger = logging.getLogger(__name__)

markets = []

def time_ms() -> int:
    return int(time.time() * 1000)


class Coin:
    """An object that allows a specific strategy to interface with an exchange,
    This includes functionality to contain and update TA indicators as well as the latest OHLCV data
    This also handles the API key for authentication, as well as methods to place orders"""

    def __init__(self, bitvavo_client, coin_info, coin_id: Optional[int] = None):
        # Database ID for tracking
        self.coin_id = coin_id
        
        # Initialize from coin_info (CSV format or dict)
        if isinstance(coin_info, dict):
            self._init_from_dict(coin_info)
        else:
            self._init_from_list(coin_info)
        
        # Trading client
        self.bitvavo = bitvavo_client.bitvavo if bitvavo_client else None
        
        # Technical analysis data
        self.signals = []
        self.indicators = defaultdict(list)
        self.candles = defaultdict(list)
        self.latest_candle = defaultdict(list)
        
        # Order parameters
        self.var_sell = {'amountQuote': str(self.transactie_bedrag), 'operatorId': config.OPERATOR_ID}
        self.var_buy = {'amountQuote': str(self.transactie_bedrag), 'operatorId': config.OPERATOR_ID}
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
        # Initialize trading signals
        self._init_trading_signals()
        
        # Test mode configuration
        self.test_mode = config.is_test_mode()
        self.testdata = self.current_price
    
    def _init_from_list(self, coin_info):
        """Initialize from CSV list format"""
        self.index = int(coin_info[0])
        self.base_currency = coin_info[1].strip()
        self.quote_currency = coin_info[2].strip()
        self.analysis_pair = f'{self.base_currency}-{self.quote_currency}'
        self.position = coin_info[3].strip() == 'Y'
        self.transactie_bedrag = float(coin_info[4])
        self.current_price = float(coin_info[5])
        self.gain = float(coin_info[6])
        self.trail = float(coin_info[7])
        # self.stoploss = float(coin_info[8])  # Removed - using only trailing stops
        self.temp_high = float(coin_info[9])
        self.high = self.temp_high
        self.temp_low = float(coin_info[10])
        self.low = self.temp_low
        self.number_deals = int(coin_info[11])
        self.last_update = str(coin_info[12])
        self.sleep_till = int(coin_info[13])
        self.last_buy_price = 0.0  # Not in CSV, default to 0

        # Proceeds strategy - use global defaults for CSV format
        self.proceeds_strategy = config.DEFAULT_PROCEEDS_STRATEGY
        self.proceeds_crypto_ratio = config.DEFAULT_PROCEEDS_CRYPTO_RATIO
    
    def _init_from_dict(self, coin_info):
        """Initialize from database dict format"""
        self.index = coin_info['index_num']
        self.base_currency = coin_info['base_currency']
        self.quote_currency = coin_info['quote_currency']
        self.analysis_pair = f'{self.base_currency}-{self.quote_currency}'
        self.position = coin_info['position'] == 'Y'
        self.transactie_bedrag = coin_info['transactie_bedrag']
        self.current_price = coin_info['current_price']
        self.gain = coin_info['gain']
        self.trail = coin_info['trail']
        # self.stoploss = coin_info['stoploss']  # Removed - using only trailing stops
        self.temp_high = coin_info['temp_high']
        self.high = self.temp_high
        self.temp_low = coin_info['temp_low']
        self.low = self.temp_low
        self.number_deals = coin_info['number_deals']
        self.last_update = coin_info['last_update']
        self.sleep_till = coin_info['sleep_till']
        self.coin_id = coin_info.get('id')
        self.last_buy_price = coin_info.get('last_buy_price', 0.0)

        # Proceeds strategy configuration (per-coin override of global config)
        self.proceeds_strategy = coin_info.get('proceeds_strategy') or config.DEFAULT_PROCEEDS_STRATEGY
        self.proceeds_crypto_ratio = coin_info.get('proceeds_crypto_ratio')
        if self.proceeds_crypto_ratio is None:
            self.proceeds_crypto_ratio = config.DEFAULT_PROCEEDS_CRYPTO_RATIO

    @property
    def buy_price_reference(self):
        """Price reference for buy logic calculations"""
        return self.current_price

    @property
    def sell_price_reference(self):
        """Price reference for sell logic calculations"""
        return self.current_price

    def _init_trading_signals(self):
        """Initialize trading thresholds and signals with herstart validation"""
        if self.position:
            # SELL coin - Valideer signal bij herstart
            self.sell_drempel = self.current_price * (1 + self.gain)

            if self.temp_high >= self.sell_drempel:
                # Signal WAS actief - valideer of BID nog boven sell_trigger is
                try:
                    current_bid = float(self.get_best_bid())

                    if current_bid >= self.sell_drempel:
                        # ✅ BID nog boven sell_trigger → Signal blijft actief, temp_high behouden
                        self.sell_signal = True
                        trail_sell = self.temp_high * (1 - self.trail)
                        logger.debug(
                            f"✅ SELL SIGNAL ACTIEF na herstart: {self.analysis_pair} | "
                            f"Coin ID: {self.coin_id} | "
                            f"Matrix: €{self.current_price:,.2f} | "
                            f"Sell trigger: €{self.sell_drempel:,.2f} | "
                            f"BID: €{current_bid:,.2f} ✅ (boven trigger) | "
                            f"temp_high: €{self.temp_high:,.2f} (behouden) | "
                            f"Trail: €{trail_sell:,.2f}"
                        )
                    else:
                        # ❌ BID onder sell_trigger → Signal moet gereset
                        old_temp_high = self.temp_high
                        self.sell_signal = False
                        self.temp_high = current_bid
                        self.high = current_bid
                        self._save_to_database()

                        logger.debug(
                            f"🔄 SIGNAL EXPIRED (SELL): {self.analysis_pair} | "
                            f"Coin ID: {self.coin_id} | "
                            f"Matrix: €{self.current_price:,.2f} | "
                            f"Sell trigger: €{self.sell_drempel:,.2f} | "
                            f"BID: €{current_bid:,.2f} ❌ (onder trigger) | "
                            f"Oude temp_high: €{old_temp_high:,.2f} | "
                            f"Reset temp_high → €{current_bid:,.2f}"
                        )
                except Exception as e:
                    logger.error(f"Kan bid niet ophalen bij herstart validatie: {e}")
                    self.sell_signal = False
            else:
                self.sell_signal = False
                logger.debug(f"No sell signal: {self.analysis_pair}, {self.temp_high} < {self.sell_drempel}")
        else:
            # BUY coin - Valideer signal bij herstart
            self.buy_drempel = self.current_price * (1 - self.gain)

            if self.temp_low < self.buy_drempel:
                # Signal WAS actief - valideer of ASK nog onder buy_trigger is
                try:
                    current_ask = float(self.get_best_ask())

                    if current_ask <= self.buy_drempel:
                        # ✅ ASK nog onder buy_trigger → Signal blijft actief, temp_low behouden
                        self.buy_signal = True
                        self.trail_stop_buy_drempel = self.temp_low * (1 + self.trail)
                        trail_buy = self.temp_low * (1 + self.trail)
                        logger.debug(
                            f"✅ BUY SIGNAL ACTIEF na herstart: {self.analysis_pair} | "
                            f"Coin ID: {self.coin_id} | "
                            f"Matrix: €{self.current_price:,.2f} | "
                            f"Buy trigger: €{self.buy_drempel:,.2f} | "
                            f"ASK: €{current_ask:,.2f} ✅ (onder trigger) | "
                            f"temp_low: €{self.temp_low:,.2f} (behouden) | "
                            f"Trail: €{trail_buy:,.2f}"
                        )
                    else:
                        # ❌ ASK boven buy_trigger → Signal moet gereset
                        old_temp_low = self.temp_low
                        self.buy_signal = False
                        self.temp_low = current_ask
                        self.low = current_ask
                        self._save_to_database()

                        logger.debug(
                            f"🔄 SIGNAL EXPIRED (BUY): {self.analysis_pair} | "
                            f"Coin ID: {self.coin_id} | "
                            f"Matrix: €{self.current_price:,.2f} | "
                            f"Buy trigger: €{self.buy_drempel:,.2f} | "
                            f"ASK: €{current_ask:,.2f} ❌ (boven trigger) | "
                            f"Oude temp_low: €{old_temp_low:,.2f} | "
                            f"Reset temp_low → €{current_ask:,.2f}"
                        )
                except Exception as e:
                    logger.error(f"Kan ask niet ophalen bij herstart validatie: {e}")
                    self.buy_signal = False
            else:
                self.buy_signal = False
                logger.debug(f"No buy signal: {self.analysis_pair}, temp: {self.temp_low} >= {self.buy_drempel}")




    def get_best_bid(self):
        # Probeer eerst de originele client (als beschikbaar)
        if self.bitvavo:
            try:
                best = self.bitvavo.book(self.analysis_pair, {'depth': '1'})
                if 'error' not in best:
                    return best['bids'][0][0]
            except Exception as e:
                logger.debug(f"Originele API gefaald voor {self.analysis_pair}: {e}")

        # Fallback naar publieke API
        try:
            from bitvavo_client import Bitvavo_client
            client = Bitvavo_client()
            if client.can_read_market_data():
                best = client.book(self.analysis_pair, {'depth': '1'})
                if 'error' not in best:
                    return float(best['bids'][0][0])
        except Exception as e:
            logger.debug(f"Publieke API gefaald voor {self.analysis_pair}: {e}")

        # Geen data beschikbaar - return None of raise error
        logger.error(f"Geen bid data beschikbaar voor {self.analysis_pair}")
        raise RuntimeError(f"Kan geen bid prijs ophalen voor {self.analysis_pair}")

    def get_best_ask(self):
        # Probeer eerst de originele client (als beschikbaar)
        if self.bitvavo:
            try:
                best = self.bitvavo.book(self.analysis_pair, {'depth': '1'})
                if 'error' not in best:
                    return best['asks'][0][0]
            except Exception as e:
                logger.debug(f"Originele API gefaald voor {self.analysis_pair}: {e}")

        # Fallback naar publieke API
        try:
            from bitvavo_client import Bitvavo_client
            client = Bitvavo_client()
            if client.can_read_market_data():
                best = client.book(self.analysis_pair, {'depth': '1'})
                if 'error' not in best:
                    return float(best['asks'][0][0])
        except Exception as e:
            logger.debug(f"Publieke API gefaald voor {self.analysis_pair}: {e}")

        # Geen data beschikbaar - return None of raise error
        logger.error(f"Geen ask data beschikbaar voor {self.analysis_pair}")
        raise RuntimeError(f"Kan geen ask prijs ophalen voor {self.analysis_pair}")

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

    def check_action(self, test: bool = None):
        """Check and execute trading actions with test mode support"""
        # Override global test mode if specified
        is_test_mode = test if test is not None else self.test_mode

        # Log price update
        if self.coin_id:
            db.log_price_update(self.coin_id, self.current_price)

        # ⭐ STIJGENDE MARKT CHECK - Voorkom kopen bij stijgende markt ⭐
        if not self.position:  # WIL KOPEN
            # Check of er al een coin van deze crypto in BEZIT is
            coins_in_bezit = db.get_coins_in_position(self.base_currency)

            if coins_in_bezit:
                # Er zijn al coins in bezit!
                # Haal de huidige marktprijs op
                try:
                    current_ask = float(self.get_best_ask())
                except Exception as e:
                    logger.warning(f"Kan marktprijs niet ophalen: {e}")
                    current_ask = self.current_price

                # Check of markt aan het stijgen is
                # We kijken naar de LAAGSTE matrix prijs van coins in bezit
                laagste_matrix = min(c['current_price'] for c in coins_in_bezit)

                if current_ask > laagste_matrix:
                    # Markt stijgt boven de laagste inkoop prijs!
                    # NIET kopen - laat bestaande coins richting trigger bewegen
                    logger.info(
                        f"⏸️  SKIP BUY {self.analysis_pair}: Stijgende markt "
                        f"(ask {current_ask:,.2f} > laagste bezit {laagste_matrix:,.2f}). "
                        f"{len(coins_in_bezit)} coin(s) in bezit monitoren voor verkoop."
                    )
                    return  # Stop hier - geen buy check
                else:
                    # Markt daalt onder laagste inkoop
                    # Dit is een DIP - WEL kopen toegestaan (extra positie opbouwen)
                    logger.info(
                        f"📉 DIP DETECTED {self.analysis_pair}: "
                        f"ask {current_ask:,.2f} < laagste bezit {laagste_matrix:,.2f}. "
                        f"Buy check toegestaan (extra positie bij daling)."
                    )
                    # Ga door naar normale buy logic hieronder

        if self.position:               # we are going to sell
            # Always read real market data when available, regardless of test mode
            if self.bitvavo:
                try:
                    bid = float(self.get_best_bid())
                except Exception as e:
                    logger.warning(f"API call failed, using test data: {e}")
                    bid = self.get_next_test()
            else:
                # Fallback to test data if no API available
                bid = self.get_next_test()
            self.bid = bid
            
            # Log price update with bid/ask
            if self.coin_id:
                db.log_price_update(self.coin_id, bid, bid=bid)
            
            # FIX: Update temp_high als BID hoger is dan huidige temp_high (niet alleen bij absolute high)
            # Dit zorgt ervoor dat trailing sell de hoogste prijs blijft volgen
            if bid > self.temp_high:
                old_temp_high = self.temp_high
                self.temp_high = bid

                # Update absolute high en drempels alleen bij nieuwe absolute high
                if bid > self.high:
                    self.high = bid
                    self.sell_drempel = self.current_price * (1 + self.gain)

                # Bereken old_trail voor logging (alleen als signal actief is)
                old_trail = old_temp_high * (1 - self.trail) if self.sell_signal else None

                # BELANGRIJK: Sla nieuwe temp_high direct op naar database
                self._save_to_database()

                # Logging: temp_high update
                diff = bid - old_temp_high
                logger.debug(
                    f"📈 TEMP_HIGH: {self.analysis_pair} | "
                    f"Coin ID: {self.coin_id} | "
                    f"€{old_temp_high:,.2f} → €{bid:,.2f} (+€{diff:,.2f})"
                )

                if self.high >= self.sell_drempel:
                    if not self.sell_signal:
                        # Signal wordt NU actief (trigger doorbraak)
                        self.trail_stop_sell_drempel = self.temp_high * (1 - self.trail)
                        logger.debug(
                            f"🚀 SELL TRIGGER BEREIKT: {self.analysis_pair} | "
                            f"Coin ID: {self.coin_id} | "
                            f"Matrix: €{self.current_price:,.2f} | "
                            f"Sell drempel: €{self.sell_drempel:,.2f} (matrix × {1 + self.gain:.4f}) | "
                            f"BID: €{bid:,.2f} ✅ | "
                            f"→ SELL SIGNAL ACTIEF | "
                            f"temp_high init: €{self.temp_high:,.2f} | "
                            f"Trail sell: €{self.trail_stop_sell_drempel:,.2f} (temp_high × {1 - self.trail:.4f})"
                        )

                    self.sell_signal = True

                    # Herbereken trail_stop_sell_drempel altijd op basis van nieuwe temp_high
                    self.trail_stop_sell_drempel = self.temp_high * (1 - self.trail)

                    # Trail herberekening logging (alleen als signal al actief was)
                    if old_trail is not None:
                        new_trail = self.trail_stop_sell_drempel
                        trail_diff = new_trail - old_trail
                        logger.debug(
                            f"⬆️ TRAIL HERBEREKEND (SELL): {self.analysis_pair} | "
                            f"Coin ID: {self.coin_id} | "
                            f"temp_high: €{old_temp_high:,.2f} → €{self.temp_high:,.2f} | "
                            f"Oude trail: €{old_trail:,.2f} | "
                            f"Nieuwe trail: €{new_trail:,.2f} (+€{trail_diff:,.2f}) | "
                            f"→ Moet nu €{new_trail:,.2f} doorbreken voor verkoop"
                        )

                    # Sla sell signal status ook op
                    self._save_to_database()

                    # Log signal to database
                    if self.coin_id:
                        db.log_signal(self.coin_id, 'sell', bid, self.sell_drempel, is_test_mode)
                        
            if self.sell_signal:
                if bid <= self.trail_stop_sell_drempel:
                    # Execute sell order
                    transaction_result = self._execute_sell_order(bid, is_test_mode)

                    if transaction_result['success']:
                        # Bereken transactie details
                        result = transaction_result.get('result', {})
                        order_id = result.get('orderId', 'N/A')

                        # Bereken amount, total en fees
                        fills = result.get('fills', [])
                        if fills:
                            actual_price = float(fills[0].get('price', bid))
                            amount = float(fills[0].get('amount', 0))
                            fee = float(fills[0].get('fee', 0)) if 'fee' in fills[0] else 0
                        else:
                            actual_price = bid
                            amount = 0
                            fee = 0

                        total = actual_price * amount if amount > 0 else self.transactie_bedrag

                        # Bereken winst
                        profit = actual_price - self.current_price
                        profit_pct = (profit / self.current_price) * 100 if self.current_price > 0 else 0

                        # Detail logging
                        logger.debug(
                            f"💰 SELL UITGEVOERD: {self.analysis_pair} | "
                            f"Coin ID: {self.id} | "
                            f"Order ID: {order_id} | "
                            f"Matrix: €{self.current_price:,.2f} | "
                            f"Sell trigger: €{self.sell_drempel:,.2f} (matrix × {1 + self.gain:.4f}) | "
                            f"temp_high (hoogste): €{self.temp_high:,.2f} | "
                            f"Trail sell: €{self.trail_stop_sell_drempel:,.2f} (temp_high × {1 - self.trail:.4f}) | "
                            f"Verkocht @ €{actual_price:,.2f} ✅ | "
                            f"Amount: {amount:.8f} {self.base_currency} | "
                            f"Total: €{total:,.2f} | "
                            f"Fees: €{fee:,.4f} | "
                            f"Winst: €{profit:,.2f} ({profit_pct:.2f}% boven matrix)"
                        )

                        # Discord notificatie voor SELL transactie
                        send_sell_notification(
                            coin_id=self.coin_id,
                            crypto=self.analysis_pair,
                            matrix_price=self.current_price,
                            sell_trigger=self.sell_drempel,
                            trail_sell_price=self.trail_stop_sell_drempel,
                            actual_sell_price=actual_price,
                            amount=amount,
                            total=total,
                            fee=fee,
                            profit=profit,
                            profit_pct=profit_pct,
                            order_id=order_id
                        )

                        logger.info(f"{'TEST' if is_test_mode else 'LIVE'} SELL executed: {self.analysis_pair} @ {bid}")

                        # Handle proceeds strategy (determines what to do with sell proceeds)
                        sell_tx_id = transaction_result.get('transaction_id')
                        proceeds_result = self._handle_proceeds_strategy(total, is_test_mode, sell_transaction_id=sell_tx_id)

                        # Common state updates after SELL
                        self.sell_signal = False
                        self.last_update = get_timestamp()
                        self.number_deals += 1

                        if proceeds_result and proceeds_result.get('success'):
                            # Reinvestment BUY was executed successfully
                            # _handle_proceeds_strategy already updated:
                            # - position = True
                            # - transactie_bedrag = new_buy_amount
                            # - last_buy_price = actual buy price
                            # - temp values = actual buy price
                            pr = proceeds_result['proceeds_result']
                            logger.info(
                                f"PROCEEDS REINVESTED: {self.analysis_pair} | "
                                f"Strategy: {pr.strategy_used} | "
                                f"Reinvested: EUR {pr.new_buy_amount:.2f} | "
                                f"Retained: EUR {pr.retained_eur:.2f}"
                            )
                        else:
                            # No reinvestment - coin goes back to BUY mode
                            self.position = False

                            # Update transactie_bedrag based on proceeds result
                            if proceeds_result and 'proceeds_result' in proceeds_result:
                                pr = proceeds_result['proceeds_result']
                                # For 'eur' strategy or failed reinvestment:
                                # Keep the original amount (or adjust based on profit if desired)
                                if pr.strategy_used == 'eur':
                                    # EUR Strategy: take profits, DEACTIVATE coin (no more monitoring)
                                    self.active = False
                                    logger.info(
                                        f"PROCEEDS EUR MODE: {self.analysis_pair} | "
                                        f"Retained EUR {pr.retained_eur:.2f} as profit | "
                                        f"Coin DEACTIVATED - no more monitoring"
                                    )
                                elif pr.strategy_used == 'split' and pr.profit <= 0:
                                    # Loss on split strategy - no reinvestment, keep what's left
                                    self.transactie_bedrag = float(pr.sell_amount)
                                    logger.info(
                                        f"PROCEEDS SPLIT (LOSS): {self.analysis_pair} | "
                                        f"Loss EUR {abs(pr.profit):.2f} | "
                                        f"New bedrag: EUR {self.transactie_bedrag:.2f}"
                                    )
                            else:
                                # Fallback: old behavior - grow by actual profit
                                if self.last_buy_price > 0:
                                    werkelijke_winst = (actual_price - self.last_buy_price) / self.last_buy_price
                                    old_bedrag = self.transactie_bedrag
                                    self.transactie_bedrag = round(self.transactie_bedrag * (1 + werkelijke_winst), 2)
                                    logger.info(
                                        f"BEDRAG GEGROEID (fallback): Buy EUR {self.last_buy_price:,.2f} -> "
                                        f"Sell EUR {actual_price:,.2f} | "
                                        f"Winst {werkelijke_winst*100:.2f}% | "
                                        f"Bedrag EUR {old_bedrag:,.2f} -> EUR {self.transactie_bedrag:,.2f}"
                                    )

                            # Reset temp waarden naar matrix_price (schone lei)
                            self.low = self.current_price
                            self.temp_low = self.low
                            self.high = self.current_price
                            self.temp_high = self.high

                            # Reset last_buy_price
                            self.last_buy_price = 0.0

                        # Save updated coin state
                        self._save_to_database()
                    else:
                        logger.error(f"Sell order failed: {transaction_result.get('error', 'Unknown error')}")

            # Stop loss removed - using only trailing stops
        else:                           # we are going to buy
            # Always read real market data when available, regardless of test mode
            if self.bitvavo:
                try:
                    ask = float(self.get_best_ask())
                except Exception as e:
                    logger.warning(f"API call failed, using test data: {e}")
                    ask = self.get_next_test()
            else:
                # Fallback to test data if no API available
                ask = self.get_next_test()
            self.ask = ask
            
            # Log price update with ask
            if self.coin_id:
                db.log_price_update(self.coin_id, ask, ask=ask)
            
            # FIX: Update temp_low als ASK lager is dan huidige temp_low (niet alleen bij absolute low)
            # Dit zorgt ervoor dat trailing buy de laagste prijs blijft volgen
            if ask < self.temp_low:
                old_temp_low = self.temp_low
                self.temp_low = ask

                # Update absolute low en drempels alleen bij nieuwe absolute low
                if ask < self.low:
                    self.low = ask
                    self.buy_drempel = self.current_price * (1 - self.gain)

                # Bereken old_trail voor logging (alleen als signal actief is)
                old_trail = old_temp_low * (1 + self.trail) if self.buy_signal else None

                # BELANGRIJK: Sla nieuwe temp_low direct op naar database
                self._save_to_database()

                # Logging: temp_low update
                diff = old_temp_low - ask
                logger.debug(
                    f"📉 TEMP_LOW: {self.analysis_pair} | "
                    f"Coin ID: {self.coin_id} | "
                    f"€{old_temp_low:,.2f} → €{ask:,.2f} (-€{diff:,.2f})"
                )

                if self.low < self.buy_drempel:
                    if not self.buy_signal:
                        # Signal wordt NU actief (trigger doorbraak)
                        self.trail_stop_buy_drempel = self.temp_low * (1 + self.trail)
                        logger.debug(
                            f"📉 BUY TRIGGER BEREIKT: {self.analysis_pair} | "
                            f"Coin ID: {self.coin_id} | "
                            f"Matrix: €{self.current_price:,.2f} | "
                            f"Buy drempel: €{self.buy_drempel:,.2f} (matrix × {1 - self.gain:.4f}) | "
                            f"ASK: €{ask:,.2f} ✅ | "
                            f"→ BUY SIGNAL ACTIEF | "
                            f"temp_low init: €{self.temp_low:,.2f} | "
                            f"Trail buy: €{self.trail_stop_buy_drempel:,.2f} (temp_low × {1 + self.trail:.4f})"
                        )

                    self.buy_signal = True

                    # Herbereken trail_stop_buy_drempel altijd op basis van nieuwe temp_low
                    self.trail_stop_buy_drempel = self.temp_low * (1 + self.trail)

                    # Trail herberekening logging (alleen als signal al actief was)
                    if old_trail is not None:
                        new_trail = self.trail_stop_buy_drempel
                        trail_diff = old_trail - new_trail
                        logger.debug(
                            f"⬇️ TRAIL HERBEREKEND (BUY): {self.analysis_pair} | "
                            f"Coin ID: {self.coin_id} | "
                            f"temp_low: €{old_temp_low:,.2f} → €{self.temp_low:,.2f} | "
                            f"Oude trail: €{old_trail:,.2f} | "
                            f"Nieuwe trail: €{new_trail:,.2f} (-€{trail_diff:,.2f}) | "
                            f"→ Moet nu €{new_trail:,.2f} doorbreken voor aankoop"
                        )

                    # Sla buy signal status ook op
                    self._save_to_database()

                    # Log signal to database
                    if self.coin_id:
                        db.log_signal(self.coin_id, 'buy', ask, self.buy_drempel, is_test_mode)
                        
            if self.buy_signal:
                if self.trail_stop_buy_drempel <= ask:
                    # Execute buy order
                    transaction_result = self._execute_buy_order(ask, is_test_mode)

                    if transaction_result['success']:
                        # Bereken transactie details
                        result = transaction_result.get('result', {})
                        order_id = result.get('orderId', 'N/A')

                        # Bereken amount, total en fees
                        fills = result.get('fills', [])
                        if fills:
                            actual_price = float(fills[0].get('price', ask))
                            amount = float(fills[0].get('amount', 0))
                            fee = float(fills[0].get('fee', 0)) if 'fee' in fills[0] else 0
                        else:
                            actual_price = ask
                            amount = 0
                            fee = 0

                        total = actual_price * amount if amount > 0 else self.transactie_bedrag

                        # Bereken discount
                        discount = self.current_price - actual_price
                        discount_pct = (discount / self.current_price) * 100 if self.current_price > 0 else 0

                        # Detail logging
                        logger.debug(
                            f"💰 BUY UITGEVOERD: {self.analysis_pair} | "
                            f"Coin ID: {self.coin_id} | "
                            f"Order ID: {order_id} | "
                            f"Matrix: €{self.current_price:,.2f} | "
                            f"Buy trigger: €{self.buy_drempel:,.2f} (matrix × {1 - self.gain:.4f}) | "
                            f"temp_low (laagste): €{self.temp_low:,.2f} | "
                            f"Trail buy: €{self.trail_stop_buy_drempel:,.2f} (temp_low × {1 + self.trail:.4f}) | "
                            f"Gekocht @ €{actual_price:,.2f} ✅ | "
                            f"Amount: {amount:.8f} {self.base_currency} | "
                            f"Total: €{total:,.2f} | "
                            f"Fees: €{fee:,.4f} | "
                            f"Discount: €{discount:,.2f} ({discount_pct:.2f}% onder matrix)"
                        )

                        # Discord notificatie voor BUY transactie
                        send_buy_notification(
                            coin_id=self.coin_id,
                            crypto=self.analysis_pair,
                            matrix_price=self.current_price,
                            buy_trigger=self.buy_drempel,
                            trail_buy_price=self.trail_stop_buy_drempel,
                            actual_buy_price=actual_price,
                            amount=amount,
                            total=total,
                            fee=fee,
                            discount=discount,
                            discount_pct=discount_pct,
                            order_id=order_id
                        )

                        logger.info(f"{'TEST' if is_test_mode else 'LIVE'} BUY executed: {self.analysis_pair} @ {ask}")
                        self.buy_signal = False
                        self.position = True
                        # Reset beide temp waarden naar matrix_price (schone lei)
                        self.high = self.current_price
                        self.temp_high = self.high
                        self.low = self.current_price
                        self.temp_low = self.low
                        self.last_update = get_timestamp()
                        self.number_deals += 1

                        # Track buy price voor winst berekening bij sell
                        self.last_buy_price = actual_price

                        logger.debug(f"💰 BUY PRICE TRACKED: {self.analysis_pair} @ €{actual_price:,.2f}")

                        # Save updated coin state
                        self._save_to_database()
                    else:
                        logger.error(f"Buy order failed: {transaction_result.get('error', 'Unknown error')}")


            # Stop loss removed - using only trailing stops
    
    def _calculate_sell_params(self, current_price: float) -> Dict[str, Any]:
        """
        Calculate sell parameters based on proceeds_strategy.

        Strategies:
        - 'eur': amountQuote = transactie_bedrag (sell EUR worth, leftover crypto = profit)
        - 'crypto': amount = crypto_owned (sell ALL crypto, no leftover)
        - 'split': amountQuote = transactie_bedrag + (profit * ratio) (partial reinvest)

        Returns:
            dict with either 'amount' (crypto) or 'amountQuote' (EUR) + metadata
        """
        # Fallback if no last_buy_price available
        if self.last_buy_price <= 0:
            logger.warning(
                f"No last_buy_price for {self.analysis_pair}, using amountQuote fallback"
            )
            return {
                'use_amount': False,
                'amountQuote': self.transactie_bedrag,
                'expected_eur': self.transactie_bedrag,
                'crypto_owned': 0,
                'strategy': self.proceeds_strategy
            }

        # Calculate how much crypto we own
        crypto_owned = self.transactie_bedrag / self.last_buy_price

        # Calculate expected profit at current price
        current_value = crypto_owned * current_price
        profit = current_value - self.transactie_bedrag
        profit_pct = (profit / self.transactie_bedrag) * 100 if self.transactie_bedrag > 0 else 0

        logger.info(
            f"SELL PARAMS CALC: {self.analysis_pair} | "
            f"Strategy: {self.proceeds_strategy} | "
            f"Crypto owned: {crypto_owned:.8f} | "
            f"Buy price: EUR {self.last_buy_price:,.2f} | "
            f"Current: EUR {current_price:,.2f} | "
            f"Value: EUR {current_value:.2f} | "
            f"Profit: EUR {profit:.2f} ({profit_pct:.1f}%)"
        )

        if self.proceeds_strategy == 'crypto':
            # Sell ALL crypto - no leftover, full compound growth
            logger.info(
                f"CRYPTO STRATEGY: Selling ALL {crypto_owned:.8f} crypto | "
                f"Expected EUR: {current_value:.2f}"
            )
            return {
                'use_amount': True,
                'amount': round(crypto_owned, 8),
                'expected_eur': current_value,
                'crypto_owned': crypto_owned,
                'profit': profit,
                'strategy': 'crypto'
            }

        elif self.proceeds_strategy == 'split':
            # Sell transactie_bedrag + (profit * ratio)
            # Leftover crypto = profit * (1 - ratio)
            if profit > 0:
                sell_eur = self.transactie_bedrag + (profit * self.proceeds_crypto_ratio)
                leftover_value = profit * (1 - self.proceeds_crypto_ratio)
            else:
                # No profit or loss - just sell original amount
                sell_eur = self.transactie_bedrag
                leftover_value = 0

            logger.info(
                f"SPLIT STRATEGY: Selling EUR {sell_eur:.2f} worth | "
                f"Ratio: {self.proceeds_crypto_ratio} | "
                f"Leftover crypto value: EUR {leftover_value:.2f}"
            )
            return {
                'use_amount': False,
                'amountQuote': round(sell_eur, 2),
                'expected_eur': sell_eur,
                'crypto_owned': crypto_owned,
                'profit': profit,
                'leftover_value': leftover_value,
                'strategy': 'split'
            }

        else:  # 'eur' or unknown - use original behavior
            # Sell only transactie_bedrag EUR worth
            # Leftover crypto = profit (stays in wallet)
            logger.info(
                f"EUR STRATEGY: Selling EUR {self.transactie_bedrag:.2f} worth | "
                f"Leftover crypto value: EUR {profit:.2f}"
            )
            return {
                'use_amount': False,
                'amountQuote': self.transactie_bedrag,
                'expected_eur': self.transactie_bedrag,
                'crypto_owned': crypto_owned,
                'profit': profit,
                'leftover_value': profit if profit > 0 else 0,
                'strategy': 'eur'
            }

    def _execute_sell_order(self, price: float, is_test_mode: bool) -> Dict[str, Any]:
        """Execute sell order with strategy-aware amount calculation"""
        try:
            # Calculate sell parameters based on proceeds_strategy
            sell_params = self._calculate_sell_params(price)

            if is_test_mode:
                # Simulate order based on sell params
                if sell_params['use_amount']:
                    # Crypto amount sell
                    crypto_amount = sell_params['amount']
                    eur_received = crypto_amount * price
                else:
                    # EUR amount sell
                    eur_received = sell_params['amountQuote']
                    crypto_amount = eur_received / price if price > 0 else 0

                result = {
                    'orderId': f'TEST_SELL_{self.analysis_pair}_{int(time.time())}',
                    'market': self.analysis_pair,
                    'side': 'sell',
                    'orderType': 'market',
                    'amount': str(crypto_amount),
                    'filledAmount': str(crypto_amount),
                    'fills': [{'price': str(price), 'amount': str(crypto_amount)}],
                    'status': 'filled',
                    'sell_params': sell_params  # Include for debugging
                }

                transaction_id = db.log_transaction(
                    self.coin_id, 'sell', 'market', eur_received, price,
                    is_test_mode=True, status='test'
                )

                logger.info(
                    f"TEST SELL: {self.analysis_pair} | "
                    f"Strategy: {sell_params['strategy']} | "
                    f"{'amount' if sell_params['use_amount'] else 'amountQuote'}: "
                    f"{crypto_amount if sell_params['use_amount'] else sell_params['amountQuote']} | "
                    f"EUR received: {eur_received:.2f}"
                )
            else:
                # Execute real order
                if not self.bitvavo:
                    raise ValueError("Bitvavo client not available for live trading")

                # Build order params based on strategy
                var_sell = {'operatorId': config.OPERATOR_ID}
                if sell_params['use_amount']:
                    var_sell['amount'] = str(sell_params['amount'])
                else:
                    var_sell['amountQuote'] = str(sell_params['amountQuote'])

                logger.info(
                    f"LIVE SELL ORDER: {self.analysis_pair} | "
                    f"Strategy: {sell_params['strategy']} | "
                    f"Params: {var_sell}"
                )

                result = self.bitvavo.placeOrder(self.analysis_pair, 'sell', 'market', var_sell)

                if 'errorCode' in result:
                    error_msg = result.get('error', 'Unknown API error')
                    db.log_transaction(
                        self.coin_id, 'sell', 'market', sell_params['expected_eur'], price,
                        is_test_mode=False, status='failed', error_message=error_msg
                    )
                    return {'success': False, 'error': error_msg}

                # Log successful transaction
                transaction_id = db.log_transaction(
                    self.coin_id, 'sell', 'market', sell_params['expected_eur'], price,
                    is_test_mode=False, bitvavo_order_id=result.get('orderId'),
                    status='completed'
                )

                result['sell_params'] = sell_params  # Include for debugging

            return {'success': True, 'result': result, 'transaction_id': transaction_id, 'sell_params': sell_params}

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Sell order execution failed: {error_msg}")

            if self.coin_id:
                db.log_transaction(
                    self.coin_id, 'sell', 'market', self.transactie_bedrag, price,
                    is_test_mode=is_test_mode, status='failed', error_message=error_msg
                )

            return {'success': False, 'error': error_msg}
    
    def _execute_buy_order(self, price: float, is_test_mode: bool) -> Dict[str, Any]:
        """Execute buy order with test mode support"""
        try:
            if is_test_mode:
                # Simulate successful order in test mode
                result = {
                    'orderId': f'TEST_BUY_{self.analysis_pair}_{int(time.time())}',
                    'market': self.analysis_pair,
                    'side': 'buy',
                    'orderType': 'market',
                    'amount': str(self.transactie_bedrag),
                    'filledAmount': str(self.transactie_bedrag),
                    'fills': [{'price': str(price), 'amount': str(self.transactie_bedrag)}],
                    'status': 'filled'
                }
                transaction_id = db.log_transaction(
                    self.coin_id, 'buy', 'market', self.transactie_bedrag, price,
                    is_test_mode=True, status='test'
                )
            else:
                # Execute real order
                if not self.bitvavo:
                    raise ValueError("Bitvavo client not available for live trading")

                var_buy = {'amountQuote': str(self.transactie_bedrag), 'operatorId': config.OPERATOR_ID}
                result = self.bitvavo.placeOrder(self.analysis_pair, 'buy', 'market', var_buy)
                
                if 'errorCode' in result:
                    error_msg = result.get('error', 'Unknown API error')
                    db.log_transaction(
                        self.coin_id, 'buy', 'market', self.transactie_bedrag, price,
                        is_test_mode=False, status='failed', error_message=error_msg
                    )
                    return {'success': False, 'error': error_msg}
                
                # Log successful transaction
                transaction_id = db.log_transaction(
                    self.coin_id, 'buy', 'market', self.transactie_bedrag, price,
                    is_test_mode=False, bitvavo_order_id=result.get('orderId'),
                    status='completed'
                )
            
            return {'success': True, 'result': result, 'transaction_id': transaction_id}
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Buy order execution failed: {error_msg}")
            
            if self.coin_id:
                db.log_transaction(
                    self.coin_id, 'buy', 'market', self.transactie_bedrag, price,
                    is_test_mode=is_test_mode, status='failed', error_message=error_msg
                )
            
            return {'success': False, 'error': error_msg}
    
    def _handle_proceeds_strategy(self, sell_amount: float, is_test_mode: bool, sell_transaction_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Handle proceeds after a successful SELL based on configured strategy.

        Args:
            sell_amount: Total EUR received from SELL order
            is_test_mode: Whether to execute in test mode
            sell_transaction_id: ID of the SELL transaction (for logging)

        Returns:
            Dict with result if new BUY was placed, None if no reinvestment
        """
        # Calculate proceeds using the configured strategy
        result = proceeds_calculator.calculate(
            sell_amount=Decimal(str(sell_amount)),
            original_amount=Decimal(str(self.transactie_bedrag)),
            strategy=self.proceeds_strategy,
            crypto_ratio=self.proceeds_crypto_ratio
        )

        logger.info(
            f"PROCEEDS STRATEGY: {self.analysis_pair} | "
            f"Strategy: {result.strategy_used} | "
            f"Sell: EUR {result.sell_amount:.2f} | "
            f"Original: EUR {result.original_amount:.2f} | "
            f"Profit: EUR {result.profit:.2f} ({result.profit_percentage:.1f}%) | "
            f"New BUY: EUR {result.new_buy_amount:.2f} | "
            f"Retained EUR: EUR {result.retained_eur:.2f}"
        )

        # If no reinvestment needed, just return the result
        if result.new_buy_amount <= 0:
            logger.info(
                f"NO REINVESTMENT: {self.analysis_pair} | "
                f"Strategy '{result.strategy_used}' resulted in no new BUY | "
                f"Retained EUR: {result.retained_eur:.2f}"
            )

            # Log proceeds to database (no reinvestment case)
            if self.coin_id:
                db.log_proceeds(
                    coin_id=self.coin_id,
                    strategy_used=result.strategy_used,
                    crypto_ratio=result.crypto_ratio,
                    sell_amount=float(result.sell_amount),
                    original_amount=float(result.original_amount),
                    profit=float(result.profit),
                    profit_percentage=result.profit_percentage,
                    new_buy_amount=float(result.new_buy_amount),
                    retained_eur=float(result.retained_eur),
                    reinvestment_ratio=result.reinvestment_ratio,
                    is_test_mode=is_test_mode,
                    sell_transaction_id=sell_transaction_id,
                    min_order_applied=result.min_order_applied,
                    reinvestment_success=None  # No reinvestment attempted
                )

            return {'proceeds_result': result, 'buy_order': None}

        # Execute new BUY order with the calculated amount
        # First update transactie_bedrag to the new amount
        old_bedrag = self.transactie_bedrag
        self.transactie_bedrag = float(result.new_buy_amount)

        logger.info(
            f"PROCEEDS REINVESTMENT: {self.analysis_pair} | "
            f"Placing new BUY order for EUR {result.new_buy_amount:.2f} | "
            f"(was EUR {old_bedrag:.2f})"
        )

        # Get current ASK price for the BUY
        try:
            ask_price = float(self.get_best_ask())
        except Exception as e:
            logger.error(f"Cannot get ASK price for reinvestment: {e}")
            # Revert transactie_bedrag
            self.transactie_bedrag = old_bedrag
            return {'proceeds_result': result, 'buy_order': None, 'error': str(e)}

        # Execute the BUY order
        buy_result = self._execute_buy_order(ask_price, is_test_mode)

        if buy_result['success']:
            # Update position and state for the new BUY
            self.position = True
            self.buy_signal = False

            # Extract actual buy price from fills
            fills = buy_result.get('result', {}).get('fills', [])
            if fills:
                actual_price = float(fills[0].get('price', ask_price))
                amount = float(fills[0].get('amount', 0))
                fee = float(fills[0].get('fee', 0)) if 'fee' in fills[0] else 0
            else:
                actual_price = ask_price
                amount = 0
                fee = 0

            # Track buy price for next sell
            self.last_buy_price = actual_price

            # Reset temp values
            self.high = actual_price
            self.temp_high = actual_price
            self.low = actual_price
            self.temp_low = actual_price
            self.last_update = get_timestamp()

            logger.info(
                f"REINVESTMENT BUY EXECUTED: {self.analysis_pair} | "
                f"{'TEST' if is_test_mode else 'LIVE'} | "
                f"Amount: EUR {result.new_buy_amount:.2f} @ EUR {actual_price:,.2f} | "
                f"Retained profit: EUR {result.retained_eur:.2f}"
            )

            # Send Discord notification for the reinvestment buy
            send_buy_notification(
                coin_id=self.coin_id,
                crypto=self.analysis_pair,
                matrix_price=actual_price,  # Use actual price as new matrix
                buy_trigger=actual_price,   # Immediate buy, no trigger
                trail_buy_price=actual_price,
                actual_buy_price=actual_price,
                amount=amount,
                total=float(result.new_buy_amount),
                fee=fee,
                discount=0,
                discount_pct=0,
                order_id=buy_result.get('result', {}).get('orderId', 'N/A'),
                extra_info=f"REINVESTMENT ({result.strategy_used}): Retained EUR {result.retained_eur:.2f}"
            )

            # Save updated state
            self._save_to_database()

            # Log proceeds to database (successful reinvestment)
            if self.coin_id:
                db.log_proceeds(
                    coin_id=self.coin_id,
                    strategy_used=result.strategy_used,
                    crypto_ratio=result.crypto_ratio,
                    sell_amount=float(result.sell_amount),
                    original_amount=float(result.original_amount),
                    profit=float(result.profit),
                    profit_percentage=result.profit_percentage,
                    new_buy_amount=float(result.new_buy_amount),
                    retained_eur=float(result.retained_eur),
                    reinvestment_ratio=result.reinvestment_ratio,
                    is_test_mode=is_test_mode,
                    sell_transaction_id=sell_transaction_id,
                    buy_transaction_id=buy_result.get('transaction_id'),
                    min_order_applied=result.min_order_applied,
                    reinvestment_success=True
                )

            return {
                'proceeds_result': result,
                'buy_order': buy_result,
                'success': True
            }
        else:
            # BUY failed - revert transactie_bedrag and log error
            error_msg = buy_result.get('error', 'Unknown')
            logger.error(
                f"REINVESTMENT BUY FAILED: {self.analysis_pair} | "
                f"Error: {error_msg} | "
                f"EUR {result.new_buy_amount:.2f} remains available for manual action"
            )
            self.transactie_bedrag = old_bedrag

            # Log proceeds to database (failed reinvestment)
            if self.coin_id:
                db.log_proceeds(
                    coin_id=self.coin_id,
                    strategy_used=result.strategy_used,
                    crypto_ratio=result.crypto_ratio,
                    sell_amount=float(result.sell_amount),
                    original_amount=float(result.original_amount),
                    profit=float(result.profit),
                    profit_percentage=result.profit_percentage,
                    new_buy_amount=float(result.new_buy_amount),
                    retained_eur=float(result.retained_eur),
                    reinvestment_ratio=result.reinvestment_ratio,
                    is_test_mode=is_test_mode,
                    sell_transaction_id=sell_transaction_id,
                    min_order_applied=result.min_order_applied,
                    reinvestment_success=False,
                    error_message=error_msg
                )

            return {
                'proceeds_result': result,
                'buy_order': buy_result,
                'success': False,
                'error': error_msg
            }

    def _save_to_database(self):
        """Save current coin state to database"""
        if not self.coin_id:
            return

        coin_data = {
            'index_num': self.index,
            'base_currency': self.base_currency,
            'quote_currency': self.quote_currency,
            'position': 'Y' if self.position else 'N',
            'transactie_bedrag': self.transactie_bedrag,
            'current_price': self.current_price,
            'gain': self.gain,
            'trail': self.trail,
            'stoploss': 0.0,  # Stoploss removed, but keep for database compatibility
            'temp_high': self.temp_high,
            'temp_low': self.temp_low,
            'number_deals': self.number_deals,
            'last_update': self.last_update,
            'sleep_till': self.sleep_till,
            'last_buy_price': self.last_buy_price,
            'proceeds_strategy': self.proceeds_strategy,
            'proceeds_crypto_ratio': self.proceeds_crypto_ratio
        }

        db.save_coin(coin_data)


def get_timestamp():
    return datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')

if __name__ == '__main__':
    pass