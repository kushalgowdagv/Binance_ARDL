# src/data/klines.py
"""Kline (candlestick) data management"""

import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from collections import defaultdict
from src.utils.logger import get_logger
from src.core.exceptions import MarketDataError

class KlineData:
    """Container for kline data with analysis methods"""
    
    def __init__(self, symbol: str, interval: str, data: pd.DataFrame):
        self.symbol = symbol
        self.interval = interval
        self.data = data
        self._indicators = {}
        
    def get_latest(self) -> Dict:
        """Get the latest kline"""
        if self.data.empty:
            return {}
        return self.data.iloc[-1].to_dict()
        
    def get_close_prices(self, limit: Optional[int] = None) -> np.ndarray:
        """Get close prices as numpy array"""
        if limit:
            return self.data['close'].tail(limit).values
        return self.data['close'].values
        
    def calculate_returns(self, periods: int = 1) -> pd.Series:
        """Calculate percentage returns"""
        return self.data['close'].pct_change(periods) * 100
        
    def calculate_volatility(self, window: int = 20) -> float:
        """Calculate rolling volatility"""
        returns = self.data['close'].pct_change()
        return returns.rolling(window=window).std().iloc[-1] * np.sqrt(252)
        
    def calculate_sma(self, period: int) -> pd.Series:
        """Calculate Simple Moving Average"""
        key = f'sma_{period}'
        if key not in self._indicators:
            self._indicators[key] = self.data['close'].rolling(window=period).mean()
        return self._indicators[key]
        
    def calculate_ema(self, period: int) -> pd.Series:
        """Calculate Exponential Moving Average"""
        key = f'ema_{period}'
        if key not in self._indicators:
            self._indicators[key] = self.data['close'].ewm(span=period, adjust=False).mean()
        return self._indicators[key]
        
    def calculate_rsi(self, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index"""
        key = f'rsi_{period}'
        if key not in self._indicators:
            delta = self.data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            self._indicators[key] = 100 - (100 / (1 + rs))
        return self._indicators[key]
        
    def calculate_bollinger_bands(self, period: int = 20, num_std: float = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands"""
        sma = self.calculate_sma(period)
        std = self.data['close'].rolling(window=period).std()
        upper = sma + (std * num_std)
        lower = sma - (std * num_std)
        return upper, sma, lower

class KlineManager:
    """Manages kline data fetching and caching"""
    
    def __init__(self, exchange, config):
        self.exchange = exchange
        self.config = config
        self.logger = get_logger(__name__)
        self._kline_cache: Dict[str, Dict[str, KlineData]] = defaultdict(dict)
        self._update_tasks: Dict[str, asyncio.Task] = {}
        
    async def fetch_klines(self, symbol: str, interval: str = '1m', 
                          limit: int = 100) -> KlineData:
        """Fetch kline data for a symbol"""
        try:
            # Fetch from exchange
            ohlcv = await self.exchange.fetch_ohlcv(symbol, interval, limit=limit)
            
            # Convert to DataFrame
            df = pd.DataFrame(
                ohlcv, 
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Create KlineData object
            kline_data = KlineData(symbol, interval, df)
            
            # Update cache
            self._kline_cache[symbol][interval] = kline_data
            
            return kline_data
            
        except Exception as e:
            self.logger.error(f"Failed to fetch klines for {symbol}: {e}")
            raise MarketDataError(f"Failed to fetch klines: {e}")
            
    async def fetch_historical_klines(self, symbol: str, interval: str,
                                    start_time: datetime, end_time: datetime) -> KlineData:
        """Fetch historical kline data"""
        try:
            all_klines = []
            current_time = start_time
            
            while current_time < end_time:
                # Fetch batch
                since = int(current_time.timestamp() * 1000)
                ohlcv = await self.exchange.fetch_ohlcv(
                    symbol, interval, since=since, limit=1000
                )
                
                if not ohlcv:
                    break
                    
                all_klines.extend(ohlcv)
                
                # Update current time to last kline timestamp
                last_timestamp = ohlcv[-1][0]
                current_time = datetime.fromtimestamp(last_timestamp / 1000)
                
                # Add small delay to avoid rate limits
                await asyncio.sleep(0.1)
                
            # Convert to DataFrame
            df = pd.DataFrame(
                all_klines,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Remove duplicates
            df = df[~df.index.duplicated(keep='first')]
            
            # Filter by end time
            df = df[df.index <= end_time]
            
            return KlineData(symbol, interval, df)
            
        except Exception as e:
            self.logger.error(f"Failed to fetch historical klines: {e}")
            raise MarketDataError(f"Failed to fetch historical klines: {e}")
            
    async def start_streaming(self, symbols: List[str], interval: str = '1m',
                            update_interval: float = 60):
        """Start streaming kline updates"""
        for symbol in symbols:
            key = f"{symbol}_{interval}"
            if key not in self._update_tasks:
                task = asyncio.create_task(
                    self._stream_klines(symbol, interval, update_interval)
                )
                self._update_tasks[key] = task
                
    async def stop_streaming(self):
        """Stop all streaming tasks"""
        for task in self._update_tasks.values():
            task.cancel()
        await asyncio.gather(*self._update_tasks.values(), return_exceptions=True)
        self._update_tasks.clear()
        
    async def _stream_klines(self, symbol: str, interval: str, update_interval: float):
        """Stream kline updates for a symbol"""
        while True:
            try:
                await self.fetch_klines(symbol, interval)
                await asyncio.sleep(update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error streaming klines for {symbol}: {e}")
                await asyncio.sleep(update_interval * 2)
                
    def get_klines(self, symbol: str, interval: str = '1m') -> Optional[KlineData]:
        """Get cached kline data"""
        return self._kline_cache.get(symbol, {}).get(interval)
        
    def calculate_spread_percentage(self, symbol1: str, symbol2: str, 
                                  interval: str = '1m') -> Optional[float]:
        """Calculate percentage spread between two symbols"""
        klines1 = self.get_klines(symbol1, interval)
        klines2 = self.get_klines(symbol2, interval)
        
        if not klines1 or not klines2:
            return None
            
        # Get latest close prices
        close1_current = klines1.data['close'].iloc[-1]
        close1_prev = klines1.data['close'].iloc[-2] if len(klines1.data) > 1 else close1_current
        
        close2_current = klines2.data['close'].iloc[-1]
        close2_prev = klines2.data['close'].iloc[-2] if len(klines2.data) > 1 else close2_current
        
        # Calculate percentage changes
        pct_change1 = ((close1_current - close1_prev) / close1_prev) * 100
        pct_change2 = ((close2_current - close2_prev) / close2_prev) * 100
        
        return pct_change2 - pct_change1
        
    def get_aligned_data(self, symbols: List[str], interval: str = '1m') -> pd.DataFrame:
        """Get aligned kline data for multiple symbols"""
        dfs = []
        
        for symbol in symbols:
            klines = self.get_klines(symbol, interval)
            if klines:
                df = klines.data[['close']].copy()
                df.columns = [f"{symbol}_close"]
                dfs.append(df)
                
        if not dfs:
            return pd.DataFrame()
            
        # Align all dataframes on timestamp
        aligned = pd.concat(dfs, axis=1, join='inner')
        return aligned