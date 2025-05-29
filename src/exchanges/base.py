from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import asyncio

class ExchangeInterface(ABC):
    @abstractmethod
    async def connect(self):
        pass
    
    @abstractmethod
    async def disconnect(self):
        pass
    
    @abstractmethod
    async def fetch_balance(self) -> Dict:
        pass
    
    @abstractmethod
    async def fetch_order_book(self, symbol: str, limit: int) -> Dict:
        pass
    
    @abstractmethod
    async def create_order(self, symbol: str, order_type: str, 
                          side: str, amount: float, price: Optional[float]) -> Dict:
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        pass
    
    @abstractmethod
    async def fetch_open_orders(self, symbol: str) -> List[Dict]:
        pass
    
    @abstractmethod
    async def fetch_positions(self) -> List[Dict]:
        pass