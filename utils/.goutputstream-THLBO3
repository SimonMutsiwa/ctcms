"""
Logging utilities
"""

import logging
import sys
from datetime import datetime
import json

class LoggerUtils:
    """Logging helper utilities"""
    
    @staticmethod
    def setup_logger(name, level=logging.INFO):
        """Setup logger with proper formatting"""
        logger = logging.getLogger(name)
        
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(level)
        
        return logger
    
    @staticmethod
    def log_audit_event(user_id, action, resource, details=None):
        """Log audit trail event"""
        logger = logging.getLogger('audit')
        
        event = {
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'action': action,
            'resource': resource,
            'details': details or {}
        }
        
        logger.info(json.dumps(event))
        return event

# Create default logger
default_logger = LoggerUtils.setup_logger('ctcms')