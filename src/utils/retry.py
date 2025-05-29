"""Retry utilities for handling transient failures"""

import asyncio
import functools
from typing import Callable, Optional, Tuple, Type, Union
import random
from src.utils.logger import get_logger

logger = get_logger(__name__)

def retry_async(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    should_retry: Optional[Callable[[Exception], bool]] = None
):
    """
    Async retry decorator with exponential backoff
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier for exponential backoff
        max_delay: Maximum delay between retries
        exceptions: Tuple of exceptions to catch and retry
        should_retry: Optional function to determine if exception should be retried
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            
            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                    
                except exceptions as e:
                    attempt += 1
                    
                    # Check if we should retry this exception
                    if should_retry and not should_retry(e):
                        raise
                        
                    if attempt >= max_attempts:
                        logger.error(
                            f"Max retry attempts ({max_attempts}) reached for {func.__name__}"
                        )
                        raise
                        
                    # Add jitter to prevent thundering herd
                    jitter = random.uniform(0, current_delay * 0.1)
                    sleep_time = min(current_delay + jitter, max_delay)
                    
                    logger.warning(
                        f"Retry attempt {attempt}/{max_attempts} for {func.__name__} "
                        f"after {sleep_time:.2f}s delay. Error: {str(e)}"
                    )
                    
                    await asyncio.sleep(sleep_time)
                    
                    # Exponential backoff
                    current_delay = min(current_delay * backoff, max_delay)
                    
        return wrapper
    return decorator

def retry_sync(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    should_retry: Optional[Callable[[Exception], bool]] = None
):
    """
    Sync retry decorator with exponential backoff
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    attempt += 1
                    
                    if should_retry and not should_retry(e):
                        raise
                        
                    if attempt >= max_attempts:
                        logger.error(
                            f"Max retry attempts ({max_attempts}) reached for {func.__name__}"
                        )
                        raise
                        
                    jitter = random.uniform(0, current_delay * 0.1)
                    sleep_time = min(current_delay + jitter, max_delay)
                    
                    logger.warning(
                        f"Retry attempt {attempt}/{max_attempts} for {func.__name__} "
                        f"after {sleep_time:.2f}s delay. Error: {str(e)}"
                    )
                    
                    import time
                    time.sleep(sleep_time)
                    
                    current_delay = min(current_delay * backoff, max_delay)
                    
        return wrapper
    return decorator

# Predefined retry strategies
class RetryStrategies:
    """Common retry strategies"""
    
    @staticmethod
    def api_retry():
        """Retry strategy for API calls"""
        return retry_async(
            max_attempts=5,
            delay=0.5,
            backoff=2.0,
            max_delay=30.0,
            exceptions=(
                ConnectionError,
                TimeoutError,
                asyncio.TimeoutError,
            )
        )
        
    @staticmethod
    def order_retry():
        """Retry strategy for order operations"""
        def should_retry_order(e: Exception) -> bool:
            # Don't retry on insufficient funds or invalid orders
            error_msg = str(e).lower()
            if any(msg in error_msg for msg in ['insufficient', 'invalid', 'rejected']):
                return False
            return True
            
        return retry_async(
            max_attempts=3,
            delay=1.0,
            backoff=1.5,
            max_delay=10.0,
            should_retry=should_retry_order
        )
        
    @staticmethod
    def connection_retry():
        """Retry strategy for connection operations"""
        return retry_async(
            max_attempts=10,
            delay=2.0,
            backoff=2.0,
            max_delay=60.0,
            exceptions=(ConnectionError, OSError)
        )