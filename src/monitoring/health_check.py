"""Health check system"""

from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import asyncio
from dataclasses import dataclass
import psutil
import aiohttp
from src.utils.logger import get_logger

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class HealthCheck:
    name: str
    status: HealthStatus
    message: str
    last_check: datetime
    metadata: Dict = None
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'last_check': self.last_check.isoformat(),
            'metadata': self.metadata or {}
        }

class HealthMonitor:
    """Monitors system health"""
    
    def __init__(self, config):
        self.config = config
        self.logger = get_logger(__name__)
        self.checks: Dict[str, HealthCheck] = {}
        self._check_functions: Dict[str, Callable] = {}
        self._running = False
        
    def register_check(self, name: str, check_function: Callable):
        """Register a health check function"""
        self._check_functions[name] = check_function
        
    async def start(self):
        """Start health monitoring"""
        self._running = True
        self.logger.info("Health monitoring started")
        
        # Register default checks
        self._register_default_checks()
        
        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())
        
    async def stop(self):
        """Stop health monitoring"""
        self._running = False
        
    def _register_default_checks(self):
        """Register default health checks"""
        self.register_check("system_resources", self._check_system_resources)
        self.register_check("exchange_connection", self._check_exchange_connection)
        self.register_check("redis_connection", self._check_redis_connection)
        self.register_check("strategy_health", self._check_strategy_health)
        
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                await self._run_all_checks()
                await asyncio.sleep(self.config.health_check_interval)
            except Exception as e:
                self.logger.error(f"Error in health monitoring: {e}")
                await asyncio.sleep(60)
                
    async def _run_all_checks(self):
        """Run all registered health checks"""
        tasks = []
        for name, check_function in self._check_functions.items():
            tasks.append(self._run_check(name, check_function))
            
        await asyncio.gather(*tasks, return_exceptions=True)
        
    async def _run_check(self, name: str, check_function: Callable):
        """Run a single health check"""
        try:
            result = await check_function()
            self.checks[name] = HealthCheck(
                name=name,
                status=result['status'],
                message=result['message'],
                last_check=datetime.utcnow(),
                metadata=result.get('metadata', {})
            )
        except Exception as e:
            self.logger.error(f"Health check {name} failed: {e}")
            self.checks[name] = HealthCheck(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {str(e)}",
                last_check=datetime.utcnow()
            )
            
    async def _check_system_resources(self) -> Dict:
        """Check system resource usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            status = HealthStatus.HEALTHY
            messages = []
            
            if cpu_percent > 80:
                status = HealthStatus.DEGRADED
                messages.append(f"High CPU usage: {cpu_percent}%")
                
            if memory.percent > 85:
                status = HealthStatus.DEGRADED
                messages.append(f"High memory usage: {memory.percent}%")
                
            if disk.percent > 90:
                status = HealthStatus.UNHEALTHY
                messages.append(f"Low disk space: {disk.percent}% used")
                
            message = "; ".join(messages) if messages else "System resources OK"
            
            return {
                'status': status,
                'message': message,
                'metadata': {
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'disk_percent': disk.percent
                }
            }
        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': f"Failed to check system resources: {e}"
            }
            
    async def _check_exchange_connection(self) -> Dict:
        """Check exchange connection health"""
        # This will be implemented by the exchange instance
        return {
            'status': HealthStatus.HEALTHY,
            'message': 'Exchange connection check not implemented'
        }
        
    async def _check_redis_connection(self) -> Dict:
        """Check Redis connection health"""
        # This will be implemented by the state manager
        return {
            'status': HealthStatus.HEALTHY,
            'message': 'Redis connection check not implemented'
        }
        
    async def _check_strategy_health(self) -> Dict:
        """Check strategy health"""
        # This will be implemented by the strategy instance
        return {
            'status': HealthStatus.HEALTHY,
            'message': 'Strategy health check not implemented'
        }
        
    def get_status(self) -> Dict:
        """Get overall health status"""
        if not self.checks:
            return {
                'status': HealthStatus.UNHEALTHY.value,
                'message': 'No health checks have run yet',
                'checks': {}
            }
            
        # Determine overall status
        statuses = [check.status for check in self.checks.values()]
        
        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall_status = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall_status = HealthStatus.UNHEALTHY
        else:
            overall_status = HealthStatus.DEGRADED
            
        return {
            'status': overall_status.value,
            'message': f"{len(statuses)} checks completed",
            'checks': {name: check.to_dict() for name, check in self.checks.items()},
            'timestamp': datetime.utcnow().isoformat()
        }
        
    async def create_health_endpoint(self):
        """Create HTTP health endpoint"""
        from aiohttp import web
        
        async def health_handler(request):
            status = self.get_status()
            http_status = 200 if status['status'] == 'healthy' else 503
            return web.json_response(status, status=http_status)
            
        app = web.Application()
        app.router.add_get('/health', health_handler)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        
        self.logger.info("Health endpoint started on port 8080")