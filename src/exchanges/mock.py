"""Mock exchange for testing and development"""

import asyncio
import random
from typing import Dict, List, Optional
from datetime import datetime
import uuid
from src.exchanges.base import ExchangeInterface
from src.utils.logger import get_logger

class MockExchange(ExchangeInterface):
    """Mock exchange implementation for testing"""
    
    def __init__(self, config):
        self.config = config
        self.logger = get_logger(__name__)
        self._connected = False
        
        # Mock data
        self._balance = {
            'USDT': {'free': 10000.0, 'used': 0.0, 'total': 10000.0}
        }
        self._positions = {}
        self._orders = {}
        self._order_books = {}
        self._last_prices = {
            'ETH/USDT:USDT': 2500.0,
            'ETH/USDT:USDT-240927': 2505.0
        }
        
    async def connect(self):
        """Simulate connection"""
        await asyncio.sleep(0.1)  # Simulate network delay
        self._connected = True
        self.logger.info("Connected to mock exchange")
        
    async def disconnect(self):
        """Simulate disconnection"""
        self._connected = False
        self.logger.info("Disconnected from mock exchange")
        
    async def fetch_balance(self) -> Dict:
        """Return mock balance"""
        self._check_connected()
        await asyncio.sleep(0.05)  # Simulate API delay
        
        return {
            'free': self._balance,
            'used': {'USDT': self._balance['USDT']['used']},
            'total': {'USDT': self._balance['USDT']['total']},
            'USDT': self._balance['USDT']
        }
        
    async def fetch_order_book(self, symbol: str, limit: int = 10) -> Dict:
        """Generate mock order book"""
        self._check_connected()
        await asyncio.sleep(0.05)
        
        base_price = self._last_prices.get(symbol, 2500.0)
        spread = 0.02  # 0.02% spread
        
        bids = []
        asks = []
        
        for i in range(limit):
            bid_price = base_price * (1 - spread/100 - i * 0.001)
            ask_price = base_price * (1 + spread/100 + i * 0.001)
            
            bid_size = random.uniform(0.1, 2.0)
            ask_size = random.uniform(0.1, 2.0)
            
            bids.append([bid_price, bid_size])
            asks.append([ask_price, ask_size])
            
        return {
            'symbol': symbol,
            'bids': bids,
            'asks': asks,
            'timestamp': int(datetime.utcnow().timestamp() * 1000),
            'datetime': datetime.utcnow().isoformat()
        }
        
    async def create_order(self, symbol: str, order_type: str, 
                          side: str, amount: float, 
                          price: Optional[float] = None) -> Dict:
        """Simulate order creation"""
        self._check_connected()
        await asyncio.sleep(0.1)
        
        order_id = str(uuid.uuid4())
        
        # Simulate order placement
        order = {
            'id': order_id,
            'symbol': symbol,
            'type': order_type,
            'side': side,
            'amount': amount,
            'price': price or self._last_prices.get(symbol, 2500.0),
            'status': 'open',
            'filled': 0.0,
            'remaining': amount,
            'timestamp': int(datetime.utcnow().timestamp() * 1000)
        }
        
        self._orders[order_id] = order
        
        # Simulate immediate fill for market orders
        if order_type == 'market':
            await self._simulate_order_fill(order_id)
            
        return order
        
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Simulate order cancellation"""
        self._check_connected()
        await asyncio.sleep(0.05)
        
        if order_id in self._orders:
            self._orders[order_id]['status'] = 'cancelled'
            return True
        return False
        
    async def fetch_open_orders(self, symbol: str) -> List[Dict]:
        """Return mock open orders"""
        self._check_connected()
        await asyncio.sleep(0.05)
        
        return [
            order for order in self._orders.values()
            if order['symbol'] == symbol and order['status'] == 'open'
        ]
        
    async def fetch_positions(self) -> List[Dict]:
        """Return mock positions"""
        self._check_connected()
        await asyncio.sleep(0.05)
        
        return list(self._positions.values())
        
    async def fetch_order(self, order_id: str, symbol: str) -> Dict:
        """Fetch specific order"""
        self._check_connected()
        await asyncio.sleep(0.05)
        
        order = self._orders.get(order_id)
        if not order:
            raise Exception(f"Order {order_id} not found")
            
        # Simulate partial fills for limit orders
        if order['status'] == 'open' and order['type'] == 'limit':
            if random.random() > 0.7:  # 30% chance of fill
                await self._simulate_order_fill(order_id)
                
        return order
        
    async def fetch_ticker(self, symbol: str) -> Dict:
        """Return mock ticker data"""
        self._check_connected()
        await asyncio.sleep(0.05)
        
        price = self._last_prices.get(symbol, 2500.0)
        
        # Add some random variation
        change = random.uniform(-0.02, 0.02)
        new_price = price * (1 + change)
        self._last_prices[symbol] = new_price
        
        return {
            'symbol': symbol,
            'last': new_price,
            'bid': new_price * 0.9999,
            'ask': new_price * 1.0001,
            'high': new_price * 1.02,
            'low': new_price * 0.98,
            'volume': random.uniform(1000, 5000),
            'timestamp': int(datetime.utcnow().timestamp() * 1000)
        }
        
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', 
                         limit: int = 100) -> List:
        """Generate mock OHLCV data"""
        self._check_connected()
        await asyncio.sleep(0.05)
        
        ohlcv = []
        base_price = self._last_prices.get(symbol, 2500.0)
        current_time = int(datetime.utcnow().timestamp() * 1000)
        
        # Generate historical data
        for i in range(limit, 0, -1):
            timestamp = current_time - (i * 60000)  # 1 minute intervals
            
            # Add some random walk
            change = random.uniform(-0.001, 0.001)
            base_price *= (1 + change)
            
            open_price = base_price
            high = base_price * random.uniform(1.0001, 1.002)
            low = base_price * random.uniform(0.998, 0.9999)
            close = base_price * random.uniform(0.999, 1.001)
            volume = random.uniform(10, 100)
            
            ohlcv.append([timestamp, open_price, high, low, close, volume])
            base_price = close
            
        return ohlcv
        
    def _check_connected(self):
        """Check if connected"""
        if not self._connected:
            raise Exception("Not connected to exchange")
            
    async def _simulate_order_fill(self, order_id: str):
        """Simulate order fill"""
        order = self._orders.get(order_id)
        if order:
            order['status'] = 'closed'
            order['filled'] = order['amount']
            order['remaining'] = 0.0
            order['average'] = order['price']
            
            # Update mock position
            symbol = order['symbol']
            if symbol not in self._positions:
                self._positions[symbol] = {
                    'symbol': symbol,
                    'side': 'long' if order['side'] == 'buy' else 'short',
                    'contracts': order['amount'],
                    'entry_price': order['price'],
                    'mark_price': order['price'],
                    'unrealized_pnl': 0.0,
                    'margin': order['amount'] * order['price'] / 10  # 10x leverage
                }
            else:
                # Update existing position
                position = self._positions[symbol]
                if order['side'] == 'buy':
                    position['contracts'] += order['amount']
                else:
                    position['contracts'] -= order['amount']
                    
                if position['contracts'] <= 0:
                    del self._positions[symbol]