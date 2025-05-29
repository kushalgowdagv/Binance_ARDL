"""Binance exchange implementation"""

import asyncio
from typing import Dict, List, Optional
import ccxt.async_support as ccxt
from binance import AsyncClient
from src.exchanges.base import ExchangeInterface
from src.utils.logger import get_logger
from src.core.exceptions import (
    ConnectionError, AuthenticationError, 
    InsufficientBalanceError, OrderError
)

class BinanceExchange(ExchangeInterface):
    def __init__(self, config):
        self.config = config
        self.logger = get_logger(__name__)
        self.ccxt_client = None
        self.binance_client = None
        self._connected = False
        
    async def connect(self):
        """Connect to Binance exchange"""
        try:
            # Initialize CCXT client
            self.ccxt_client = ccxt.binance({
                'apiKey': self.config.api_key,
                'secret': self.config.api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',  # Use futures by default
                    'adjustForTimeDifference': True
                }
            })
            
            if self.config.testnet:
                self.ccxt_client.set_sandbox_mode(True)
                
            # Initialize Binance client for specific futures operations
            self.binance_client = await AsyncClient.create(
                api_key=self.config.api_key,
                api_secret=self.config.api_secret,
                testnet=self.config.testnet
            )
            
            # Test connection
            await self.ccxt_client.load_markets()
            balance = await self.fetch_balance()
            
            self._connected = True
            self.logger.info(f"Connected to Binance {'testnet' if self.config.testnet else 'mainnet'}")
            self.logger.info(f"USDT Balance: {balance.get('USDT', {}).get('free', 0)}")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Binance: {e}")
            raise ConnectionError(f"Failed to connect to Binance: {e}")
            
    async def disconnect(self):
        """Disconnect from exchange"""
        if self.ccxt_client:
            await self.ccxt_client.close()
        if self.binance_client:
            await self.binance_client.close_connection()
        self._connected = False
        self.logger.info("Disconnected from Binance")
        
    async def fetch_balance(self) -> Dict:
        """Fetch account balance"""
        try:
            balance = await self.ccxt_client.fetch_balance()
            return balance
        except Exception as e:
            self.logger.error(f"Failed to fetch balance: {e}")
            raise
            
    async def fetch_order_book(self, symbol: str, limit: int = 10) -> Dict:
        """Fetch order book"""
        try:
            order_book = await self.ccxt_client.fetch_order_book(symbol, limit)
            return order_book
        except Exception as e:
            self.logger.error(f"Failed to fetch order book for {symbol}: {e}")
            raise
            
    async def create_order(self, symbol: str, order_type: str, 
                          side: str, amount: float, 
                          price: Optional[float] = None) -> Dict:
        """Create an order"""
        try:
            # Check balance
            if side == 'buy':
                balance = await self.fetch_balance()
                usdt_balance = balance.get('USDT', {}).get('free', 0)
                
                # Estimate required balance
                if price:
                    required = amount * price / 10  # Assuming 10x leverage
                else:
                    ticker = await self.ccxt_client.fetch_ticker(symbol)
                    required = amount * ticker['last'] / 10
                    
                if usdt_balance < required:
                    raise InsufficientBalanceError(
                        f"Insufficient balance. Required: {required}, Available: {usdt_balance}"
                    )
                    
            # Place order
            if order_type == 'limit' and price is None:
                raise OrderError("Price is required for limit orders")
                
            order = await self.ccxt_client.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=amount,
                price=price
            )
            
            self.logger.info(
                f"Order created: {order['id']} - {symbol} {side} "
                f"{amount} @ {price if price else 'market'}"
            )
            return order
            
        except ccxt.InsufficientFunds as e:
            raise InsufficientBalanceError(str(e))
        except Exception as e:
            self.logger.error(f"Failed to create order: {e}")
            raise OrderError(f"Failed to create order: {e}")
            
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order"""
        try:
            await self.ccxt_client.cancel_order(order_id, symbol)
            self.logger.info(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
            
    async def fetch_open_orders(self, symbol: str) -> List[Dict]:
        """Fetch open orders"""
        try:
            orders = await self.ccxt_client.fetch_open_orders(symbol)
            return orders
        except Exception as e:
            self.logger.error(f"Failed to fetch open orders: {e}")
            return []
            
    async def fetch_positions(self) -> List[Dict]:
        """Fetch all positions"""
        try:
            balance = await self.ccxt_client.fetch_balance()
            positions = []
            
            if 'info' in balance and 'positions' in balance['info']:
                for position in balance['info']['positions']:
                    if float(position.get('positionInitialMargin', 0)) > 0:
                        positions.append({
                            'symbol': position['symbol'],
                            'side': 'long' if float(position['positionAmt']) > 0 else 'short',
                            'contracts': abs(float(position['positionAmt'])),
                            'entry_price': float(position['entryPrice']),
                            'mark_price': float(position.get('markPrice', 0)),
                            'unrealized_pnl': float(position.get('unrealizedProfit', 0)),
                            'margin': float(position['positionInitialMargin'])
                        })
                        
            return positions
        except Exception as e:
            self.logger.error(f"Failed to fetch positions: {e}")
            return []
            
    async def fetch_position(self, symbol: str) -> Optional[Dict]:
        """Fetch position for a specific symbol"""
        positions = await self.fetch_positions()
        
        # Convert symbol format
        binance_symbol = symbol.replace('/', '').replace(':', '').replace('-', '_')
        
        for position in positions:
            if position['symbol'] == binance_symbol:
                return position
        return None
        
    async def fetch_ticker(self, symbol: str) -> Dict:
        """Fetch ticker information"""
        try:
            ticker = await self.ccxt_client.fetch_ticker(symbol)
            return ticker
        except Exception as e:
            self.logger.error(f"Failed to fetch ticker for {symbol}: {e}")
            raise
            
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', 
                         limit: int = 100) -> List:
        """Fetch OHLCV data"""
        try:
            ohlcv = await self.ccxt_client.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            self.logger.error(f"Failed to fetch OHLCV for {symbol}: {e}")
            raise
            
    async def fetch_order(self, order_id: str, symbol: str) -> Dict:
        """Fetch a specific order"""
        try:
            order = await self.ccxt_client.fetch_order(order_id, symbol)
            return order
        except Exception as e:
            self.logger.error(f"Failed to fetch order {order_id}: {e}")
            raise