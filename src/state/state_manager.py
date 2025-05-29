import json
from typing import Dict, Optional
from datetime import datetime
import redis.asyncio as redis

class StateManager:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._redis = None
        
    async def connect(self):
        self._redis = await redis.from_url(self.redis_url)
        
    async def disconnect(self):
        if self._redis:
            await self._redis.close()
            
    async def get_position(self, symbol: str) -> Optional[Dict]:
        data = await self._redis.get(f"position:{symbol}")
        return json.loads(data) if data else None
        
    async def save_position(self, symbol: str, position: Dict):
        await self._redis.set(
            f"position:{symbol}",
            json.dumps(position),
            ex=86400  # 24 hour expiry
        )
        
    async def get_strategy_state(self) -> Dict:
        data = await self._redis.get("strategy:state")
        return json.loads(data) if data else {}
        
    async def save_strategy_state(self, state: Dict):
        await self._redis.set("strategy:state", json.dumps(state))