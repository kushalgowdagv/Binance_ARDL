"""Market data aggregator for fetching and managing market data"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd
from src.utils.logger import get_logger
from src.core.exceptions import MarketDataError

class MarketDataManager:
    def __init__(self, exchange, config):
        self.exchange = exchange
        self.config = config
        self.logger = get_logger(__name__)
        self._cache = {}
        self._cache_ttl = 60  # seconds
        
    async def fetch_market_data(self, symbols: List[str]) -> Dict:
        """Fetch comprehensive market data for multiple symbols"""
        try:
            tasks = []
            for symbol in symbols:
                tasks.append(self._fetch_symbol_data(symbol))
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            market_data = {
                'timestamp': datetime.utcnow().timestamp(),
                'symbols': {}
            }
            
            for symbol, result in zip(symbols, results):
                if isinstance(result, Exception):
                    self.logger.error(f"Failed to fetch data for {symbol}: {result}")
                    continue
                market_data['symbols'][symbol] = result
                
            return market_data
            
        except Exception as e:
            raise MarketDataError(f"Failed to fetch market data: {e}")
            
    async def _fetch_symbol_data(self, symbol: str) -> Dict:
        """Fetch data for a single symbol"""
        # Check cache
        if self._is_cache_valid(symbol):
            return self._cache[symbol]['data']
            
        # Fetch fresh data
        ticker_task = self.exchange.fetch_ticker(symbol)
        ohlcv_task = self.exchange.fetch_ohlcv(symbol, '1m', limit=100)
        
        ticker, ohlcv = await asyncio.gather(ticker_task, ohlcv_task)
        
        # Process OHLCV data
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        data = {
            'ticker': ticker,
            'ohlcv': df,
            'close': df['close'].tolist(),
            'volume': df['volume'].tolist(),
            'last_price': ticker['last'],
            'bid': ticker['bid'],
            'ask': ticker['ask'],
            'spread': ticker['ask'] - ticker['bid'],
            'spread_pct': ((ticker['ask'] - ticker['bid']) / ticker['bid']) * 100
        }
        
        # Update cache
        self._cache[symbol] = {
            'data': data,
            'timestamp': datetime.utcnow()
        }
        
        return data
        
    def _is_cache_valid(self, symbol: str) -> bool:
        """Check if cache is still valid"""
        if symbol not in self._cache:
            return False
            
        cache_age = (datetime.utcnow() - self._cache[symbol]['timestamp']).total_seconds()
        return cache_age < self._cache_ttl