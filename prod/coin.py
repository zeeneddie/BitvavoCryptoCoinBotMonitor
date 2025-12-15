import datetime
import time
import logging
import os
from collections import defaultdict
from typing import Optional, Dict, Any

from config import config
from database import db
from trade_discord_notifier import send_sell_notification, send_buy_notification

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

                        # Pas transactie_bedrag aan met ECHTE gemaakte winst
                        if self.last_buy_price > 0:
                            werkelijke_winst = (actual_price - self.last_buy_price) / self.last_buy_price
                            old_bedrag = self.transactie_bedrag
                            self.transactie_bedrag = round(self.transactie_bedrag * (1 + werkelijke_winst), 2)

                            logger.info(
                                f"💰 BEDRAG GEGROEID: Buy €{self.last_buy_price:,.2f} → Sell €{actual_price:,.2f} | "
                                f"Winst {werkelijke_winst*100:.2f}% | "
                                f"Bedrag €{old_bedrag:,.2f} → €{self.transactie_bedrag:,.2f}"
                            )
                        else:
                            # Fallback: Query database voor laatste buy prijs
                            cursor = self.conn.cursor()
                            cursor.execute("""
                                SELECT price FROM transactions
                                WHERE coin_id = ? AND transaction_type = 'buy'
                                ORDER BY created_at DESC LIMIT 1
                            """, (self.coin_id,))
                            result = cursor.fetchone()
                            
                            if result:
                                last_buy_from_db = result[0]
                                werkelijke_winst = (actual_price - last_buy_from_db) / last_buy_from_db
                                old_bedrag = self.transactie_bedrag
                                self.transactie_bedrag = round(self.transactie_bedrag * (1 + werkelijke_winst), 2)
                                
                                logger.info(
                                    f"💰 BEDRAG GEGROEID (via DB): Buy €{last_buy_from_db:,.2f} → Sell €{actual_price:,.2f} | "
                                    f"Winst {werkelijke_winst*100:.2f}% | "
                                    f"Bedrag €{old_bedrag:,.2f} → €{self.transactie_bedrag:,.2f}"
                                )
                            else:
                                # Echte fallback: geen buy transactie gevonden
                                self.transactie_bedrag = round(self.transactie_bedrag * 1.01, 2)
                                logger.warning(f"⚠️ Geen buy transactie gevonden voor coin {self.coin_id}, gebruik 1% groei")

                        self.sell_signal = False
                        self.position = False
                        # Reset beide temp waarden naar matrix_price (schone lei)
                        self.low = self.current_price
                        self.temp_low = self.low
                        self.high = self.current_price
                        self.temp_high = self.high
                        self.last_update = get_timestamp()
                        self.number_deals += 1

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
    
    def _execute_sell_order(self, price: float, is_test_mode: bool) -> Dict[str, Any]:
        """Execute sell order with test mode support"""
        try:
            if is_test_mode:
                # Simulate successful order in test mode
                result = {
                    'orderId': f'TEST_SELL_{self.analysis_pair}_{int(time.time())}',
                    'market': self.analysis_pair,
                    'side': 'sell',
                    'orderType': 'market',
                    'amount': str(self.transactie_bedrag),
                    'filledAmount': str(self.transactie_bedrag),
                    'fills': [{'price': str(price), 'amount': str(self.transactie_bedrag)}],
                    'status': 'filled'
                }
                transaction_id = db.log_transaction(
                    self.coin_id, 'sell', 'market', self.transactie_bedrag, price,
                    is_test_mode=True, status='test'
                )
            else:
                # Execute real order
                if not self.bitvavo:
                    raise ValueError("Bitvavo client not available for live trading")

                var_sell = {'amountQuote': str(self.transactie_bedrag), 'operatorId': config.OPERATOR_ID}
                result = self.bitvavo.placeOrder(self.analysis_pair, 'sell', 'market', var_sell)
                
                if 'errorCode' in result:
                    error_msg = result.get('error', 'Unknown API error')
                    db.log_transaction(
                        self.coin_id, 'sell', 'market', self.transactie_bedrag, price,
                        is_test_mode=False, status='failed', error_message=error_msg
                    )
                    return {'success': False, 'error': error_msg}
                
                # Log successful transaction
                transaction_id = db.log_transaction(
                    self.coin_id, 'sell', 'market', self.transactie_bedrag, price,
                    is_test_mode=False, bitvavo_order_id=result.get('orderId'),
                    status='completed'
                )
            
            return {'success': True, 'result': result, 'transaction_id': transaction_id}
            
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
            'last_buy_price': self.last_buy_price
        }

        db.save_coin(coin_data)


def get_timestamp():
    return datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')

if __name__ == '__main__':
    pass