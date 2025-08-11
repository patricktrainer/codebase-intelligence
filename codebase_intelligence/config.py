# codebase_intelligence/config.py
"""
Configuration for the Codebase Intelligence System.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
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
                "timeout": int(os.getenv("CLAUDE_CODE_TIMEOUT", "600")),
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
            },
            "logging": {
                "level": os.getenv("LOG_LEVEL", "INFO"),
                "format": os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
                "file_path": os.getenv("LOG_FILE", "./logs/codebase_intelligence.log"),
                "max_bytes": int(os.getenv("LOG_MAX_BYTES", "10485760")),  # 10MB
                "backup_count": int(os.getenv("LOG_BACKUP_COUNT", "5")),
                "enable_console": os.getenv("LOG_ENABLE_CONSOLE", "true").lower() == "true",
                "enable_file": os.getenv("LOG_ENABLE_FILE", "true").lower() == "true"
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