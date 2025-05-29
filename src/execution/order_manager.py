import asyncio
from typing import Optional, Dict, List
from dataclasses import dataclass
from enum import Enum
import uuid
from src.utils.logger import get_logger
from src.utils.retry import retry_async

class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"

@dataclass
class Order:
    id: str
    symbol: str
    side: str
    order_type: str
    amount: float
    price: Optional[float]
    status: OrderStatus
    exchange_order_id: Optional[str] = None
    filled_amount: float = 0.0
    average_price: float = 0.0
    
class OrderManager:
    def __init__(self, exchange, state_manager):
        self.exchange = exchange
        self.state_manager = state_manager
        self.logger = get_logger(__name__)
        self.active_orders: Dict[str, Order] = {}
        
    @retry_async(max_attempts=3, delay=1)
    async def place_order(self, symbol: str, side: str, order_type: str, 
                         amount: float, price: Optional[float] = None) -> Order:
        """Place an order with retry logic"""
        order = Order(
            id=str(uuid.uuid4()),
            symbol=symbol,
            side=side,
            order_type=order_type,
            amount=amount,
            price=price,
            status=OrderStatus.PENDING
        )
        
        try:
            # Place order on exchange
            response = await self.exchange.create_order(
                symbol=symbol,
                order_type=order_type,
                side=side,
                amount=amount,
                price=price
            )
            
            order.exchange_order_id = response['id']
            self.active_orders[order.id] = order
            
            # Save to state
            await self.state_manager.save_order(order.id, order.__dict__)
            
            # Start monitoring
            asyncio.create_task(self._monitor_order(order))
            
            self.logger.info(f"Order placed: {order.id} - {symbol} {side} {amount}")
            return order
            
        except Exception as e:
            order.status = OrderStatus.FAILED
            self.logger.error(f"Failed to place order: {e}")
            raise
            
    async def _monitor_order(self, order: Order):
        """Monitor order status until filled or cancelled"""
        max_attempts = 10
        attempt = 0
        
        while attempt < max_attempts and order.status == OrderStatus.PENDING:
            try:
                # Check order status
                exchange_orders = await self.exchange.fetch_order(
                    order.exchange_order_id, 
                    order.symbol
                )
                
                if exchange_orders['status'] == 'closed':
                    order.status = OrderStatus.FILLED
                    order.filled_amount = exchange_orders['filled']
                    order.average_price = exchange_orders['average']
                    break
                elif exchange_orders['status'] == 'cancelled':
                    order.status = OrderStatus.CANCELLED
                    break
                    
            except Exception as e:
                self.logger.error(f"Error monitoring order {order.id}: {e}")
                
            await asyncio.sleep(2)
            attempt += 1
            
        # Update state
        await self.state_manager.save_order(order.id, order.__dict__)
        
        if order.status == OrderStatus.PENDING and attempt >= max_attempts:
            # Cancel if still pending
            await self.cancel_order(order.id)
            
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        order = self.active_orders.get(order_id)
        if not order:
            return False
            
        try:
            await self.exchange.cancel_order(order.exchange_order_id, order.symbol)
            order.status = OrderStatus.CANCELLED
            await self.state_manager.save_order(order.id, order.__dict__)
            return True
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
