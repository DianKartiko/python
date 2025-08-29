# Flask Requirements
from flask import Flask, request, render_template
import threading
import requests
# Database System
import sqlite3
# Timezone Requirements
import datetime
import time
from zoneinfo import ZoneInfo  # Untuk timezone Indonesia
# MQTT Service 
import paho.mqtt.client as mqtt
# Telegram Requirements
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Bot
from telegram.ext import ContextTypes, ApplicationBuilder, CallbackQueryHandler, MessageHandler, filters
import asyncio
# Operatin System Requirements
from dotenv import load_dotenv
import os
# Logging System
import logging
# Excel Requirements
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

# Setup logging dengan timezone Indonesia
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# Basic Configuration
class TemperatureMonitorConfig:
    """Class untuk mengelola konfigurasi aplikasi"""
    
    def __init__(self):
        self.MQTT_BROKER = os.getenv("MQTT_BROKER")
        self.MQTT_PORT = 1883
        self.MQTT_TOPIC = os.getenv("MQTT_TOPIC")
        self.TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
        self.CHAT_ID = os.getenv("CHAT_ID")
        self.DATA_SAVE_INTERVAL = 600
        self.EXCEL_SEND_INTERVAL = 10800
        self.TEMPERATURE_OFFSET = 12.6
        self.INDONESIA_TZ = ZoneInfo("Asia/Jakarta")
        self.MIN_TEMP_ALERT = float(120)
        self.MAX_TEMP_ALERT = float(155)
        self.DB_PATH = "/data/data_suhu.db" if os.path.exists("/data") else "data_suhu.db"
        
        self.validate()
        
    def validate(self):
        """Validasi konfigurasi yang diperlukan"""
        if not all([self.MQTT_BROKER, self.MQTT_TOPIC, self.TELEGRAM_TOKEN, self.CHAT_ID]):
            logger.error("Missing required environment variables")
            exit(1)
            
        logger.info(f"Config loaded - Broker: {self.MQTT_BROKER}, Topic: {self.MQTT_TOPIC}")
        logger.info(f"Temperature offset: +{self.TEMPERATURE_OFFSET}°C")
        logger.info(f"Current Indonesia time: {self.format_indonesia_time()}")

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

