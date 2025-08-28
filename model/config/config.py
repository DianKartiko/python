# config.py

import os
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
import logging

load_dotenv()

class Config:
    """
    Kelas untuk mengelola semua konfigurasi aplikasi dari environment variables.
    """
    # Konfigurasi MQTT
    MQTT_BROKER = os.getenv("MQTT_BROKER")
    MQTT_PORT = 1883
    MQTT_TOPIC = os.getenv("MQTT_TOPIC")

    # Konfigurasi Telegram
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    CHAT_ID = os.getenv("CHAT_ID")

    # Interval Operasional (dalam detik)
    DATA_SAVE_INTERVAL = 600    # 10 menit
    EXCEL_SEND_INTERVAL = 10800 # 3 jam
    MONITOR_INTERVAL = 3600     # 1 jam
    KEEPALIVE_INTERVAL = 1800   # 30 menit

    # Parameter Aplikasi
    TEMPERATURE_OFFSET = 12.6
    DB_PATH = "/data/data_suhu.db" if os.path.exists("/data") else "data_suhu.db"
    FLY_APP_NAME = os.getenv("FLY_APP_NAME", "")
    
    # Timezone
    INDONESIA_TZ = ZoneInfo("Asia/Jakarta")

    @staticmethod
    def validate():
        """Memvalidasi bahwa semua konfigurasi penting telah diatur."""
        logger = logging.getLogger(__name__)
        if not all([Config.MQTT_BROKER, Config.MQTT_TOPIC, Config.TELEGRAM_TOKEN, Config.CHAT_ID]):
            logger.error("FATAL: Variabel environment (MQTT/TELEGRAM) tidak lengkap!")
            exit(1)
        logger.info("Konfigurasi berhasil dimuat dan divalidasi.")