import requests
import logging
import os
from .base_task import BackgroundTask

logger = logging.getLogger(__name__)

class KeepaliveTask(BackgroundTask):
    """Task untuk menjaga aplikasi tetap aktif"""
    
    def __init__(self, config):
        super().__init__(1800, "KeepaliveTask")  # 30 minutes
        self.config = config
        
    def task(self):
        """Send keepalive request"""
        app_url = os.getenv("FLY_APP_NAME", "")
        if app_url:
            try:
                requests.get(f"https://{app_url}.fly.dev/keepalive", timeout=10)
                logger.info("Keepalive request sent successfully")
            except Exception as e:
                logger.error(f"Keepalive error: {e}")