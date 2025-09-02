import datetime
import logging
from .base_task import BackgroundTask

logger = logging.getLogger(__name__)

class MonitorDataTask(BackgroundTask):
    """Task untuk monitoring data dan deteksi error sistem"""
    
    def __init__(self, config, db_manager, telegram_service):
        super().__init__(3600, "MonitorDataTask")  # 1 hour
        self.config = config
        self.db_manager = db_manager
        self.telegram_service = telegram_service
        self.is_error_notified = {"dryer": False, "kedi": False, "boiler": False}
        
    def task(self):
        """Monitor semua sistem untuk deteksi error"""
        waktu_awal = (self.config.get_indonesia_time() - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Check each system
        systems = ["dryer", "kedi", "boiler"]
        for system in systems:
            self._check_system_error(system, waktu_awal)
    
    def _check_system_error(self, system_type, since_time):
        """Check specific system for errors"""
        rows = self.db_manager.get_data_since(since_time, system_type)
        if not rows:
            return
        
        unique_values = set([round(row[3], 2) for row in rows if len(row) > 3 and row[3] is not None])
        
        if len(unique_values) == 1:
            if not self.is_error_notified[system_type]:
                suhu_error = list(unique_values)[0]
                error_message = f"⚠️ *PERINGATAN SISTEM ERROR - {system_type.upper()}* ⚠️\n\nSuhu macet di *{suhu_error:.2f}°C*."
                self.telegram_service.send_message(error_message)
                self.is_error_notified[system_type] = True
                logger.warning(f"Error detected in {system_type} system: temperature stuck at {suhu_error}°C")
        else:
            if self.is_error_notified[system_type]:
                self.is_error_notified[system_type] = False
                logger.info(f"{system_type.title()} system error resolved")