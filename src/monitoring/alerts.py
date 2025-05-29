"""Alert management system"""

import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import json
from src.utils.logger import get_logger

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertType(Enum):
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    LARGE_LOSS = "large_loss"
    RISK_LIMIT = "risk_limit"
    CONNECTION_ERROR = "connection_error"
    ORDER_FAILED = "order_failed"
    STRATEGY_ERROR = "strategy_error"
    LOW_BALANCE = "low_balance"
    HIGH_DRAWDOWN = "high_drawdown"
    SYSTEM_ERROR = "system_error"

class Alert:
    def __init__(self, alert_type: AlertType, level: AlertLevel, 
                 message: str, metadata: Optional[Dict] = None):
        self.id = datetime.utcnow().timestamp()
        self.timestamp = datetime.utcnow()
        self.type = alert_type
        self.level = level
        self.message = message
        self.metadata = metadata or {}
        self.sent = False
        
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'type': self.type.value,
            'level': self.level.value,
            'message': self.message,
            'metadata': self.metadata
        }

class AlertManager:
    """Manages alerts and notifications"""
    
    def __init__(self, config):
        self.config = config
        self.logger = get_logger(__name__)
        self.webhook_url = config.alert_webhook
        self.alerts_history: List[Alert] = []
        self.alert_rules: Dict[AlertType, Dict] = self._default_rules()
        self._rate_limits: Dict[str, datetime] = {}
        
    def _default_rules(self) -> Dict[AlertType, Dict]:
        """Default alert rules"""
        return {
            AlertType.LARGE_LOSS: {
                'threshold': 50.0,  # USDT
                'rate_limit_minutes': 30
            },
            AlertType.HIGH_DRAWDOWN: {
                'threshold': 0.05,  # 5%
                'rate_limit_minutes': 60
            },
            AlertType.LOW_BALANCE: {
                'threshold': 100.0,  # USDT
                'rate_limit_minutes': 120
            },
            AlertType.RISK_LIMIT: {
                'rate_limit_minutes': 15
            },
            AlertType.CONNECTION_ERROR: {
                'rate_limit_minutes': 5
            },
            AlertType.ORDER_FAILED: {
                'rate_limit_minutes': 5
            }
        }
        
    async def send_alert(self, alert: Alert):
        """Send alert through configured channels"""
        # Check rate limits
        if not self._check_rate_limit(alert):
            self.logger.debug(f"Alert rate limited: {alert.type.value}")
            return
            
        # Add to history
        self.alerts_history.append(alert)
        
        # Log alert
        log_method = getattr(self.logger, alert.level.value)
        log_method(f"Alert: {alert.message}")
        
        # Send to webhook if configured
        if self.webhook_url:
            await self._send_webhook(alert)
            
        alert.sent = True
        
    def _check_rate_limit(self, alert: Alert) -> bool:
        """Check if alert passes rate limiting"""
        rule = self.alert_rules.get(alert.type, {})
        rate_limit_minutes = rule.get('rate_limit_minutes', 0)
        
        if rate_limit_minutes == 0:
            return True
            
        key = f"{alert.type.value}_{alert.level.value}"
        last_sent = self._rate_limits.get(key)
        
        if last_sent:
            time_diff = (datetime.utcnow() - last_sent).total_seconds() / 60
            if time_diff < rate_limit_minutes:
                return False
                
        self._rate_limits[key] = datetime.utcnow()
        return True
        
    async def _send_webhook(self, alert: Alert):
        """Send alert to webhook"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = self._format_webhook_payload(alert)
                
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        self.logger.error(
                            f"Webhook failed: {response.status} - {await response.text()}"
                        )
                        
        except Exception as e:
            self.logger.error(f"Failed to send webhook: {e}")
            
    def _format_webhook_payload(self, alert: Alert) -> Dict:
        """Format alert for webhook (Slack format by default)"""
        color = {
            AlertLevel.INFO: "#36a64f",
            AlertLevel.WARNING: "#ff9800",
            AlertLevel.ERROR: "#f44336",
            AlertLevel.CRITICAL: "#9c27b0"
        }.get(alert.level, "#808080")
        
        fields = []
        for key, value in alert.metadata.items():
            fields.append({
                "title": key.replace('_', ' ').title(),
                "value": str(value),
                "short": True
            })
            
        return {
            "attachments": [{
                "color": color,
                "title": f"{alert.level.value.upper()}: {alert.type.value.replace('_', ' ').title()}",
                "text": alert.message,
                "fields": fields,
                "footer": "Trading Bot",
                "ts": int(alert.timestamp.timestamp())
            }]
        }
        
    async def check_position_alerts(self, position: Dict):
        """Check for position-related alerts"""
        # Large loss alert
        if position.get('pnl', 0) < -self.alert_rules[AlertType.LARGE_LOSS]['threshold']:
            await self.send_alert(Alert(
                AlertType.LARGE_LOSS,
                AlertLevel.WARNING,
                f"Large loss on {position['symbol']}: {position['pnl']:.2f} USDT",
                metadata=position
            ))
            
    async def check_balance_alerts(self, balance: float):
        """Check for balance-related alerts"""
        if balance < self.alert_rules[AlertType.LOW_BALANCE]['threshold']:
            await self.send_alert(Alert(
                AlertType.LOW_BALANCE,
                AlertLevel.WARNING,
                f"Low balance: {balance:.2f} USDT",
                metadata={'balance': balance}
            ))
            
    async def check_drawdown_alerts(self, drawdown: float):
        """Check for drawdown alerts"""
        if drawdown > self.alert_rules[AlertType.HIGH_DRAWDOWN]['threshold']:
            await self.send_alert(Alert(
                AlertType.HIGH_DRAWDOWN,
                AlertLevel.ERROR,
                f"High drawdown: {drawdown:.2%}",
                metadata={'drawdown': drawdown}
            ))
            
    def get_recent_alerts(self, hours: int = 24) -> List[Alert]:
        """Get recent alerts"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return [
            alert for alert in self.alerts_history
            if alert.timestamp > cutoff_time
        ]
