"""Main trade execution engine"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from src.strategy.base import TradingSignal, Signal
from src.execution.order_manager import OrderManager, OrderStatus
from src.execution.position_manager import PositionManager
from src.data.order_book import OrderBookManager
from src.utils.logger import get_logger
from src.core.constants import OrderSide, OrderType

class TradingExecutor:
    def __init__(self, exchange, state_manager, risk_manager, config):
        self.exchange = exchange
        self.state_manager = state_manager
        self.risk_manager = risk_manager
        self.config = config
        self.logger = get_logger(__name__)
        
        # Initialize managers
        self.order_manager = OrderManager(exchange, state_manager)
        self.position_manager = PositionManager(exchange, state_manager, risk_manager)
        self.order_book_manager = OrderBookManager(exchange)
        
        # Execution state
        self._active_orders = {}
        self._position_targets = {}
        
    async def initialize(self):
        """Initialize the executor"""
        # Sync positions with exchange
        await self.position_manager.sync_positions()
        
        # Start order book streaming for configured symbols
        symbols = self.config.symbols
        await self.order_book_manager.start_streaming(symbols)
        
        self.logger.info("Trading executor initialized")
        
    async def shutdown(self):
        """Shutdown the executor"""
        # Stop order book streaming
        await self.order_book_manager.stop_streaming()
        
        # Cancel all open orders
        await self.cancel_all_orders()
        
        self.logger.info("Trading executor shut down")
        
    async def execute_signal(self, signal: TradingSignal) -> Optional[Dict]:
        """Execute a trading signal"""
        try:
            self.logger.info(
                f"Executing signal: {signal.signal.value} for {signal.symbol} "
                f"@ {signal.price} (confidence: {signal.confidence})"
            )
            
            # Check if we should act on this signal
            if signal.confidence < self.config.min_confidence:
                self.logger.info(f"Signal confidence too low: {signal.confidence}")
                return None
                
            # Route to appropriate handler
            if signal.signal == Signal.LONG_ENTRY:
                return await self._handle_long_entry(signal)
            elif signal.signal == Signal.LONG_EXIT:
                return await self._handle_long_exit(signal)
            elif signal.signal == Signal.SHORT_ENTRY:
                return await self._handle_short_entry(signal)
            elif signal.signal == Signal.SHORT_EXIT:
                return await self._handle_short_exit(signal)
            else:
                self.logger.warning(f"Unknown signal type: {signal.signal}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to execute signal: {e}")
            return None
            
    async def _handle_long_entry(self, signal: TradingSignal) -> Optional[Dict]:
        """Handle long entry signal"""
        # Check if we already have a position
        position = await self.position_manager.get_position(signal.symbol)
        if position and position.status == 'open':
            self.logger.info(f"Already have open position for {signal.symbol}")
            return None
            
        # Calculate position size
        position_size = await self.risk_manager.calculate_position_size(signal.symbol)
        
        # Check risk limits
        if not await self.risk_manager.can_open_position(signal.symbol, position_size):
            self.logger.warning("Risk limits prevent opening position")
            return None
            
        # Get best entry price from order book
        order_book = self.order_book_manager.get_order_book(signal.symbol)
        if order_book:
            # Place limit order at 2nd best bid for better fill
            entry_price = order_book.bids[1].price if len(order_book.bids) > 1 else signal.price
        else:
            entry_price = signal.price
            
        # Place entry order
        order = await self.order_manager.place_order(
            symbol=signal.symbol,
            side=OrderSide.BUY.value,
            order_type=OrderType.LIMIT.value,
            amount=position_size,
            price=entry_price
        )
        
        if order and order.status != OrderStatus.FAILED:
            self._active_orders[order.id] = order
            self._position_targets[signal.symbol] = {
                'side': 'long',
                'target_size': position_size,
                'entry_order_id': order.id
            }
            
        return order
        
    async def _handle_long_exit(self, signal: TradingSignal) -> Optional[Dict]:
        """Handle long exit signal"""
        # Get current position
        position = await self.position_manager.get_position(signal.symbol)
        if not position or position.status != 'open' or position.side != 'long':
            self.logger.warning(f"No long position to exit for {signal.symbol}")
            return None
            
        # Cancel any open orders for this symbol
        await self._cancel_symbol_orders(signal.symbol)
        
        # Get best exit price from order book
        order_book = self.order_book_manager.get_order_book(signal.symbol)
        if order_book:
            # Place limit order at 3rd best ask for better fill
            exit_price = order_book.asks[2].price if len(order_book.asks) > 2 else signal.price
        else:
            exit_price = signal.price
            
        # Place exit order
        order = await self.order_manager.place_order(
            symbol=signal.symbol,
            side=OrderSide.SELL.value,
            order_type=OrderType.LIMIT.value,
            amount=position.amount,
            price=exit_price
        )
        
        if order and order.status != OrderStatus.FAILED:
            self._active_orders[order.id] = order
            
        return order
        
    async def _handle_short_entry(self, signal: TradingSignal) -> Optional[Dict]:
        """Handle short entry signal"""
        # Similar to long entry but with sell orders
        position = await self.position_manager.get_position(signal.symbol)
        if position and position.status == 'open':
            self.logger.info(f"Already have open position for {signal.symbol}")
            return None
            
        position_size = await self.risk_manager.calculate_position_size(signal.symbol)
        
        if not await self.risk_manager.can_open_position(signal.symbol, position_size):
            self.logger.warning("Risk limits prevent opening position")
            return None
            
        order_book = self.order_book_manager.get_order_book(signal.symbol)
        if order_book:
            entry_price = order_book.asks[1].price if len(order_book.asks) > 1 else signal.price
        else:
            entry_price = signal.price
            
        order = await self.order_manager.place_order(
            symbol=signal.symbol,
            side=OrderSide.SELL.value,
            order_type=OrderType.LIMIT.value,
            amount=position_size,
            price=entry_price
        )
        
        if order and order.status != OrderStatus.FAILED:
            self._active_orders[order.id] = order
            self._position_targets[signal.symbol] = {
                'side': 'short',
                'target_size': position_size,
                'entry_order_id': order.id
            }
            
        return order
        
    async def _handle_short_exit(self, signal: TradingSignal) -> Optional[Dict]:
        """Handle short exit signal"""
        position = await self.position_manager.get_position(signal.symbol)
        if not position or position.status != 'open' or position.side != 'short':
            self.logger.warning(f"No short position to exit for {signal.symbol}")
            return None
            
        await self._cancel_symbol_orders(signal.symbol)
        
        order_book = self.order_book_manager.get_order_book(signal.symbol)
        if order_book:
            exit_price = order_book.bids[2].price if len(order_book.bids) > 2 else signal.price
        else:
            exit_price = signal.price
            
        order = await self.order_manager.place_order(
            symbol=signal.symbol,
            side=OrderSide.BUY.value,
            order_type=OrderType.LIMIT.value,
            amount=position.amount,
            price=exit_price
        )
        
        if order and order.status != OrderStatus.FAILED:
            self._active_orders[order.id] = order
            
        return order
        
    async def _cancel_symbol_orders(self, symbol: str):
        """Cancel all orders for a symbol"""
        orders_to_cancel = []
        for order_id, order in self._active_orders.items():
            if order.symbol == symbol and order.status == OrderStatus.PENDING:
                orders_to_cancel.append(order_id)
                
        for order_id in orders_to_cancel:
            await self.order_manager.cancel_order(order_id)
            
    async def cancel_all_orders(self):
        """Cancel all active orders"""
        for order_id in list(self._active_orders.keys()):
            await self.order_manager.cancel_order(order_id)
            
    async def close_all_positions(self):
        """Close all open positions"""
        positions = await self.position_manager.get_open_positions()
        
        for position in positions:
            # Get current price
            order_book = self.order_book_manager.get_order_book(position.symbol)
            if not order_book:
                self.logger.error(f"No order book for {position.symbol}, using market order")
                order_type = OrderType.MARKET.value
                price = None
            else:
                order_type = OrderType.LIMIT.value
                price = order_book.bids[0].price if position.side == 'long' else order_book.asks[0].price
                
            # Place closing order
            await self.order_manager.place_order(
                symbol=position.symbol,
                side=OrderSide.SELL.value if position.side == 'long' else OrderSide.BUY.value,
                order_type=order_type,
                amount=position.amount,
                price=price
            )
            
    async def get_positions(self) -> List[Dict]:
        """Get all positions"""
        return await self.position_manager.get_open_positions()
        
    async def get_orders(self) -> List[Dict]:
        """Get all active orders"""
        return list(self._active_orders.values())
