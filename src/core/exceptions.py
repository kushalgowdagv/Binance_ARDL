"""Custom exceptions for the trading bot"""

class TradingBotError(Exception):
    """Base exception for all trading bot errors"""
    pass

class ConnectionError(TradingBotError):
    """Raised when connection to exchange fails"""
    pass

class AuthenticationError(TradingBotError):
    """Raised when authentication fails"""
    pass

class InsufficientBalanceError(TradingBotError):
    """Raised when account has insufficient balance"""
    pass

class OrderError(TradingBotError):
    """Base exception for order-related errors"""
    pass

class OrderPlacementError(OrderError):
    """Raised when order placement fails"""
    pass

class OrderCancellationError(OrderError):
    """Raised when order cancellation fails"""
    pass

class PositionError(TradingBotError):
    """Base exception for position-related errors"""
    pass

class RiskLimitExceededError(TradingBotError):
    """Raised when risk limits are exceeded"""
    pass

class MarketDataError(TradingBotError):
    """Raised when market data fetching fails"""
    pass

class StrategyError(TradingBotError):
    """Raised when strategy execution fails"""
    pass

class StateError(TradingBotError):
    """Raised when state management fails"""
    pass

class ValidationError(TradingBotError):
    """Raised when validation fails"""
    pass

class ConfigurationError(TradingBotError):
    """Raised when configuration is invalid"""
    pass