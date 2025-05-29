from prometheus_client import Counter, Gauge, Histogram, start_http_server
import time
from typing import Dict

class MetricsCollector:
    def __init__(self):
        # Define metrics
        self.trades_total = Counter('trades_total', 'Total number of trades', 
                                   ['symbol', 'side', 'status'])
        self.position_pnl = Gauge('position_pnl', 'Current position PnL', 
                                 ['symbol'])
        self.balance_usdt = Gauge('balance_usdt', 'USDT balance')
        self.spread_percentage = Gauge('spread_percentage', 'Current spread percentage',
                                     ['pair'])
        self.order_latency = Histogram('order_latency_seconds', 
                                     'Order execution latency')
        self.api_requests = Counter('api_requests_total', 'Total API requests',
                                  ['exchange', 'endpoint', 'status'])
        
    def record_trade(self, symbol: str, side: str, status: str):
        self.trades_total.labels(symbol=symbol, side=side, status=status).inc()
        
    def update_position_pnl(self, symbol: str, pnl: float):
        self.position_pnl.labels(symbol=symbol).set(pnl)
        
    def update_balance(self, balance: float):
        self.balance_usdt.set(balance)
        
    def record_spread(self, pair: str, spread: float):
        self.spread_percentage.labels(pair=pair).set(spread)
        
    def record_order_latency(self, latency: float):
        self.order_latency.observe(latency)
        
    def record_api_request(self, exchange: str, endpoint: str, status: str):
        self.api_requests.labels(
            exchange=exchange, 
            endpoint=endpoint, 
            status=status
        ).inc()

class MetricsServer:
    def __init__(self, config):
        self.config = config
        self.collector = MetricsCollector()
        self.port = config.metrics_port
        
    async def start(self):
        """Start Prometheus metrics server"""
        start_http_server(self.port)
        
    def update_metrics(self, data: Dict):
        """Update all metrics"""
        if 'balance' in data:
            self.collector.update_balance(data['balance']['free']['USDT'])
            
        if 'positions' in data:
            for position in data['positions']:
                if position.status == 'open':
                    self.collector.update_position_pnl(
                        position.symbol, 
                        position.pnl
                    )