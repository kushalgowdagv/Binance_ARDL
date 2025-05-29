from typing import List
import numpy as np
from .base import Strategy, TradingSignal, Signal

class SpreadTradingStrategy(Strategy):
    def __init__(self, config):
        super().__init__(config)
        self.prev_pct_diff = 0
        self.position_state = None
        
    async def calculate_signals(self, market_data: dict) -> List[TradingSignal]:
        signals = []
        
        # Extract data
        perp_data = market_data['ETHUSDT']
        futures_data = market_data['ETHUSDT_240927']
        
        # Calculate percentage difference
        pct_diff = self._calculate_spread_percentage(perp_data, futures_data)
        
        # Generate signals based on thresholds
        if self.prev_pct_diff <= -0.1 and pct_diff <= -0.06 and not self._has_long_position():
            signals.append(TradingSignal(
                signal=Signal.LONG_ENTRY,
                symbol='ETH/USDT:USDT-240927',
                price=market_data['order_book']['bids'][1][0],
                confidence=0.8,
                timestamp=market_data['timestamp'],
                metadata={'spread_pct': pct_diff}
            ))
            
        elif pct_diff >= 0.04 and self._has_long_position():
            signals.append(TradingSignal(
                signal=Signal.LONG_EXIT,
                symbol='ETH/USDT:USDT-240927',
                price=market_data['order_book']['asks'][3][0],
                confidence=0.8,
                timestamp=market_data['timestamp'],
                metadata={'spread_pct': pct_diff}
            ))
            
        self.prev_pct_diff = pct_diff
        return signals
    
    def _calculate_spread_percentage(self, perp_data, futures_data):
        if len(perp_data['close']) > 1 and len(futures_data['close']) > 1:
            pct_change1 = ((perp_data['close'][-1] - perp_data['close'][-2]) / 
                          perp_data['close'][-2]) * 100
            pct_change2 = ((futures_data['close'][-1] - futures_data['close'][-2]) / 
                          futures_data['close'][-2]) * 100
            return pct_change2 - pct_change1
        return None