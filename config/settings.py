import datetime
import logging
import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# Setup logging dengan timezone Indonesia
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

class TemperatureMonitorConfig:
    """Class untuk mengelola konfigurasi aplikasi"""
    
    def __init__(self):
        # MQTT Configuration
        self.MQTT_BROKER = os.getenv("MQTT_BROKER")
        self.MQTT_PORT = 1883
        self.MQTT_TOPICS = {
            "dryer1": os.getenv("MQTT_TOPIC_1"),
            "dryer2": os.getenv("MQTT_TOPIC_2"),
            "dryer3": os.getenv("MQTT_TOPIC_3"),
            # Tambahan untuk sistem baru
            "kedi1": os.getenv("MQTT_TOPIC_KEDI_1"),
            "kedi2": os.getenv("MQTT_TOPIC_KEDI_2"),
            "kedi3": os.getenv("MQTT_TOPIC_KEDI_3"),
            "kedi4": os.getenv("MQTT_TOPIC_KEDI_4"),
            # Sistem untuk boiler baru
            "boiler1": os.getenv("MQTT_TOPIC_BOILER_1"),
            "boiler2": os.getenv("MQTT_TOPIC_BOILER_2"),
            
            # Sistem untuk Kelembaban Kedi
            "humidity4" : os.getenv("MQTT_HUMIDITY_4")
        }
        
        # Telegram Configuration
        self.TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
        self.CHAT_ID = os.getenv("CHAT_ID")
        
        # Time and Temperature Configuration
        self.DATA_SAVE_INTERVAL = 600  # 10 menit
        self.TEMPERATURE_OFFSET = 12.6
        self.INDONESIA_TZ = ZoneInfo("Asia/Jakarta")
        self.MIN_TEMP_ALERT = float(120)
        self.MAX_TEMP_ALERT = float(155)
        
        # Database Configuration
        self.DB_PATH = "/data/data_suhu_multi.db" if os.path.exists("/data") else "data_suhu_multi.db"
        
        self.validate()
        
    def validate(self):
        """Validasi konfigurasi yang diperlukan"""
        if not all([self.MQTT_BROKER, self.TELEGRAM_TOKEN, self.CHAT_ID]):
            logger.error("Missing required environment variables")
            exit(1)
            
        logger.info(f"Config loaded - Broker: {self.MQTT_BROKER}")

    def get_indonesia_time(self):
        """Get current time in Indonesia timezone"""
        return datetime.datetime.now(self.INDONESIA_TZ)

    def format_indonesia_time(self, dt=None):
        """Format time in Indonesian format with timezone"""
        if dt is None:
            dt = self.get_indonesia_time()
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")

    def format_indonesia_time_simple(self, dt=None):
        """Format time in simple format without timezone for database"""
        if dt is None:
            dt = self.get_indonesia_time()
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def apply_temperature_offset(self, raw_temp):
        """Apply consistent temperature offset"""
        if raw_temp is None:
            return None
        return raw_temp + self.TEMPERATURE_OFFSET