from dataclasses import dataclass
from typing import Dict, Optional, List
from datetime import datetime
from src.utils.logger import get_logger

@dataclass
class Position:
    symbol: str
    side: str  # 'long' or 'short'
    entry_price: float
    amount: float
    entry_time: datetime
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    status: str = 'open'  # 'open', 'closed'
    
class PositionManager:
    def __init__(self, exchange, state_manager, risk_manager):
        self.exchange = exchange
        self.state_manager = state_manager
        self.risk_manager = risk_manager
        self.logger = get_logger(__name__)
        self.positions: Dict[str, Position] = {}
        
    async def open_position(self, symbol: str, side: str, 
                          amount: float, entry_price: float) -> Position:
        """Open a new position"""
        # Check risk limits
        if not await self.risk_manager.can_open_position(symbol, amount):
            raise Exception("Risk limit exceeded")
            
        position = Position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            amount=amount,
            entry_time=datetime.utcnow()
        )
        
        self.positions[symbol] = position
        await self.state_manager.save_position(symbol, position.__dict__)
        
        self.logger.info(f"Position opened: {symbol} {side} {amount} @ {entry_price}")
        return position
        
    async def close_position(self, symbol: str, exit_price: float) -> Position:
        """Close an existing position"""
        position = self.positions.get(symbol)
        if not position or position.status == 'closed':
            raise Exception(f"No open position for {symbol}")
            
        position.exit_price = exit_price
        position.exit_time = datetime.utcnow()
        position.status = 'closed'
        
        # Calculate PnL
        if position.side == 'long':
            position.pnl = (exit_price - position.entry_price) * position.amount
        else:
            position.pnl = (position.entry_price - exit_price) * position.amount
            
        await self.state_manager.save_position(symbol, position.__dict__)
        
        self.logger.info(
            f"Position closed: {symbol} {position.side} "
            f"PnL: {position.pnl:.2f} USDT"
        )
        return position
        
    async def get_open_positions(self) -> List[Position]:
        """Get all open positions"""
        return [p for p in self.positions.values() if p.status == 'open']
        
    async def sync_positions(self):
        """Sync positions with exchange"""
        try:
            exchange_positions = await self.exchange.fetch_positions()
            
            for ex_pos in exchange_positions:
                symbol = ex_pos['symbol']
                if symbol not in self.positions and float(ex_pos['contracts']) > 0:
                    # Found position on exchange not in local state
                    self.logger.warning(f"Found untracked position: {symbol}")
                    # Recover position from exchange data
                    position = Position(
                        symbol=symbol,
                        side='long' if ex_pos['side'] == 'long' else 'short',
                        entry_price=float(ex_pos['markPrice']),
                        amount=float(ex_pos['contracts']),
                        entry_time=datetime.utcnow()
                    )
                    self.positions[symbol] = position
                    
        except Exception as e:
            self.logger.error(f"Failed to sync positions: {e}")