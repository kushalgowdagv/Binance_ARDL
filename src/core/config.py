from dataclasses import dataclass
from typing import Optional
import yaml
import os
from pathlib import Path

@dataclass
class ExchangeConfig:
    api_key: str
    api_secret: str
    testnet: bool = False
    rate_limit: int = 100
    
@dataclass
class StrategyConfig:
    symbols: list[str]
    interval: str
    entry_threshold: float
    exit_threshold: float
    position_size: float
    max_positions: int
    
@dataclass
class MonitoringConfig:
    metrics_port: int = 8000
    log_level: str = "INFO"
    alert_webhook: Optional[str] = None

class Config:
    def __init__(self, env: str = "development"):
        self.env = env
        self._load_config()
        
    def _load_config(self):
        config_path = Path(f"config/{self.env}.yaml")
        with open(config_path) as f:
            data = yaml.safe_load(f)
            
        # Override with environment variables
        self.exchange = ExchangeConfig(
            api_key=os.getenv("BINANCE_API_KEY", data["exchange"]["api_key"]),
            api_secret=os.getenv("BINANCE_API_SECRET", data["exchange"]["api_secret"]),
            testnet=data["exchange"].get("testnet", False)
        )
        
        self.strategy = StrategyConfig(**data["strategy"])
        self.monitoring = MonitoringConfig(**data.get("monitoring", {}))