"""Main application entry point"""

import asyncio
import signal
import os
import sys
from typing import Optional
from datetime import datetime
from src.core.config import Config
from src.exchanges.binance import BinanceExchange
from src.exchanges.mock import MockExchange
from src.strategy.spread_strategy import SpreadTradingStrategy
from src.strategy.risk_manager import RiskManager
from src.execution.executor import TradingExecutor
from src.state.redis_store import RedisStore
from src.monitoring.metrics import MetricsServer
from src.monitoring.health_check import HealthMonitor
from src.monitoring.alerts import AlertManager
from src.data.klines import KlineManager
from src.data.order_book import OrderBookManager
from src.utils.logger import setup_logging, get_logger, TradingLogger
from src.utils.validators import Validators

class TradingBot:
    """Main trading bot application"""
    
    def __init__(self, config: Config, use_mock: bool = False):
        self.config = config
        self.use_mock = use_mock
        self.logger = TradingLogger(__name__)
        self.running = False
        self._shutdown_event = asyncio.Event()
        
        # Initialize components
        self._init_components()
        
    def _init_components(self):
        """Initialize all bot components"""
        # Exchange
        if self.use_mock:
            self.exchange = MockExchange(self.config.exchange)
        else:
            # Validate API credentials
            Validators.validate_api_credentials(
                self.config.exchange.api_key,
                self.config.exchange.api_secret
            )
            self.exchange = BinanceExchange(self.config.exchange)
            
        # State management
        self.state_store = RedisStore(
            redis_url=getattr(self.config, 'redis_url', 'redis://localhost:6379')
        )
        
        # Risk management
        self.risk_manager = RiskManager(
            self.config.risk,
            self.exchange,
            self.state_store
        )
        
        # Strategy
        self.strategy = SpreadTradingStrategy(self.config.strategy)
        
        # Execution
        self.executor = TradingExecutor(
            self.exchange,
            self.state_store,
            self.risk_manager,
            self.config.strategy
        )
        
        # Data managers
        self.kline_manager = KlineManager(self.exchange, self.config)
        
        # Monitoring
        self.metrics_server = MetricsServer(self.config.monitoring)
        self.health_monitor = HealthMonitor(self.config.monitoring)
        self.alert_manager = AlertManager(self.config.monitoring)
        
    async def start(self):
        """Start the trading bot"""
        self.logger.logger.info("Starting trading bot...")
        
        try:
            # Connect to services
            await self._connect_services()
            
            # Initialize components
            await self._initialize_components()
            
            # Setup signal handlers
            self._setup_signal_handlers()
            
            self.running = True
            
            # Start main trading loop
            await self._trading_loop()
            
        except Exception as e:
            self.logger.logger.error(f"Failed to start bot: {e}")
            await self.stop()
            raise
            
    async def stop(self):
        """Gracefully stop the trading bot"""
        self.logger.logger.info("Stopping trading bot...")
        self.running = False
        self._shutdown_event.set()
        
        try:
            # Close all positions
            await self._close_all_positions()
            
            # Disconnect services
            await self._disconnect_services()
            
        except Exception as e:
            self.logger.logger.error(f"Error during shutdown: {e}")
            
        self.logger.logger.info("Trading bot stopped")
        
    async def _connect_services(self):
        """Connect to all external services"""
        # Connect to exchange
        await self.exchange.connect()
        
        # Connect to Redis
        await self.state_store.connect()
        
        # Start monitoring services
        await self.metrics_server.start()
        await self.health_monitor.start()
        
        self.logger.logger.info("All services connected")
        
    async def _disconnect_services(self):
        """Disconnect from all services"""
        await self.executor.shutdown()
        await self.exchange.disconnect()
        await self.state_store.disconnect()
        await self.health_monitor.stop()
        
    async def _initialize_components(self):
        """Initialize all components"""
        # Initialize executor
        await self.executor.initialize()
        
        # Start streaming market data
        await self.kline_manager.start_streaming(
            self.config.strategy.symbols,
            self.config.strategy.interval
        )
        
        # Sync positions
        await self.executor.position_manager.sync_positions()
        
        self.logger.logger.info("Components initialized")
        
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        loop = asyncio.get_event_loop()
        
        def signal_handler(sig):
            self.logger.logger.info(f"Received signal {sig}")
            asyncio.create_task(self.stop())
            
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
            
    async def _trading_loop(self):
        """Main trading loop"""
        self.logger.logger.info("Starting trading loop")
        
        while self.running:
            try:
                loop_start_time = datetime.utcnow()
                
                # Fetch market data
                market_data = await self._fetch_market_data()
                
                if market_data:
                    # Generate trading signals
                    signals = await self.strategy.calculate_signals(market_data)
                    
                    # Execute valid signals
                    for signal in signals:
                        if self.strategy.validate_signal(signal):
                            self.logger.signal_generated(
                                signal.signal.value,
                                signal.symbol,
                                signal.confidence
                            )
                            await self.executor.execute_signal(signal)
                            
                    # Update metrics
                    await self._update_metrics()
                    
                    # Check alerts
                    await self._check_alerts()
                    
                # Calculate sleep time to maintain consistent intervals
                elapsed = (datetime.utcnow() - loop_start_time).total_seconds()
                sleep_time = max(45 - elapsed, 1)  # 45 second intervals
                
                await asyncio.sleep(sleep_time)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.logger.error(f"Error in trading loop: {e}")
                await self.alert_manager.send_alert(
                    Alert(
                        AlertType.SYSTEM_ERROR,
                        AlertLevel.ERROR,
                        f"Trading loop error: {str(e)}"
                    )
                )
                await asyncio.sleep(60)  # Wait before retry
                
    async def _fetch_market_data(self) -> Optional[Dict]:
        """Fetch and prepare market data"""
        try:
            # Get kline data
            perp_klines = self.kline_manager.get_klines('ETHUSDT', '1m')
            futures_klines = self.kline_manager.get_klines('ETHUSDT_240927', '1m')
            
            if not perp_klines or not futures_klines:
                self.logger.logger.warning("Kline data not available")
                return None
                
            # Get order book
            order_book = await self.executor.order_book_manager.fetch_order_book(
                'ETH/USDT:USDT-240927', 
                10
            )
            
            # Calculate spread percentage
            spread_pct = self.kline_manager.calculate_spread_percentage(
                'ETHUSDT', 
                'ETHUSDT_240927'
            )
            
            return {
                'timestamp': datetime.utcnow().timestamp(),
                'ETHUSDT': {
                    'close': perp_klines.get_close_prices().tolist(),
                    'latest': perp_klines.get_latest()
                },
                'ETHUSDT_240927': {
                    'close': futures_klines.get_close_prices().tolist(),
                    'latest': futures_klines.get_latest()
                },
                'order_book': {
                    'bids': [[level.price, level.quantity] for level in order_book.bids],
                    'asks': [[level.price, level.quantity] for level in order_book.asks]
                },
                'spread_pct': spread_pct
            }
            
        except Exception as e:
            self.logger.logger.error(f"Failed to fetch market data: {e}")
            return None
            
    async def _update_metrics(self):
        """Update monitoring metrics"""
        try:
            # Get current data
            balance = await self.exchange.fetch_balance()
            positions = await self.executor.get_positions()
            
            # Update metrics
            self.metrics_server.update_metrics({
                'balance': balance,
                'positions': positions
            })
            
            # Record spread
            spread_pct = self.kline_manager.calculate_spread_percentage(
                'ETHUSDT', 
                'ETHUSDT_240927'
            )
            if spread_pct is not None:
                self.metrics_server.collector.record_spread(
                    'ETH_PERP_FUT',
                    spread_pct
                )
                
        except Exception as e:
            self.logger.logger.error(f"Failed to update metrics: {e}")
            
    async def _check_alerts(self):
        """Check for alert conditions"""
        try:
            # Check balance
            balance = await self.exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {}).get('free', 0)
            await self.alert_manager.check_balance_alerts(usdt_balance)
            
            # Check positions
            positions = await self.executor.get_positions()
            for position in positions:
                await self.alert_manager.check_position_alerts(position.__dict__)
                
        except Exception as e:
            self.logger.logger.error(f"Failed to check alerts: {e}")
            
    async def _close_all_positions(self):
        """Close all open positions before shutdown"""
        try:
            self.logger.logger.info("Closing all positions...")
            await self.executor.close_all_positions()
            
            # Wait for orders to fill
            await asyncio.sleep(10)
            
            # Check if any positions remain
            positions = await self.executor.get_positions()
            if positions:
                self.logger.logger.warning(
                    f"{len(positions)} positions still open after close attempt"
                )
                
        except Exception as e:
            self.logger.logger.error(f"Failed to close positions: {e}")


async def main():
    """Main entry point"""
    # Setup logging
    setup_logging(
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_file=f"logs/trading_bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        log_format="colored" if sys.stdout.isatty() else "json"
    )
    
    logger = get_logger(__name__)
    
    try:
        # Load configuration
        env = os.getenv("ENVIRONMENT", "development")
        config = Config(env=env)
        
        # Check if using mock exchange
        use_mock = os.getenv("USE_MOCK_EXCHANGE", "false").lower() == "true"
        
        # Create and start bot
        bot = TradingBot(config, use_mock=use_mock)
        await bot.start()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Bot failed: {e}")
        raise
    finally:
        logger.info("Shutting down...")

if __name__ == "__main__":
    asyncio.run(main())