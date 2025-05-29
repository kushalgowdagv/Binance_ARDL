"""Data models for state management"""

from dataclasses import dataclass, asdict
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum
import json

class SerializableModel:
    """Base class for serializable models"""
    
    def to_dict(self) -> dict:
        """Convert model to dictionary"""
        return asdict(self)
        
    def to_json(self) -> str:
        """Convert model to JSON string"""
        return json.dumps(self.to_dict(), default=str)
        
    @classmethod
    def from_dict(cls, data: dict):
        """Create model instance from dictionary"""
        return cls(**data)
        
    @classmethod
    def from_json(cls, json_str: str):
        """Create model instance from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)

@dataclass
class OrderState(SerializableModel):
    """Order state model"""
    id: str
    symbol: str
    side: str
    order_type: str
    amount: float
    price: Optional[float]
    status: str
    exchange_order_id: Optional[str] = None
    filled_amount: float = 0.0
    average_price: float = 0.0
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
            
    def to_dict(self) -> dict:
        data = super().to_dict()
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data
        
    @classmethod
    def from_dict(cls, data: dict):
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)

@dataclass
class PositionState(SerializableModel):
    """Position state model"""
    symbol: str
    side: str
    entry_price: float
    amount: float
    entry_time: datetime
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    status: str = 'open'
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data['entry_time'] = self.entry_time.isoformat()
        if self.exit_time:
            data['exit_time'] = self.exit_time.isoformat()
        return data
        
    @classmethod
    def from_dict(cls, data: dict):
        data['entry_time'] = datetime.fromisoformat(data['entry_time'])
        if data.get('exit_time'):
            data['exit_time'] = datetime.fromisoformat(data['exit_time'])
        return cls(**data)

@dataclass
class TradeState(SerializableModel):
    """Trade state model"""
    id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    amount: float
    pnl: float
    entry_time: datetime
    exit_time: datetime
    entry_order_id: str
    exit_order_id: str
    strategy: str
    metadata: Dict = None
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data['entry_time'] = self.entry_time.isoformat()
        data['exit_time'] = self.exit_time.isoformat()
        return data
        
    @classmethod
    def from_dict(cls, data: dict):
        data['entry_time'] = datetime.fromisoformat(data['entry_time'])
        data['exit_time'] = datetime.fromisoformat(data['exit_time'])
        return cls(**data)

@dataclass
class StrategyState(SerializableModel):
    """Strategy state model"""
    name: str
    active: bool
    last_signal_time: Optional[datetime] = None
    total_signals: int = 0
    total_trades: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    metadata: Dict = None
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        if self.last_signal_time:
            data['last_signal_time'] = self.last_signal_time.isoformat()
        return data
        
    @classmethod
    def from_dict(cls, data: dict):
        if data.get('last_signal_time'):
            data['last_signal_time'] = datetime.fromisoformat(data['last_signal_time'])
        return cls(**data)