# codebase_intelligence/logging_config.py
"""
Centralized logging configuration for the Codebase Intelligence System.
"""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional

from .config import SystemConfig


class LoggingManager:
    """Manages centralized logging configuration."""
    
    _instance = None
    _configured = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._configured:
            self.config = SystemConfig()
            self._setup_logging()
            LoggingManager._configured = True
    
    def _setup_logging(self):
        """Configure logging based on system configuration."""
        logging_config = self.config.get("logging", {})
        
        # Get configuration values
        log_level = getattr(logging, logging_config.get("level", "INFO").upper())
        log_format = logging_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        log_file = logging_config.get("file_path", "./logs/codebase_intelligence.log")
        max_bytes = logging_config.get("max_bytes", 10485760)  # 10MB
        backup_count = logging_config.get("backup_count", 5)
        enable_console = logging_config.get("enable_console", True)
        enable_file = logging_config.get("enable_file", True)
        
        # Create formatter
        formatter = logging.Formatter(log_format)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Clear existing handlers to avoid duplicates
        root_logger.handlers.clear()
        
        # Add console handler if enabled
        if enable_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
        
        # Add file handler if enabled
        if enable_file:
            # Ensure log directory exists
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        
        # Configure specific loggers for our modules
        self._configure_module_loggers(log_level)
    
    def _configure_module_loggers(self, log_level: int):
        """Configure loggers for specific modules."""
        module_loggers = [
            "codebase_intelligence",
            "codebase_intelligence.assets",
            "codebase_intelligence.claude_integration",
            "codebase_intelligence.jobs",
            "codebase_intelligence.utils",
        ]
        
        for logger_name in module_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(log_level)
            # Don't add handlers here - they inherit from root logger
    
    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """Get a logger instance for the given name."""
        # Ensure logging is configured
        LoggingManager()
        return logging.getLogger(name)
    
    @staticmethod
    def set_level(level: str):
        """Dynamically change the logging level."""
        log_level = getattr(logging, level.upper())
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Update all handlers
        for handler in root_logger.handlers:
            handler.setLevel(log_level)


def get_logger(name: str) -> logging.Logger:
    """Convenience function to get a logger instance."""
    return LoggingManager.get_logger(name)


def setup_logging(config: Optional[SystemConfig] = None):
    """Setup centralized logging. Called once at application startup."""
    if config:
        LoggingManager._instance = None
        LoggingManager._configured = False
        manager = LoggingManager()
        manager.config = config
        manager._setup_logging()
    else:
        LoggingManager()