"""Order book data management"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import asyncio
from src.utils.logger import get_logger
from src.utils.retry import retry_async

@dataclass
class OrderBookLevel:
    price: float
    quantity: float
    
@dataclass
class OrderBook:
    symbol: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    timestamp: float
    
    def get_best_bid(self) -> Optional[OrderBookLevel]:
        return self.bids[0] if self.bids else None
        
    def get_best_ask(self) -> Optional[OrderBookLevel]:
        return self.asks[0] if self.asks else None
        
    def get_mid_price(self) -> Optional[float]:
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return (best_bid.price + best_ask.price) / 2
        return None
        
    def get_spread(self) -> Optional[float]:
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return best_ask.price - best_bid.price
        return None

class OrderBookManager:
    def __init__(self, exchange):
        self.exchange = exchange
        self.logger = get_logger(__name__)
        self._order_books: Dict[str, OrderBook] = {}
        self._update_tasks: Dict[str, asyncio.Task] = {}
        
    @retry_async(max_attempts=3, delay=1)
    async def fetch_order_book(self, symbol: str, limit: int = 10) -> OrderBook:
        """Fetch order book for a symbol"""
        try:
            raw_order_book = await self.exchange.fetch_order_book(symbol, limit)
            
            # Convert to OrderBook object
            order_book = OrderBook(
                symbol=symbol,
                bids=[OrderBookLevel(price=bid[0], quantity=bid[1]) 
                      for bid in raw_order_book['bids']],
                asks=[OrderBookLevel(price=ask[0], quantity=ask[1]) 
                      for ask in raw_order_book['asks']],
                timestamp=raw_order_book['timestamp']
            )
            
            self._order_books[symbol] = order_book
            return order_book
            
        except Exception as e:
            self.logger.error(f"Failed to fetch order book for {symbol}: {e}")
            raise
            
    async def start_streaming(self, symbols: List[str], update_interval: float = 1.0):
        """Start streaming order book updates for multiple symbols"""
        for symbol in symbols:
            if symbol not in self._update_tasks:
                task = asyncio.create_task(
                    self._stream_order_book(symbol, update_interval)
                )
                self._update_tasks[symbol] = task
                
    async def stop_streaming(self):
        """Stop all streaming tasks"""
        for task in self._update_tasks.values():
            task.cancel()
        await asyncio.gather(*self._update_tasks.values(), return_exceptions=True)
        self._update_tasks.clear()
        
    async def _stream_order_book(self, symbol: str, update_interval: float):
        """Stream order book updates for a symbol"""
        while True:
            try:
                await self.fetch_order_book(symbol)
                await asyncio.sleep(update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error streaming order book for {symbol}: {e}")
                await asyncio.sleep(update_interval * 2)  # Back off on error
                
    def get_order_book(self, symbol: str) -> Optional[OrderBook]:
        """Get cached order book"""
        return self._order_books.get(symbol)
        
    def get_execution_price(self, symbol: str, side: str, 
                          amount: float) -> Optional[float]:
        """Calculate execution price for a given amount"""
        order_book = self.get_order_book(symbol)
        if not order_book:
            return None
            
        levels = order_book.asks if side == 'buy' else order_book.bids
        remaining_amount = amount
        total_cost = 0.0
        
        for level in levels:
            if remaining_amount <= 0:
                break
                
            fill_amount = min(remaining_amount, level.quantity)
            total_cost += fill_amount * level.price
            remaining_amount -= fill_amount
            
        if remaining_amount > 0:
            # Not enough liquidity
            return None
            
        return total_cost / amount