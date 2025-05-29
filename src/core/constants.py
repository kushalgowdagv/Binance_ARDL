"""Core constants for the trading bot"""

from enum import Enum

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"

class TimeInForce(Enum):
    GTC = "GTC"  # Good Till Cancelled
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill
    GTX = "GTX"  # Good Till Crossing

class ExchangeType(Enum):
    SPOT = "spot"
    FUTURES = "futures"
    PERPETUAL = "perpetual"

# Trading constants
DEFAULT_LEVERAGE = 10
MIN_ORDER_SIZE = 0.001
MAX_RETRY_ATTEMPTS = 3
ORDER_FILL_TIMEOUT = 60  # seconds
POSITION_SYNC_INTERVAL = 300  # seconds

# API Rate limits
BINANCE_RATE_LIMIT = 2400  # per minute
BINANCE_ORDER_RATE_LIMIT = 300  # per minute

# Price precision
PRICE_PRECISION = 2
QUANTITY_PRECISION = 3

# Risk management
DEFAULT_STOP_LOSS_PCT = 0.02  # 2%
DEFAULT_TAKE_PROFIT_PCT = 0.04  # 4%
MAX_POSITION_SIZE_PCT = 0.1  # 10% of balance

# Monitoring
METRICS_UPDATE_INTERVAL = 5  # seconds
HEALTH_CHECK_INTERVAL = 30  # seconds

# State management
STATE_CACHE_TTL = 3600  # seconds
ORDER_HISTORY_RETENTION = 7  # days
TRADE_HISTORY_RETENTION = 30  # days