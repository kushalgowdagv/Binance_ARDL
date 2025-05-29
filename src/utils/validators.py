"""Input validation utilities"""

import re
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal
from datetime import datetime
from src.core.constants import (
    MIN_ORDER_SIZE, PRICE_PRECISION, QUANTITY_PRECISION,
    OrderSide, OrderType, PositionSide
)
from src.core.exceptions import ValidationError
from src.utils.logger import get_logger

logger = get_logger(__name__)

class Validators:
    """Common validation functions"""
    
    @staticmethod
    def validate_symbol(symbol: str) -> bool:
        """Validate trading symbol format"""
        # Binance futures format: BTC/USDT:USDT or BTC/USDT:USDT-240927
        pattern = r'^[A-Z]+/[A-Z]+:[A-Z]+(-\d{6})?$'
        return bool(re.match(pattern, symbol))
        
    @staticmethod
    def validate_price(price: Union[float, Decimal], 
                      min_price: float = 0.0) -> Decimal:
        """Validate and format price"""
        try:
            price_decimal = Decimal(str(price))
            
            if price_decimal <= min_price:
                raise ValidationError(f"Price must be greater than {min_price}")
                
            # Round to price precision
            return round(price_decimal, PRICE_PRECISION)
            
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid price format: {e}")
            
    @staticmethod
    def validate_quantity(quantity: Union[float, Decimal], 
                         min_quantity: float = MIN_ORDER_SIZE) -> Decimal:
        """Validate and format quantity"""
        try:
            qty_decimal = Decimal(str(quantity))
            
            if qty_decimal < min_quantity:
                raise ValidationError(
                    f"Quantity must be at least {min_quantity}"
                )
                
            # Round to quantity precision
            return round(qty_decimal, QUANTITY_PRECISION)
            
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid quantity format: {e}")
            
    @staticmethod
    def validate_order_side(side: str) -> str:
        """Validate order side"""
        side_upper = side.upper()
        valid_sides = [s.value.upper() for s in OrderSide]
        
        if side_upper not in valid_sides:
            raise ValidationError(
                f"Invalid order side: {side}. Must be one of {valid_sides}"
            )
            
        return side.lower()
        
    @staticmethod
    def validate_order_type(order_type: str) -> str:
        """Validate order type"""
        type_upper = order_type.upper()
        valid_types = [t.value.upper() for t in OrderType]
        
        if type_upper not in valid_types:
            raise ValidationError(
                f"Invalid order type: {order_type}. Must be one of {valid_types}"
            )
            
        return order_type.lower()
        
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration dictionary"""
        required_fields = {
            'exchange': ['api_key', 'api_secret'],
            'strategy': ['symbols', 'interval', 'entry_threshold', 
                        'exit_threshold', 'position_size', 'max_positions'],
            'risk': ['max_position_size', 'position_size_pct', 
                    'max_daily_loss', 'max_drawdown']
        }
        
        for section, fields in required_fields.items():
            if section not in config:
                raise ValidationError(f"Missing config section: {section}")
                
            for field in fields:
                if field not in config[section]:
                    raise ValidationError(
                        f"Missing required field: {section}.{field}"
                    )
                    
        # Validate specific fields
        if config['strategy']['position_size'] <= 0:
            raise ValidationError("Position size must be positive")
            
        if config['risk']['max_drawdown'] <= 0 or config['risk']['max_drawdown'] > 1:
            raise ValidationError("Max drawdown must be between 0 and 1")
            
        return config
        
    @staticmethod
    def validate_api_credentials(api_key: str, api_secret: str) -> bool:
        """Validate API credentials format"""
        if not api_key or not api_secret:
            raise ValidationError("API credentials cannot be empty")
            
        # Basic length validation
        if len(api_key) < 20 or len(api_secret) < 20:
            raise ValidationError("API credentials appear to be invalid")
            
        # Check for placeholder values
        if 'your-' in api_key.lower() or 'your-' in api_secret.lower():
            raise ValidationError("Please replace placeholder API credentials")
            
        return True
        
    @staticmethod
    def validate_timestamp(timestamp: Union[int, float, datetime]) -> int:
        """Validate and convert timestamp to milliseconds"""
        try:
            if isinstance(timestamp, datetime):
                return int(timestamp.timestamp() * 1000)
            elif isinstance(timestamp, (int, float)):
                # Check if already in milliseconds or seconds
                if timestamp > 1e12:  # Likely milliseconds
                    return int(timestamp)
                else:  # Likely seconds
                    return int(timestamp * 1000)
            else:
                raise ValidationError(
                    f"Invalid timestamp type: {type(timestamp)}"
                )
        except Exception as e:
            raise ValidationError(f"Invalid timestamp: {e}")

class OrderValidator:
    """Order-specific validation"""
    
    @staticmethod
    def validate_limit_order(symbol: str, side: str, amount: float, 
                           price: float) -> Dict[str, Any]:
        """Validate limit order parameters"""
        return {
            'symbol': symbol if Validators.validate_symbol(symbol) else None,
            'side': Validators.validate_order_side(side),
            'amount': float(Validators.validate_quantity(amount)),
            'price': float(Validators.validate_price(price))
        }
        
    @staticmethod
    def validate_market_order(symbol: str, side: str, 
                            amount: float) -> Dict[str, Any]:
        """Validate market order parameters"""
        return {
            'symbol': symbol if Validators.validate_symbol(symbol) else None,
            'side': Validators.validate_order_side(side),
            'amount': float(Validators.validate_quantity(amount))
        }
        
    @staticmethod
    def validate_order_response(response: Dict[str, Any]) -> bool:
        """Validate order response from exchange"""
        required_fields = ['id', 'symbol', 'side', 'type', 'status']
        
        for field in required_fields:
            if field not in response:
                logger.error(f"Missing field in order response: {field}")
                return False
                
        return True

class PositionValidator:
    """Position-specific validation"""
    
    @staticmethod
    def validate_position_size(symbol: str, size: float, 
                             max_size: float, balance: float) -> bool:
        """Validate position size against limits"""
        if size <= 0:
            raise ValidationError("Position size must be positive")
            
        if size > max_size:
            raise ValidationError(
                f"Position size {size} exceeds maximum {max_size}"
            )
            
        # Additional checks can be added here
        return True
        
    @staticmethod
    def validate_leverage(leverage: int, max_leverage: int = 20) -> int:
        """Validate leverage setting"""
        if leverage < 1 or leverage > max_leverage:
            raise ValidationError(
                f"Leverage must be between 1 and {max_leverage}"
            )
        return leverage