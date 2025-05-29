"""Redis-based state storage implementation"""

import json
import asyncio
from typing import Dict, List, Optional, Any, Type
from datetime import datetime, timedelta
import redis.asyncio as redis
from src.state.models import (
    OrderState, PositionState, TradeState, 
    StrategyState, SerializableModel
)
from src.utils.logger import get_logger
from src.core.constants import (
    STATE_CACHE_TTL, ORDER_HISTORY_RETENTION, 
    TRADE_HISTORY_RETENTION
)

class RedisStore:
    """Redis-based persistent storage"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", db: int = 0):
        self.redis_url = redis_url
        self.db = db
        self._redis: Optional[redis.Redis] = None
        self.logger = get_logger(__name__)
        self._key_prefix = "trading_bot:"
        
    async def connect(self):
        """Connect to Redis"""
        try:
            self._redis = await redis.from_url(
                self.redis_url, 
                db=self.db,
                decode_responses=True
            )
            await self._redis.ping()
            self.logger.info("Connected to Redis")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            raise
            
    async def disconnect(self):
        """Disconnect from Redis"""
        if self._redis:
            await self._redis.close()
            self.logger.info("Disconnected from Redis")
            
    def _make_key(self, namespace: str, key: str) -> str:
        """Create namespaced key"""
        return f"{self._key_prefix}{namespace}:{key}"
        
    async def save_order(self, order: OrderState):
        """Save order state"""
        key = self._make_key("orders", order.id)
        order.updated_at = datetime.utcnow()
        
        await self._redis.setex(
            key,
            ORDER_HISTORY_RETENTION * 86400,  # Days to seconds
            order.to_json()
        )
        
        # Add to active orders set if pending
        if order.status == "pending":
            await self._redis.sadd(
                self._make_key("active_orders", order.symbol),
                order.id
            )
        else:
            await self._redis.srem(
                self._make_key("active_orders", order.symbol),
                order.id
            )
            
    async def get_order(self, order_id: str) -> Optional[OrderState]:
        """Get order by ID"""
        key = self._make_key("orders", order_id)
        data = await self._redis.get(key)
        
        if data:
            return OrderState.from_json(data)
        return None
        
    async def get_active_orders(self, symbol: Optional[str] = None) -> List[OrderState]:
        """Get active orders"""
        orders = []
        
        if symbol:
            order_ids = await self._redis.smembers(
                self._make_key("active_orders", symbol)
            )
        else:
            # Get all active orders
            pattern = self._make_key("active_orders", "*")
            keys = []
            async for key in self._redis.scan_iter(pattern):
                members = await self._redis.smembers(key)
                keys.extend(members)
            order_ids = keys
            
        for order_id in order_ids:
            order = await self.get_order(order_id)
            if order:
                orders.append(order)
                
        return orders
        
    async def save_position(self, position: PositionState):
        """Save position state"""
        key = self._make_key("positions", position.symbol)
        
        await self._redis.setex(
            key,
            STATE_CACHE_TTL,
            position.to_json()
        )
        
        # Track open positions
        if position.status == "open":
            await self._redis.sadd("open_positions", position.symbol)
        else:
            await self._redis.srem("open_positions", position.symbol)
            
    async def get_position(self, symbol: str) -> Optional[PositionState]:
        """Get position by symbol"""
        key = self._make_key("positions", symbol)
        data = await self._redis.get(key)
        
        if data:
            return PositionState.from_json(data)
        return None
        
    async def get_all_positions(self) -> List[PositionState]:
        """Get all positions"""
        positions = []
        pattern = self._make_key("positions", "*")
        
        async for key in self._redis.scan_iter(pattern):
            data = await self._redis.get(key)
            if data:
                positions.append(PositionState.from_json(data))
                
        return positions
        
    async def get_open_positions(self) -> List[PositionState]:
        """Get open positions"""
        positions = []
        symbols = await self._redis.smembers("open_positions")
        
        for symbol in symbols:
            position = await self.get_position(symbol)
            if position and position.status == "open":
                positions.append(position)
                
        return positions
        
    async def save_trade(self, trade: TradeState):
        """Save completed trade"""
        key = self._make_key("trades", trade.id)
        
        await self._redis.setex(
            key,
            TRADE_HISTORY_RETENTION * 86400,
            trade.to_json()
        )
        
        # Add to sorted set by timestamp for easy querying
        score = trade.exit_time.timestamp()
        await self._redis.zadd(
            self._make_key("trades_by_time", trade.symbol),
            {trade.id: score}
        )
        
    async def get_trades(self, symbol: Optional[str] = None, 
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None) -> List[TradeState]:
        """Get trades with optional filters"""
        trades = []
        
        if symbol:
            keys = [self._make_key("trades_by_time", symbol)]
        else:
            # Get all trade keys
            pattern = self._make_key("trades_by_time", "*")
            keys = [key async for key in self._redis.scan_iter(pattern)]
            
        for key in keys:
            # Get trade IDs in time range
            min_score = start_time.timestamp() if start_time else "-inf"
            max_score = end_time.timestamp() if end_time else "+inf"
            
            trade_ids = await self._redis.zrangebyscore(
                key, min_score, max_score
            )
            
            for trade_id in trade_ids:
                trade_data = await self._redis.get(
                    self._make_key("trades", trade_id)
                )
                if trade_data:
                    trades.append(TradeState.from_json(trade_data))
                    
        return trades
        
    async def get_trades_since(self, since: datetime) -> List[TradeState]:
        """Get trades since a specific time"""
        return await self.get_trades(start_time=since)
        
    async def save_strategy_state(self, strategy: StrategyState):
        """Save strategy state"""
        key = self._make_key("strategies", strategy.name)
        
        await self._redis.setex(
            key,
            STATE_CACHE_TTL,
            strategy.to_json()
        )
        
    async def get_strategy_state(self, name: str) -> Optional[StrategyState]:
        """Get strategy state"""
        key = self._make_key("strategies", name)
        data = await self._redis.get(key)
        
        if data:
            return StrategyState.from_json(data)
        return None
        
    async def save_global_state(self, state: Dict[str, Any]):
        """Save global bot state"""
        key = self._make_key("global", "state")
        
        await self._redis.setex(
            key,
            STATE_CACHE_TTL,
            json.dumps(state, default=str)
        )
        
    async def get_global_state(self) -> Dict[str, Any]:
        """Get global bot state"""
        key = self._make_key("global", "state")
        data = await self._redis.get(key)
        
        if data:
            return json.loads(data)
        return {}
        
    async def health_check(self) -> bool:
        """Check Redis connection health"""
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False
            
    async def cleanup_old_data(self):
        """Clean up old data beyond retention period"""
        try:
            # Clean old trades
            cutoff_time = datetime.utcnow() - timedelta(days=TRADE_HISTORY_RETENTION)
            cutoff_score = cutoff_time.timestamp()
            
            pattern = self._make_key("trades_by_time", "*")
            async for key in self._redis.scan_iter(pattern):
                # Remove old entries
                await self._redis.zremrangebyscore(key, "-inf", cutoff_score)
                
            self.logger.info("Cleaned up old trade data")
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old data: {e}")