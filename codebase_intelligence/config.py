# codebase_intelligence/config.py
"""
Configuration for the Codebase Intelligence System.
"""

import os
from pathlib import Path
from typing import Dict, Any
import yaml


class SystemConfig:
    """System-wide configuration."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("config.yaml")
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or environment."""
        config = {
            "claude_code": {
                "api_key": os.getenv("CLAUDE_CODE_API_KEY", ""),
                "timeout": int(os.getenv("CLAUDE_CODE_TIMEOUT", "300")),
                "max_retries": int(os.getenv("CLAUDE_CODE_MAX_RETRIES", "3"))
            },
            "repository": {
                "path": os.getenv("REPO_PATH", "."),
                "branch": os.getenv("REPO_BRANCH", "main"),
                "lookback_days": int(os.getenv("LOOKBACK_DAYS", "7"))
            },
            "storage": {
                "docs_root": os.getenv("DOCS_ROOT", "./docs"),
                "graph_store": os.getenv("GRAPH_STORE", "./data/knowledge_graph"),
                "metrics_store": os.getenv("METRICS_STORE", "./data/metrics")
            },
            "notifications": {
                "slack_webhook": os.getenv("SLACK_WEBHOOK", ""),
                "email_config": {
                    "smtp_host": os.getenv("SMTP_HOST", ""),
                    "smtp_port": int(os.getenv("SMTP_PORT", "587")),
                    "from_email": os.getenv("FROM_EMAIL", "")
                }
            }
        }
        
        # Override with config file if it exists
        if self.config_path.exists():
            with open(self.config_path) as f:
                file_config = yaml.safe_load(f)
                config.update(file_config)
        
        return config
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-separated key."""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value