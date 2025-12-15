from python_bitvavo_api.bitvavo import Bitvavo
import os
import logging
import requests
import time
from typing import Dict, List, Optional
from config import config

logger = logging.getLogger(__name__)

class Bitvavo_client():
    def __init__(self):
        """Initialize Bitvavo client with proper error handling and public API fallback"""
        self.bitvavo = None
        self.api_key = None
        self.api_secret = None
        self.use_public_api = False
        
        # Setup for public API fallback
        self.public_api_url = "https://api.bitvavo.com/v2"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self._ticker_cache = {}
        self._cache_timestamp = 0
        self._cycle_id = None  # Track current trading cycle
        
        try:
            # Get API credentials from config/environment
            self.api_key = config.BITVAVO_API_KEY
            self.api_secret = config.BITVAVO_API_SECRET
            
            # Initialize client for market data reading (always) and trading (live mode only)
            if self.api_key and self.api_secret:
                try:
                    self.bitvavo = Bitvavo({
                        'APIKEY': self.api_key,
                        'APISECRET': self.api_secret,
                        'RESTURL': 'https://api.bitvavo.com/v2',
                        'WSURL': 'wss://ws.bitvavo.com/v2/',
                        'ACCESSWINDOW': 10000,
                        'DEBUGGING': False
                    })
                    if config.is_test_mode():
                        logger.info("Bitvavo client initialized for TEST MODE - market data reading only")
                    else:
                        logger.info("Bitvavo client initialized for LIVE trading")
                except Exception as e:
                    logger.error(f"Failed to initialize Bitvavo client: {e}")
                    self.bitvavo = None
            else:
                # For test mode, allow using public API without credentials
                if config.is_test_mode():
                    logger.info("No API credentials found - using public API for TEST MODE")
                    logger.info("This allows testing with real price data but no trading capabilities")
                    self.use_public_api = True
                else:
                    logger.error("ERROR: Bitvavo API credentials required for live trading")
                    logger.error("Set BITVAVOAPIKEY and BITVAVOSECKEY in .env file")
                    raise ValueError("Missing Bitvavo API credentials - cannot trade in live mode")
                
        except ValueError:
            # Re-raise ValueError for missing credentials in live mode
            raise
        except Exception as e:
            logger.error(f"Error during Bitvavo client initialization: {e}")
            self.bitvavo = None
            raise
    
    def is_available(self) -> bool:
        """Check if Bitvavo client is available for trading (not market data)"""
        return self.bitvavo is not None and not config.is_test_mode()
    
    def can_read_market_data(self) -> bool:
        """Check if Bitvavo client can read market data"""
        return self.bitvavo is not None or self.use_public_api
    
    def _get_public_ticker_data(self, force_refresh: bool = False) -> Optional[List[Dict]]:
        """Get 24h ticker data from public API with optimized caching"""
        current_time = time.time()
        
        # Use cache if data is less than 2 seconds old (unless force refresh)
        cache_age = current_time - self._cache_timestamp
        if not force_refresh and cache_age < 2.0 and self._ticker_cache:
            logger.debug(f"Using cached ticker data (age: {cache_age:.1f}s)")
            return self._ticker_cache.get('data')
        
        try:
            logger.debug(f"Fetching fresh ticker data from public API (cache age: {cache_age:.1f}s)")
            url = f"{self.public_api_url}/ticker/24h"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Update cache
            self._ticker_cache = {'data': data}
            self._cache_timestamp = current_time
            
            logger.info(f"Retrieved {len(data)} tickers from public API")
            return data
            
        except Exception as e:
            logger.error(f"Failed to get public ticker data: {e}")
            # Return stale cache if available
            if self._ticker_cache:
                logger.warning(f"Using stale cache data (age: {cache_age:.1f}s)")
                return self._ticker_cache.get('data')
            return None
    
    def _get_public_ticker(self, market: str) -> Optional[Dict]:
        """Get ticker data for specific market from public API"""
        try:
            all_data = self._get_public_ticker_data()
            if not all_data:
                return None
            
            for ticker in all_data:
                if ticker.get('market') == market:
                    return ticker
            
            logger.warning(f"Market {market} not found in public ticker data")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get ticker for {market}: {e}")
            return None
    
    def book(self, market: str, options: Dict = None) -> Dict:
        """Get orderbook data - fallback to public API if needed"""
        if self.bitvavo is not None:
            # Use authenticated API
            try:
                return self.bitvavo.book(market, options or {})
            except Exception as e:
                logger.error(f"Authenticated book API failed: {e}")
                # Fall through to public API
        
        if self.use_public_api:
            # Use public API ticker data as fallback
            try:
                ticker = self._get_public_ticker(market)
                if ticker:
                    # Convert ticker data to book format
                    return {
                        'market': market,
                        'bids': [[ticker.get('bid', '0'), ticker.get('bidSize', '0')]],
                        'asks': [[ticker.get('ask', '0'), ticker.get('askSize', '0')]],
                        'nonce': int(time.time() * 1000)
                    }
                else:
                    return {'error': f'Market {market} not found'}
            except Exception as e:
                logger.error(f"Public API book fallback failed: {e}")
                return {'error': f'Failed to get book data: {e}'}
        
        return {'error': 'No API available for market data'}
    
    def start_new_cycle(self, cycle_id: int = None):
        """Start a new trading cycle - forces cache refresh on next request"""
        if cycle_id != self._cycle_id:
            self._cycle_id = cycle_id
            logger.debug(f"Starting new trading cycle {cycle_id} - cache will refresh on next request")
    
    def get_cycle_cached_data(self, cycle_id: int = None) -> Optional[List[Dict]]:
        """Get ticker data with cycle-aware caching"""
        # If this is a new cycle, force refresh
        force_refresh = (cycle_id is not None and cycle_id != self._cycle_id)
        
        if force_refresh:
            self._cycle_id = cycle_id
            logger.debug(f"New cycle {cycle_id} detected - forcing cache refresh")
        
        return self._get_public_ticker_data(force_refresh=force_refresh)


if __name__ == "__main__":
    # SAFE TEST CODE - No real orders
    bitvavo = Bitvavo_client()
    
    print(f"Test mode: {config.is_test_mode()}")
    print(f"Can read market data: {bitvavo.can_read_market_data()}")
    print(f"Use public API: {bitvavo.use_public_api}")
    print()
    
    if bitvavo.can_read_market_data():
        print("Testing market data access...")
        
        # Test market data (safe operations)
        try:
            response = bitvavo.book('BTC-EUR', {'depth': '1'})
            if 'error' not in response:
                print(f"SUCCESS: Market data access working")
                print(f"BTC-EUR best bid: €{response['bids'][0][0]}")
                print(f"BTC-EUR best ask: €{response['asks'][0][0]}")
                
                if bitvavo.use_public_api:
                    print("SUCCESS: Using public API - perfect for test mode!")
                else:
                    print("SUCCESS: Using authenticated API")
            else:
                print(f"ERROR: API error: {response['error']}")
        except Exception as e:
            print(f"ERROR: Connection failed: {e}")
    
    if bitvavo.is_available():
        print("\nWARNING: Live trading mode detected!")
        print("Real orders can be placed - use with caution")
    else:
        print("\nSUCCESS: Safe mode - no real trades will be executed")
        if config.is_test_mode():
            print("   This is test mode - perfect for testing")
        else:
            print("   Set BITVAVOAPIKEY and BITVAVOSECKEY to enable live trading")