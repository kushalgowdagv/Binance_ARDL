from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum

class Signal(Enum):
    LONG_ENTRY = "long_entry"
    LONG_EXIT = "long_exit"
    SHORT_ENTRY = "short_entry"
    SHORT_EXIT = "short_exit"
    NEUTRAL = "neutral"

@dataclass
class TradingSignal:
    signal: Signal
    symbol: str
    price: float
    confidence: float
    timestamp: float
    metadata: dict

class Strategy(ABC):
    def __init__(self, config):
        self.config = config
        
    @abstractmethod
    async def calculate_signals(self, market_data: dict) -> List[TradingSignal]:
        pass
    
    @abstractmethod
    def validate_signal(self, signal: TradingSignal) -> bool:
        pass