class DatabaseManager:
    """Class untuk mengelola operasi database"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.initialize_database()
        
    def initialize_database(self):
        """Initialize database dengan table yang diperlukan"""
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS suhu (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                waktu TEXT,
                suhu REAL
            )
        """)
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at: {self.db_path}")
    
    def get_connection(self):
        """Mendapatkan koneksi database yang thread-safe"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    
    def insert_temperature(self, waktu, suhu):
        """Insert data suhu ke database"""
        try:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO suhu (waktu, suhu) VALUES (?, ?)", (waktu, suhu))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error inserting temperature: {e}")
            return False
    
    def get_recent_data(self, limit=5):
        """Mendapatkan data terbaru dari database"""
        try:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM suhu ORDER BY id DESC LIMIT ?", (limit,))
            result = c.fetchall()
            conn.close()
            return result
        except Exception as e:
            logger.error(f"Error getting recent data: {e}")
            return []
    
    def get_data_since(self, since_time):
        """Mendapatkan data sejak waktu tertentu"""
        try:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM suhu WHERE datetime(waktu) >= datetime(?) ORDER BY waktu", (since_time,))
            result = c.fetchall()
            conn.close()
            return result
        except Exception as e:
            logger.error(f"Error getting data since {since_time}: {e}")
            return []
    
    def get_statistics(self, since_time):
        """Mendapatkan statistik data"""
        try:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute("SELECT AVG(suhu), MIN(suhu), MAX(suhu) FROM suhu WHERE datetime(waktu) >= datetime(?)", (since_time,))
            result = c.fetchone()
            conn.close()
            return result
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return (None, None, None)

class MQTTService:
    """Class untuk mengelola koneksi dan komunikasi MQTT"""
    
    def __init__(self, config, data_callback):
        self.config = config
        self.data_callback = data_callback
        self.client = mqtt.Client()
        self.is_connected = False
        self.setup_callbacks()
        
    def setup_callbacks(self):
        """Setup callback functions untuk MQTT client"""
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback ketika terhubung ke MQTT broker"""
        if rc == 0:
            self.is_connected = True
            logger.info(f"MQTT Connected successfully at {self.config.format_indonesia_time()}")
            self.client.subscribe(self.config.MQTT_TOPIC)
            logger.info(f"Subscribed to topic: {self.config.MQTT_TOPIC}")
        else:
            logger.error(f"MQTT Connection failed with code {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Callback ketika menerima message MQTT"""
        try:
            raw_suhu = float(msg.payload.decode())
            if self.data_callback:
                self.data_callback(raw_suhu)
        except Exception as e:
            logger.error(f"Error parsing MQTT data: {e}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback ketika terputus dari MQTT broker"""
        self.is_connected = False
        logger.warning(f"MQTT Disconnected with code {rc} at {self.config.format_indonesia_time()}")
    
    def connect(self):
        """Connect ke MQTT broker dengan retry mechanism"""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                self.client.connect(self.config.MQTT_BROKER, self.config.MQTT_PORT, 60)
                self.client.loop_start()
                logger.info("MQTT Client started")
                return True
            except Exception as e:
                logger.error(f"MQTT Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying MQTT connection in 10 seconds...")
                    time.sleep(10)
        logger.error("Failed to connect to MQTT after all retries")
        return False
    
    def disconnect(self):
        """Disconnect dari MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()

class TelegramService:
    """Class untuk mengelola komunikasi Telegram"""
    
    def __init__(self, config, db_manager):
        self.config = config
        self.db_manager = db_manager
        self.bot = Bot(token=config.TELEGRAM_TOKEN) if config.TELEGRAM_TOKEN else None
        self.application = None
        self.setup_bot()
        
    def setup_bot(self):
        """Setup Telegram bot dengan handlers"""
        if self.config.TELEGRAM_TOKEN:
            self.application = ApplicationBuilder().token(self.config.TELEGRAM_TOKEN).build()
            self._setup_handlers()
        else:
            logger.warning("Telegram token not configured")
    
    def _setup_handlers(self):
        """Setup handlers untuk Telegram bot"""
        self.application.add_handler(MessageHandler(filters.Regex('^Mulai$'), self.start))
        self.application.add_handler(CallbackQueryHandler(self.button))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler untuk command /start"""
        keyboard = [
            [InlineKeyboardButton("Test Message", callback_data="test")],
            [InlineKeyboardButton("Data Dryers", callback_data="data")],
            [InlineKeyboardButton("Force Excel", callback_data="force_excel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Privasi mode disabled for Suhu @wijaya_suhu",
            reply_markup=reply_markup
        )
    
    async def button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler untuk inline keyboard buttons"""
        query = update.callback_query
        await query.answer()

        if query.data == "test":
            await self._handle_test(query)
        elif query.data == "data":
            await self._handle_data(query)
        elif query.data == "force_excel":
            await self._handle_force_excel(query)
    
    async def _handle_test(self, query):
        """Handler untuk test message"""
        current_time = self.config.format_indonesia_time()
        test_message = f"""🧪 Test Message dari Temperature Monitor

🕐 Waktu: {current_time}
⚙️ Offset: +{self.config.TEMPERATURE_OFFSET}°C
💾 Save: {self.config.DATA_SAVE_INTERVAL} detik
📊 Excel: {self.config.EXCEL_SEND_INTERVAL} detik

✅ Bot berfungsi normal!"""

        await query.edit_message_text(test_message)
    
    async def _handle_data(self, query):
        """Handler untuk menampilkan data"""
        recent_data = self.db_manager.get_recent_data(5)
        
        if recent_data:
            data_text = "📊 5 Data Terakhir Dryer 2:\n\n"
            for row in recent_data:
                data_text += f"🕐 {row[1]} WIB\n🌡️ {row[2]:.1f}°C\n\n"
        else:
            data_text = "❌ Tidak ada data tersedia"
            
        await query.edit_message_text(data_text)
    
    async def _handle_force_excel(self, query):
        """Handler untuk force excel generation"""
        await query.edit_message_text("📊 Generating Excel... Please wait...")
        
        try:
            rows = self.db_manager.get_recent_data(100)
            
            if not rows:
                await query.edit_message_text("❌ No data available")
                return
                
            wb = Workbook()
            ws = wb.active
            ws.title = "Data Suhu Dryer 2"
            ws.append(["ID", "Waktu (WIB)", "Suhu (°C)"])
            
            for row in rows:
                ws.append(row)
                
            temp_dir = "/tmp" if os.path.exists("/tmp") else "."
            filename = os.path.join(temp_dir, f"dryer2_suhu_{self.config.get_indonesia_time().strftime('%Y%m%d_%H%M')}.xlsx")
            wb.save(filename)
            
            caption = f"📊 Data Suhu Dryer 2 - {len(rows)} records\n🕐 {self.config.format_indonesia_time()}\n⚙️ Offset: +{self.config.TEMPERATURE_OFFSET}°C"
            
            # Send document
            with open(filename, "rb") as file:
                await self.bot.send_document(chat_id=query.message.chat_id, document=file, caption=caption)
            
            try:
                os.remove(filename)
            except:
                pass
                
            await query.edit_message_text(f"✅ Excel sent! {len(rows)} records")
            
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {str(e)}")
    
    async def send_message(self, message):
        """Mengirim message ke Telegram"""
        try:
            await self.bot.send_message(chat_id=self.config.CHAT_ID, text=message)
            return True
        except Exception as e:
            logger.error(f"Failed to send telegram message: {e}")
            return False
    
    async def send_document(self, file_path, caption):
        """Mengirim document ke Telegram"""
        try:
            with open(file_path, "rb") as file:
                await self.bot.send_document(chat_id=self.config.CHAT_ID, document=file, caption=caption)
            return True
        except Exception as e:
            logger.error(f"Failed to send telegram document: {e}")
            return False
    
    def start_polling(self):
        """Memulai Telegram bot polling"""
        if self.application:
            self.application.run_polling()

class BackgroundTask:
    """Base class untuk background tasks"""
    
    def __init__(self, interval, name="BackgroundTask"):
        self.interval = interval
        self.name = name
        self.thread = None
        self.is_running = False
    
    def task(self):
        """Method yang harus diimplementasikan oleh subclass"""
        raise NotImplementedError("Subclasses must implement this method")
    
    def run(self):
        """Main execution loop untuk background task"""
        self.is_running = True
        logger.info(f"Starting {self.name} - running every {self.interval} seconds")
        
        while self.is_running:
            try:
                self.task()
            except Exception as e:
                logger.error(f"Error in {self.name}: {e}")
            time.sleep(self.interval)
    
    def start(self):
        """Memulai background task"""
        self.thread = threading.Thread(target=self.run, daemon=True, name=self.name)
        self.thread.start()
        logger.info(f"{self.name} started")
    
    def stop(self):
        """Menghentikan background task"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
            logger.info(f"{self.name} stopped")

class DataSaveTask(BackgroundTask):
    """Task untuk menyimpan data ke database"""
    
    def __init__(self, config, data_provider, db_manager):
        super().__init__(config.DATA_SAVE_INTERVAL, "DataSaveTask")
        self.config = config
        self.data_provider = data_provider
        self.db_manager = db_manager
    
    def task(self):
        """Menyimpan data suhu ke database"""
        current_suhu = self.data_provider.get_latest_temperature()
        if current_suhu is not None:
            adjusted_suhu = self.config.apply_temperature_offset(current_suhu)
            waktu = self.config.format_indonesia_time_simple()
            success = self.db_manager.insert_temperature(waktu, adjusted_suhu)
            if success:
                logger.info(f"Data saved: {waktu} WIB | {adjusted_suhu:.2f}°C (raw: {current_suhu:.2f}°C)")
            else:
                logger.error("Failed to save data to database")
        else:
            logger.warning(f"No temperature data received from MQTT at {self.config.format_indonesia_time()}")

class ExcelSendTask(BackgroundTask):
    """Task untuk mengirim laporan Excel"""
    
    def __init__(self, config, db_manager, telegram_service):
        super().__init__(config.EXCEL_SEND_INTERVAL, "ExcelSendTask")
        self.config = config
        self.db_manager = db_manager
        self.telegram_service = telegram_service
    
    def task(self):
        """Mengirim laporan Excel ke Telegram"""
        current_time = self.config.format_indonesia_time()
        logger.info(f"Attempting to send Excel report at {current_time}")
        
        if not self.config.TELEGRAM_TOKEN or not self.config.CHAT_ID:
            logger.error("Missing Telegram credentials")
            return
        
        # Get data from last hour
        waktu_awal = (self.config.get_indonesia_time() - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        rows = self.db_manager.get_data_since(waktu_awal)
        
        if not rows:
            logger.warning(f"No data to send in Excel report (looking since {waktu_awal} WIB)")
            return

        # Create Excel file
        wb = Workbook()
        ws = wb.active
        ws.title = "Data Suhu"
        
        headers = ["ID", "Waktu (WIB)", "Suhu (°C)"]
        ws.append(headers)
        
        # Style headers
        try:
            for col in range(1, len(headers) + 1):
                cell = ws.cell(row=1, column=col)
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal='center')
        except Exception as e:
            logger.debug(f"Could not style Excel headers: {e}")
        
        # Add data rows
        for row in rows:
            ws.append(row)
        
        # Auto-adjust column widths
        try:
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        cell_length = len(str(cell.value))
                        if cell_length > max_length:
                            max_length = cell_length
                    except:
                        pass
                adjusted_width = min(max_length + 2, 30)
                ws.column_dimensions[column_letter].width = adjusted_width
        except Exception as e:
            logger.debug(f"Could not adjust column widths: {e}")

        # Save file
        temp_dir = "/tmp" if os.path.exists("/tmp") else "."
        filename = os.path.join(temp_dir, f"data_suhu_dryer2_{self.config.get_indonesia_time().strftime('%Y%m%d_%H%M')}.xlsx")
        wb.save(filename)
        logger.info(f"Excel file created: {filename} with {len(rows)} records")
        
        # Send file
        caption = f"📊 **Data Suhu Dryer2 - {len(rows)} records**\n🕐 {self.config.format_indonesia_time()}\n📅 Data 1 jam terakhir\n🌡️ Interval: {self.config.DATA_SAVE_INTERVAL//60} menit\n⚙️ Offset: +{self.config.TEMPERATURE_OFFSET}°C"
        
        # Run async function in thread
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success = loop.run_until_complete(self.telegram_service.send_document(filename, caption))
            loop.close()
            
            if success:
                logger.info(f"Excel file sent successfully: {filename}")
            else:
                logger.error(f"Failed to send Excel file: {filename}")
        except Exception as e:
            logger.error(f"Error sending Excel file: {e}")
        
        # Clean up
        try:
            os.remove(filename)
            logger.info(f"Temporary file deleted: {filename}")
        except OSError as e:
            logger.warning(f"Could not delete temporary file: {e}")

class KeepaliveTask(BackgroundTask):
    """Task untuk menjaga aplikasi tetap aktif"""
    
    def __init__(self, config):
        super().__init__(1800, "KeepaliveTask")  # 30 minutes
        self.config = config
    
    def task(self):
        """Mengirim ping untuk menjaga aplikasi tetap aktif"""
        app_url = os.getenv("FLY_APP_NAME", "")
        if app_url:
            try:
                response = requests.get(f"https://{app_url}.fly.dev/keepalive", timeout=10)
                logger.info(f"Self-ping sent at {self.config.format_indonesia_time()}, status: {response.status_code}")
            except Exception as e:
                logger.error(f"Keepalive error: {e}")

class MonitorDataTask(BackgroundTask):
    """Task untuk memantau konsistensi data"""
    
    def __init__(self, config, db_manager, telegram_service):
        super().__init__(3600, "MonitorDataTask")  # 1 hour
        self.config = config
        self.db_manager = db_manager
        self.telegram_service = telegram_service
        self.is_error_notified = False
    
    def task(self):
        """Memantau data dan mengirim notifikasi jika ada error"""
        # Ambil data 1 jam terakhir
        waktu_awal = (self.config.get_indonesia_time() - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        rows = self.db_manager.get_data_since(waktu_awal)

        if not rows:
            logger.warning("Tidak ada data dalam 1 jam terakhir untuk monitoring")
            return

        # Cek apakah semua suhu sama
        unique_values = set([round(row[2], 2) for row in rows if len(row) > 2 and row[2] is not None])
        
        # Kondisi Error Pertama
        if len(unique_values) == 1:
            # --- Kondisi jika terjadi error dan notif apakah sudah pernah dikirim
            if not self.is_error_notified:
                current_time = self.config.format_indonesia_time()
                suhu_error = list(unique_values)[0]
                
                logger.warning(f"Sistem error terdeteksi (suhu macet di {suhu_error}°C). Mengirim notifikasi.")
                error_message = (f"⚠️ *PERINGATAN SISTEM ERROR* ⚠️\n\n"
                                f"📅 Waktu: {current_time}\n"
                                f"🌡️ Suhu tidak berubah selama 1 jam terakhir.\n"
                                f"🔢 Nilai tetap: *{suhu_error:.2f}°C*\n"
                                f"📌 Kemungkinan sensor atau ESP32 mengalami macet.")

                # Kirim notifikasi dan langsung ubah status
                threading.Thread(target=lambda: asyncio.run(self.telegram_service.send_message(error_message))).start()
                self.is_error_notified = True
            else:
                logger.info("Sistem error masih terdeteksi, tetapi notifikasi sudah dikirim sebelumnya. Tidak ada tindakan.")
        
        # Kondisi 2: Sistem Kembali Normal (nilai suhu bervariasi)
        else:
            if self.is_error_notified:
                logger.info("Sistem kembali normal. Mereset status notifikasi error.")
                # Reset status agar siap mengirim notifikasi lagi jika error terjadi di masa depan
                self.is_error_notified = False
            else:
                logger.info("Data bervariasi, sistem pemantauan normal.")

class TemperatureMonitor:
    """Main class untuk mengelola seluruh aplikasi"""
    
    def __init__(self):
        # Initialize configuration
        self.config = TemperatureMonitorConfig()
        
        # Initialize components
        self.latest_temperature = None
        self.data_lock = threading.Lock()
        
        # --- TAMBAHKAN SATU BARIS INI ---
        # Status bisa: 'NORMAL', 'LOW', 'HIGH'
        self.current_alert_status = 'NORMAL'
        # --------------------------------
        
        # Database manager
        self.db_manager = DatabaseManager(self.config.DB_PATH)
        
        # MQTT service
        self.mqtt_service = MQTTService(self.config, self._on_mqtt_message)
        
        # Telegram service
        self.telegram_service = TelegramService(self.config, self.db_manager)
        
        # Background tasks
        self.tasks = []
    
    def _on_mqtt_message(self, raw_temperature):
        """Callback untuk MQTT messages"""
        adjusted_temperature = self.config.apply_temperature_offset(raw_temperature)
        
        with self.data_lock:
            self.latest_temperature = raw_temperature
        
        logger.info(f"MQTT Data received: {raw_temperature:.2f}°C (adjusted: {adjusted_temperature:.2f}°C) at {self.config.format_indonesia_time()}")
        
        # --- LOGIKA BARU DITAMBAHKAN (KIRIM NOTIFIKASI SUHU) ---
        current_hour = self.config.get_indonesia_time().hour
        # --- Tambah logika operasional pabrik jam 6 sampai 16.59
        if 6 <=current_hour < 17:
            # --- Logika notifikasi hanya bekerja di jam operasional 
            waktu_kejadian = self.config.format_indonesia_time()
            
            # Kondisi 1 Jika suhu terlalu TINGGI 
            if adjusted_temperature > self.config.MAX_TEMP_ALERT:
                if self.current_alert_status != "HIGH":
                    logger.warning(f"Suhu MELEBIHI batas: {adjusted_temperature:.1f}°C. Mengirim notifikasi.")
                    pesan = (f"🔥 *PERINGATAN: SUHU TINGGI* 🔥\n\n"
                             f"🌡️ Suhu saat ini: *{adjusted_temperature:.1f}°C*\n"
                            f"📈 Batas atas: {self.config.MAX_TEMP_ALERT}°C\n"
                            f"🕒 Waktu: {waktu_kejadian}")
                    
                    threading.Thread(target=lambda: asyncio.run(self.telegram_service.send_message(pesan))).start()
                    self.current_alert_status = 'HIGH'
            
            # Kondisi 2 Jika suhu terlalu RENDAH
            elif adjusted_temperature > self.config.MIN_TEMP_ALERT:
                if self.current_alert_status != "LOW":
                    logger.warning(f"Suhu MELEBIHI batas: {adjusted_temperature:.1f}°C. Mengirim notifikasi.")
                    pesan = (f"🔥 *PERINGATAN: SUHU TINGGI* 🔥\n\n"
                             f"🌡️ Suhu saat ini: *{adjusted_temperature:.1f}°C*\n"
                            f"📈 Batas atas: {self.config.MIN_TEMP_ALERT}°C\n"
                            f"🕒 Waktu: {waktu_kejadian}")
                    
                    threading.Thread(target=lambda: asyncio.run(self.telegram_service.send_message(pesan))).start()
                    self.current_alert_status = 'LOW'

            # Kondisi 3 Jika suhu masuk kategori Normal
            else:
                if self.current_alert_status != 'NORMAL':
                    logger.info(f"Suhu KEMBALI NORMAL: {adjusted_temperature:.1f}°C. Mengirim notifikasi.")
                    pesan = (f"✅ *INFORMASI: SUHU NORMAL* ✅\n\n"
                             f"🌡️ Suhu saat ini: *{adjusted_temperature:.1f}°C*\n"
                            f"👍 Kembali dalam rentang normal ({self.config.MIN_TEMP_ALERT}°C - {self.config.MAX_TEMP_ALERT}°C)\n"
                            f"🕒 Waktu: {waktu_kejadian}")
                    
                    threading.Thread(target=lambda: asyncio.run(self.telegram_service.send_message(pesan))).start()
                    self.current_alert_status = 'NORMAL'
                    
        else:
            # Di luar jam operasional, pastikan status kembali normal agar notifikasi siap untuk hari berikutnya
            if self.current_alert_status != 'NORMAL':
                logger.info("Di luar jam operasional. Mereset status notifikasi menjadi NORMAL.")
                self.current_alert_status = 'NORMAL'
                
                
    def get_latest_temperature(self):
        """Mendapatkan pembacaan suhu terbaru"""
        with self.data_lock:
            return self.latest_temperature
    
    def start_background_tasks(self):
        """Memulai semua background tasks"""
        # Data saving task
        data_save_task = DataSaveTask(self.config, self, self.db_manager)
        data_save_task.start()
        self.tasks.append(data_save_task)
        
        # Excel sending task
        excel_send_task = ExcelSendTask(self.config, self.db_manager, self.telegram_service)
        excel_send_task.start()
        self.tasks.append(excel_send_task)
        
        # Keepalive task
        keepalive_task = KeepaliveTask(self.config)
        keepalive_task.start()
        self.tasks.append(keepalive_task)
        
        # Monitor task
        monitor_task = MonitorDataTask(self.config, self.db_manager, self.telegram_service)
        monitor_task.start()
        self.tasks.append(monitor_task)
        
        logger.info("All background tasks started")
    
    def stop_background_tasks(self):
        """Menghentikan semua background tasks"""
        for task in self.tasks:
            task.stop()
        logger.info("All background tasks stopped")
    
    def create_flask_app(self):
        """Membuat dan mengkonfigurasi Flask app"""
        app = Flask(__name__)
        
        @app.route("/")
        def index():
            """Halaman utama"""
            with self.data_lock:
                current_raw_suhu = self.latest_temperature
                if current_raw_suhu is None: 
                    adjusted_suhu_str = "Data Belum Diterima"
                else:
                    current_adjusted_suhu = self.config.apply_temperature_offset(current_raw_suhu)
                    adjusted_suhu_str = f"{current_adjusted_suhu:.1f}"
            
            context = {
                "db_path": self.config.DB_PATH,
                "current_time": self.config.format_indonesia_time(),
                "save_interval": self.config.DATA_SAVE_INTERVAL,
                "excel_interval": self.config.EXCEL_SEND_INTERVAL,
                "current_suhu": adjusted_suhu_str,
                "timezone": "Asia/Jakarta (WIB)"
            }
            return render_template("index.html", **context)
        
        @app.route("/status")
        def status():
            """Endpoint untuk monitoring status"""
            try:
                # Get approximate count
                conn = self.db_manager.get_connection()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM suhu")
                total = c.fetchone()[0]
                conn.close()
                
                latest_records = self.db_manager.get_recent_data(5)
                
                # Get statistics for last 24 hours
                yesterday = (self.config.get_indonesia_time() - datetime.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
                stats = self.db_manager.get_statistics(yesterday)
                
                with self.data_lock:
                    current_mqtt_data = self.latest_temperature
                    adjusted_mqtt_data = self.config.apply_temperature_offset(current_mqtt_data) if current_mqtt_data else None
                
                return {
                    "status": "running",
                    "database_path": self.config.DB_PATH,
                    "total_records": total,
                    "latest_records": latest_records,
                    "latest_mqtt": {
                        "raw": current_mqtt_data,
                        "adjusted": adjusted_mqtt_data
                    },
                    "statistics_24h": {
                        "average": round(stats[0], 2) if stats[0] else None,
                        "minimum": stats[1],
                        "maximum": stats[2]
                    },
                    "temperature_offset": self.config.TEMPERATURE_OFFSET,
                    "intervals": {
                        "data_save_seconds": self.config.DATA_SAVE_INTERVAL,
                        "excel_send_seconds": self.config.EXCEL_SEND_INTERVAL
                    },
                    "mqtt_config": {
                        "broker": self.config.MQTT_BROKER,
                        "topic": self.config.MQTT_TOPIC,
                        "connected": self.mqtt_service.is_connected
                    },
                    "timestamp": self.config.format_indonesia_time(),
                    "timezone": "Asia/Jakarta (WIB)"
                }
            except Exception as e:
                logger.error(f"Status endpoint error: {e}")
                return {"error": str(e)}, 500
        
        @app.route("/keepalive")
        def keepalive():
            """Endpoint untuk keep container alive"""
            with self.data_lock:
                current_suhu = self.latest_temperature
                adjusted_suhu = self.config.apply_temperature_offset(current_suhu) if current_suhu else None
                
            return {
                "status": "alive", 
                "timestamp": self.config.format_indonesia_time(),
                "latest_suhu": {
                    "raw": current_suhu,
                    "adjusted": adjusted_suhu
                },
                "temperature_offset": self.config.TEMPERATURE_OFFSET,
                "timezone": "WIB",
                "next_save": f"{self.config.DATA_SAVE_INTERVAL} seconds",
                "next_excel": f"{self.config.EXCEL_SEND_INTERVAL} seconds"
            }
        
        @app.route("/test-telegram")
        def test_telegram():
            """Test Telegram bot connection"""
            try:
                current_time = self.config.format_indonesia_time()
                with self.data_lock:
                    raw_temp = self.latest_temperature
                    adjusted_temp = self.config.apply_temperature_offset(raw_temp) if raw_temp else None
                    
                message = f"🧪 **Test Message dari Temperature Monitor**\n🕐 {current_time}\n💾 Save: setiap {self.config.DATA_SAVE_INTERVAL} detik\n📊 Excel: setiap {self.config.EXCEL_SEND_INTERVAL} detik"
                if adjusted_temp:
                    message += f"\n🌡️ Latest Suhu Dryer 2: {adjusted_temp:.1f}°C"
                
                # Run async function in thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(self.telegram_service.send_message(message))
                loop.close()
                
                if success:
                    return {"status": "success", "message": "Test message sent", "time": current_time}
                else:
                    return {"status": "error", "message": "Failed to send message"}, 500
                    
            except Exception as e:
                logger.error(f"Telegram test failed: {e}")
                return {"error": str(e)}, 500
        
        return app
    
    def run(self):
        """Main execution method"""
        try:
            # Connect to MQTT
            if not self.mqtt_service.connect():
                logger.warning("MQTT connection failed, but continuing with server startup")
            
            # Start background tasks
            self.start_background_tasks()
            
            # Start Flask app in a separate thread
            app = self.create_flask_app()
            flask_thread = threading.Thread(
                target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080))),
                daemon=True
            )
            flask_thread.start()
            
            # Start Telegram bot polling (this will block)
            self.telegram_service.start_polling()
            
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.stop_background_tasks()
            self.mqtt_service.disconnect()


if __name__ == "__main__":
    monitor = TemperatureMonitor()
    monitor.run()
