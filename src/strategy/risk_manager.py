from dataclasses import dataclass
from typing import Dict, List
from src.utils.logger import get_logger

@dataclass
class RiskLimits:
    max_position_size: float
    max_positions: int
    max_daily_loss: float
    max_drawdown: float
    position_size_pct: float  # Percentage of balance per position
    
class RiskManager:
    def __init__(self, config, exchange, state_manager):
        self.config = config
        self.exchange = exchange
        self.state_manager = state_manager
        self.logger = get_logger(__name__)
        self.limits = RiskLimits(
            max_position_size=config.max_position_size,
            max_positions=config.max_positions,
            max_daily_loss=config.max_daily_loss,
            max_drawdown=config.max_drawdown,
            position_size_pct=config.position_size_pct
        )
        
    async def can_open_position(self, symbol: str, amount: float) -> bool:
        """Check if we can open a new position"""
        # Check position count
        positions = await self.state_manager.get_all_positions()
        open_positions = [p for p in positions if p['status'] == 'open']
        
        if len(open_positions) >= self.limits.max_positions:
            self.logger.warning("Max positions limit reached")
            return False
            
        # Check position size
        if amount > self.limits.max_position_size:
            self.logger.warning("Position size exceeds limit")
            return False
            
        # Check daily loss
        daily_pnl = await self._calculate_daily_pnl()
        if daily_pnl < -self.limits.max_daily_loss:
            self.logger.warning("Daily loss limit reached")
            return False
            
        # Check account balance
        balance = await self.exchange.fetch_balance()
        usdt_balance = balance['free']['USDT']
        required_margin = await self._calculate_required_margin(symbol, amount)
        
        if required_margin > usdt_balance * 0.9:  # Keep 10% buffer
            self.logger.warning("Insufficient balance for position")
            return False
            
        return True
        
    async def calculate_position_size(self, symbol: str) -> float:
        """Calculate appropriate position size based on risk limits"""
        balance = await self.exchange.fetch_balance()
        usdt_balance = balance['free']['USDT']
        
        # Use percentage of balance
        position_value = usdt_balance * self.limits.position_size_pct
        
        # Get current price
        ticker = await self.exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        
        # Calculate position size
        position_size = position_value / current_price
        
        # Apply maximum limit
        return min(position_size, self.limits.max_position_size)
        
    async def _calculate_daily_pnl(self) -> float:
        """Calculate today's PnL"""
        trades = await self.state_manager.get_trades_since(
            datetime.utcnow().replace(hour=0, minute=0, second=0)
        )
        return sum(trade.get('pnl', 0) for trade in trades)
        
    async def _calculate_required_margin(self, symbol: str, amount: float) -> float:
        """Calculate required margin for position"""
        ticker = await self.exchange.fetch_ticker(symbol)
        position_value = ticker['last'] * amount
        # Assuming 10x leverage
        return position_value / 10