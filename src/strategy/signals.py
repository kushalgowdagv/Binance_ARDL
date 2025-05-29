# src/strategy/signals.py
"""Signal generation and management"""

from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import asyncio
from collections import deque
from src.strategy.base import TradingSignal, Signal
from src.utils.logger import get_logger

@dataclass
class SignalFilter:
    """Filter for signal validation"""
    name: str
    condition: Callable[[TradingSignal], bool]
    description: str = ""
    
class SignalHistory:
    """Manages signal history and statistics"""
    
    def __init__(self, max_history: int = 1000):
        self.signals: deque = deque(maxlen=max_history)
        self.stats = {
            'total_signals': 0,
            'signals_by_type': {},
            'signals_by_symbol': {},
            'average_confidence': 0.0,
            'win_rate': 0.0
        }
        
    def add_signal(self, signal: TradingSignal, executed: bool = False, 
                  profitable: Optional[bool] = None):
        """Add a signal to history"""
        self.signals.append({
            'signal': signal,
            'timestamp': datetime.utcnow(),
            'executed': executed,
            'profitable': profitable
        })
        self._update_stats()
        
    def _update_stats(self):
        """Update signal statistics"""
        if not self.signals:
            return
            
        self.stats['total_signals'] = len(self.signals)
        
        # Count by type
        signals_by_type = {}
        signals_by_symbol = {}
        total_confidence = 0.0
        executed_count = 0
        profitable_count = 0
        
        for record in self.signals:
            signal = record['signal']
            
            # By type
            signal_type = signal.signal.value
            signals_by_type[signal_type] = signals_by_type.get(signal_type, 0) + 1
            
            # By symbol
            signals_by_symbol[signal.symbol] = signals_by_symbol.get(signal.symbol, 0) + 1
            
            # Confidence
            total_confidence += signal.confidence
            
            # Win rate
            if record['executed']:
                executed_count += 1
                if record['profitable']:
                    profitable_count += 1
                    
        self.stats['signals_by_type'] = signals_by_type
        self.stats['signals_by_symbol'] = signals_by_symbol
        self.stats['average_confidence'] = total_confidence / len(self.signals)
        
        if executed_count > 0:
            self.stats['win_rate'] = profitable_count / executed_count
            
    def get_recent_signals(self, minutes: int = 60) -> List[Dict]:
        """Get signals from the last N minutes"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        return [
            record for record in self.signals 
            if record['timestamp'] > cutoff_time
        ]
        
    def get_signal_frequency(self, symbol: str, signal_type: Signal) -> float:
        """Get frequency of signals per hour"""
        if not self.signals:
            return 0.0
            
        # Get time span
        oldest = self.signals[0]['timestamp']
        newest = self.signals[-1]['timestamp']
        hours = (newest - oldest).total_seconds() / 3600
        
        if hours == 0:
            return 0.0
            
        # Count matching signals
        count = sum(
            1 for record in self.signals
            if record['signal'].symbol == symbol and 
               record['signal'].signal == signal_type
        )
        
        return count / hours

class SignalAggregator:
    """Aggregates signals from multiple strategies"""
    
    def __init__(self, min_consensus: float = 0.6):
        self.logger = get_logger(__name__)
        self.min_consensus = min_consensus
        self.strategies: List[Any] = []
        self.filters: List[SignalFilter] = []
        self.history = SignalHistory()
        
    def add_strategy(self, strategy):
        """Add a strategy to the aggregator"""
        self.strategies.append(strategy)
        
    def add_filter(self, filter: SignalFilter):
        """Add a signal filter"""
        self.filters.append(filter)
        
    async def get_signals(self, market_data: Dict) -> List[TradingSignal]:
        """Get aggregated signals from all strategies"""
        all_signals = []
        
        # Collect signals from all strategies
        for strategy in self.strategies:
            try:
                signals = await strategy.calculate_signals(market_data)
                all_signals.extend(signals)
            except Exception as e:
                self.logger.error(f"Error getting signals from {strategy.__class__.__name__}: {e}")
                
        # Filter signals
        filtered_signals = self._filter_signals(all_signals)
        
        # Aggregate if multiple strategies agree
        aggregated = self._aggregate_signals(filtered_signals)
        
        # Add to history
        for signal in aggregated:
            self.history.add_signal(signal)
            
        return aggregated
        
    def _filter_signals(self, signals: List[TradingSignal]) -> List[TradingSignal]:
        """Apply filters to signals"""
        filtered = []
        
        for signal in signals:
            passed = True
            for filter in self.filters:
                if not filter.condition(signal):
                    self.logger.debug(f"Signal filtered by {filter.name}: {signal}")
                    passed = False
                    break
                    
            if passed:
                filtered.append(signal)
                
        return filtered
        
    def _aggregate_signals(self, signals: List[TradingSignal]) -> List[TradingSignal]:
        """Aggregate signals by consensus"""
        if len(self.strategies) == 1:
            return signals
            
        # Group signals by symbol and type
        signal_groups = {}
        for signal in signals:
            key = (signal.symbol, signal.signal)
            if key not in signal_groups:
                signal_groups[key] = []
            signal_groups[key].append(signal)
            
        # Check consensus
        aggregated = []
        for (symbol, signal_type), group in signal_groups.items():
            consensus = len(group) / len(self.strategies)
            
            if consensus >= self.min_consensus:
                # Create aggregated signal
                avg_confidence = sum(s.confidence for s in group) / len(group)
                avg_price = sum(s.price for s in group) / len(group)
                
                aggregated_signal = TradingSignal(
                    signal=signal_type,
                    symbol=symbol,
                    price=avg_price,
                    confidence=avg_confidence * consensus,
                    timestamp=datetime.utcnow().timestamp(),
                    metadata={
                        'consensus': consensus,
                        'strategies_count': len(group),
                        'original_signals': [s.metadata for s in group]
                    }
                )
                aggregated.append(aggregated_signal)
                
        return aggregated

# Pre-defined signal filters
class CommonFilters:
    """Common signal filters"""
    
    @staticmethod
    def min_confidence(threshold: float = 0.7) -> SignalFilter:
        """Filter signals below confidence threshold"""
        return SignalFilter(
            name="min_confidence",
            condition=lambda s: s.confidence >= threshold,
            description=f"Minimum confidence {threshold}"
        )
        
    @staticmethod
    def time_window(start_hour: int = 0, end_hour: int = 24) -> SignalFilter:
        """Filter signals outside time window"""
        def condition(signal: TradingSignal) -> bool:
            hour = datetime.fromtimestamp(signal.timestamp).hour
            if start_hour <= end_hour:
                return start_hour <= hour < end_hour
            else:  # Overnight window
                return hour >= start_hour or hour < end_hour
                
        return SignalFilter(
            name="time_window",
            condition=condition,
            description=f"Time window {start_hour}-{end_hour}"
        )
        
    @staticmethod
    def no_recent_signal(minutes: int = 5) -> SignalFilter:
        """Filter if similar signal was recently generated"""
        recent_signals = {}
        
        def condition(signal: TradingSignal) -> bool:
            key = (signal.symbol, signal.signal)
            current_time = signal.timestamp
            
            if key in recent_signals:
                last_time = recent_signals[key]
                if current_time - last_time < minutes * 60:
                    return False
                    
            recent_signals[key] = current_time
            return True
            
        return SignalFilter(
            name="no_recent_signal",
            condition=condition,
            description=f"No signal in last {minutes} minutes"
        )