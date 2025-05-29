"""Centralized logging configuration"""

import logging
import logging.handlers
import sys
from pathlib import Path
from datetime import datetime
import json
import colorlog
from typing import Optional

class JsonFormatter(logging.Formatter):
    """JSON log formatter for structured logging"""
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
            
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 
                          'funcName', 'levelname', 'levelno', 'lineno', 
                          'module', 'msecs', 'pathname', 'process', 
                          'processName', 'relativeCreated', 'thread', 
                          'threadName', 'exc_info', 'exc_text', 'stack_info']:
                log_data[key] = value
                
        return json.dumps(log_data)

def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_to_console: bool = True,
    log_format: str = "colored",  # "colored", "json", "simple"
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
):
    """Setup logging configuration"""
    
    # Create logs directory if needed
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        
        if log_format == "colored":
            formatter = colorlog.ColoredFormatter(
                "%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "bold_red",
                }
            )
        elif log_format == "json":
            formatter = JsonFormatter()
        else:
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
    # File handler
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        
        # Always use JSON format for file logs
        file_handler.setFormatter(JsonFormatter())
        root_logger.addHandler(file_handler)
        
    # Suppress noisy loggers
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("ccxt").setLevel(logging.WARNING)
    
def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)

# Trading-specific log methods
class TradingLogger:
    """Extended logger with trading-specific methods"""
    
    def __init__(self, name: str):
        self.logger = get_logger(name)
        
    def order_placed(self, order_id: str, symbol: str, side: str, 
                    amount: float, price: Optional[float] = None):
        """Log order placement"""
        self.logger.info(
            f"Order placed",
            extra={
                'order_id': order_id,
                'symbol': symbol,
                'side': side,
                'amount': amount,
                'price': price,
                'event': 'order_placed'
            }
        )
        
    def order_filled(self, order_id: str, filled_amount: float, 
                    average_price: float):
        """Log order fill"""
        self.logger.info(
            f"Order filled",
            extra={
                'order_id': order_id,
                'filled_amount': filled_amount,
                'average_price': average_price,
                'event': 'order_filled'
            }
        )
        
    def position_opened(self, symbol: str, side: str, amount: float, 
                       entry_price: float):
        """Log position opening"""
        self.logger.info(
            f"Position opened",
            extra={
                'symbol': symbol,
                'side': side,
                'amount': amount,
                'entry_price': entry_price,
                'event': 'position_opened'
            }
        )
        
    def position_closed(self, symbol: str, pnl: float, exit_price: float):
        """Log position closing"""
        level = self.logger.info if pnl >= 0 else self.logger.warning
        level(
            f"Position closed",
            extra={
                'symbol': symbol,
                'pnl': pnl,
                'exit_price': exit_price,
                'event': 'position_closed'
            }
        )
        
    def signal_generated(self, signal_type: str, symbol: str, 
                        confidence: float):
        """Log signal generation"""
        self.logger.info(
            f"Signal generated",
            extra={
                'signal_type': signal_type,
                'symbol': symbol,
                'confidence': confidence,
                'event': 'signal_generated'
            }
        )