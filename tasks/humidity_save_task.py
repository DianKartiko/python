import threading
import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class HumiditySaveTask:
    """Background task untuk menyimpan data humidity secara berkala"""

    def __init__(self, config, monitor_instance, db_manager):
        self.config = config
        self.monitor = monitor_instance
        self.db_manager = db_manager
        self.running = False
        self.thread = None
        self.humidity_buffer = defaultdict(list)
        self.buffer_lock = threading.Lock()

    def add_humidity_data(self, device_id, humidity_value):
        """Tambahkan data humidity ke buffer"""
        with self.buffer_lock:
            timestamp = self.config.format_indonesia_time_simple()
            self.humidity_buffer[device_id].append((timestamp, humidity_value))

    def start(self):
        """Mulai background task"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            logger.info("HumiditySaveTask started")

    def stop(self):
        """Stop background task"""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("HumiditySaveTask stopped")

    def _run(self):
        """Main loop untuk save humidity data"""
        while self.running:
            try:
                time.sleep(self.config.DATA_SAVE_INTERVAL)  # 10 menit
                self._save_buffered_humidity()
            except Exception as e:
                logger.error(f"Error in HumiditySaveTask: {e}")

    def _save_buffered_humidity(self):
        """Save semua buffered humidity data ke database"""
        with self.buffer_lock:
            for device_id, data_list in self.humidity_buffer.items():
                for timestamp, humidity in data_list:
                    success = self.db_manager.insert_humidity(
                        timestamp, device_id, humidity, "kedi"
                    )
                    if success:
                        logger.info(
                            f"Humidity data saved: {device_id} = {humidity}% at {timestamp}"
                        )

            # Clear buffer after saving
            self.humidity_buffer.clear()
