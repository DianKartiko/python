from flask import Flask, request, render_template
import threading
import sqlite3
import datetime
import time
from zoneinfo import ZoneInfo  # Untuk timezone Indonesia
import paho.mqtt.client as mqtt
from openpyxl import Workbook
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Bot
from telegram.ext import ContextTypes, ApplicationBuilder, CallbackQueryHandler, MessageHandler, filters
import asyncio
from dotenv import load_dotenv
import os
import logging

# Setup logging dengan timezone Indonesia
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# === KONFIGURASI ===
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = 1883
MQTT_TOPIC = os.getenv("MQTT_TOPIC")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Interval saving data 
DATA_SAVE_INTERVAL = 60  # SETIAP 1 MENIT (60 DETIK)
EXCEL_SEND_INTERVAL = 3600  # SETIAP 1 JAM (3600 DETIK)

# KONSISTEN: Parameter offset suhu
TEMPERATURE_OFFSET = 20  # Tambah 35 derajat untuk semua pembacaan

# === TIMEZONE CONFIGURATION ===
INDONESIA_TZ = ZoneInfo("Asia/Jakarta")  # WIB (GMT+7)
# Alternatif timezone Indonesia:
# INDONESIA_TZ = ZoneInfo("Asia/Makassar")  # WITA (GMT+8) 
# INDONESIA_TZ = ZoneInfo("Asia/Jayapura")  # WIT (GMT+9)

def get_indonesia_time():
    """Get current time in Indonesia timezone"""
    return datetime.datetime.now(INDONESIA_TZ)

def format_indonesia_time(dt=None):
    """Format time in Indonesian format with timezone"""
    if dt is None:
        dt = get_indonesia_time()
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")

def format_indonesia_time_simple(dt=None):
    """Format time in simple format without timezone for database"""
    if dt is None:
        dt = get_indonesia_time()
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def apply_temperature_offset(raw_temp):
    """Apply consistent temperature offset"""
    if raw_temp is None:
        return None
    return raw_temp + TEMPERATURE_OFFSET

# Validasi konfigurasi
if not all([MQTT_BROKER, MQTT_TOPIC, TELEGRAM_TOKEN, CHAT_ID]):
    logger.error("Missing required environment variables")
    exit(1)

logger.info(f"Config loaded - Broker: {MQTT_BROKER}, Topic: {MQTT_TOPIC}, Chat ID: {CHAT_ID}")
logger.info(f"Temperature offset: +{TEMPERATURE_OFFSET}°C")
logger.info(f"Current Indonesia time: {format_indonesia_time()}")

# === DATABASE === 
DB_PATH = "/data/data_suhu.db" if os.path.exists("/data") else "data_suhu.db"

# PERBAIKAN: Thread-safe database connection
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")  # Better for concurrent access
    return conn

# Initialize database
conn = get_db_connection()
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
logger.info(f"Database initialized at: {DB_PATH}")

# === VARIABEL PENAMPUNG ===
latest_suhu = None
data_lock = threading.Lock()  # PERBAIKAN: Thread safety

# === MQTT CALLBACK ===
def on_message(client, userdata, msg):
    global latest_suhu
    try:
        raw_suhu = float(msg.payload.decode())
        adjusted_suhu = apply_temperature_offset(raw_suhu)
        
        with data_lock:
            latest_suhu = raw_suhu  # Simpan nilai mentah untuk referensi
            
        # Log dengan timezone Indonesia dan nilai yang sudah disesuaikan
        logger.info(f"MQTT Data received: {raw_suhu:.2f}°C (adjusted: {adjusted_suhu:.2f}°C) at {format_indonesia_time()}")
    except Exception as e:
        logger.error(f"Error parsing MQTT data: {e}")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f"MQTT Connected successfully at {format_indonesia_time()}")
        client.subscribe(MQTT_TOPIC)
        logger.info(f"Subscribed to topic: {MQTT_TOPIC}")
    else:
        logger.error(f"MQTT Connection failed with code {rc}")

def on_disconnect(client, userdata, rc):
    logger.warning(f"MQTT Disconnected with code {rc} at {format_indonesia_time()}")

# PERBAIKAN: Better MQTT client setup
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

# PERBAIKAN: Retry connection logic
def connect_mqtt():
    max_retries = 5
    for attempt in range(max_retries):
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            client.loop_start()
            logger.info("MQTT Client started")
            return True
        except Exception as e:
            logger.error(f"MQTT Connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying MQTT connection in 10 seconds...")
                time.sleep(10)
    logger.error("Failed to connect to MQTT after all retries")
    return False

# Start MQTT connection
mqtt_connected = connect_mqtt()
if not mqtt_connected:
    logger.warning("MQTT connection failed, but continuing with server startup")

# === BACKGROUND TASKS ===
def save_data_task():
    global latest_suhu
    logger.info(f"Starting data save task - saving every {DATA_SAVE_INTERVAL} seconds")
    
    while True:
        try:
            time.sleep(DATA_SAVE_INTERVAL)  # 1 menit
            
            with data_lock:
                current_suhu = latest_suhu
            
            if current_suhu is not None:
                # KONSISTEN: Gunakan fungsi apply_temperature_offset
                adjusted_suhu = apply_temperature_offset(current_suhu)
                
                conn = get_db_connection()
                c = conn.cursor()
                waktu = format_indonesia_time_simple()  # Menggunakan waktu Indonesia
                c.execute("INSERT INTO suhu (waktu, suhu) VALUES (?, ?)", (waktu, adjusted_suhu))
                conn.commit()
                conn.close()
                logger.info(f"Data saved: {waktu} WIB | {adjusted_suhu:.2f}°C (raw: {current_suhu:.2f}°C)")
            else:
                logger.warning(f"No temperature data received from MQTT at {format_indonesia_time()}")
                
        except Exception as e:
            logger.error(f"Error saving data: {e}")

async def send_telegram_message(message):
    """Helper function to send telegram message asynchronously"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=CHAT_ID, text=message)
        return True
    except Exception as e:
        logger.error(f"Failed to send telegram message: {e}")
        return False

async def send_telegram_document(file_path, caption):
    """Helper function to send telegram document asynchronously"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        with open(file_path, "rb") as file:
            await bot.send_document(chat_id=CHAT_ID, document=file, caption=caption)
        return True
    except Exception as e:
        logger.error(f"Failed to send telegram document: {e}")
        return False

def run_async_in_thread(coro):
    """Helper to run async function in thread"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()

def send_excel_task():
    logger.info(f"Starting Excel send task - sending every {EXCEL_SEND_INTERVAL} seconds")
    
    # PERBAIKAN: Wait for initial data
    initial_wait = 120  # 2 minutes
    logger.info(f"Waiting {initial_wait} seconds for initial data...")
    time.sleep(initial_wait)
    
    while True:
        try:
            current_time = format_indonesia_time()
            logger.info(f"Attempting to send Excel report at {current_time}")
            
            # PERBAIKAN: Check if bot token and chat_id are valid
            if not TELEGRAM_TOKEN or not CHAT_ID:
                logger.error("Missing Telegram credentials")
                time.sleep(EXCEL_SEND_INTERVAL)
                continue
            
            # Get data from last hour using Indonesia time
            waktu_awal = (get_indonesia_time() - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM suhu WHERE datetime(waktu) >= datetime(?) ORDER BY waktu", (waktu_awal,))
            rows = c.fetchall()
            conn.close()
            
            if not rows:
                logger.warning(f"No data to send in Excel report (looking since {waktu_awal} WIB)")
                time.sleep(EXCEL_SEND_INTERVAL)
                continue

            # Create Excel file with better formatting
            wb = Workbook()
            ws = wb.active
            ws.title = "Data Suhu"
            
            # PERBAIKAN: Add headers with Indonesian labels
            headers = ["ID", "Waktu (WIB)", "Suhu (°C)"]
            ws.append(headers)
            
            # PERBAIKAN: Style headers if possible
            try:
                from openpyxl.styles import Font, Alignment
                for col in range(1, len(headers) + 1):
                    cell = ws.cell(row=1, column=col)
                    cell.font = Font(bold=True)
                    cell.alignment = Alignment(horizontal='center')
            except ImportError:
                logger.debug("openpyxl styles not available, skipping formatting")
            
            # Add data rows - suhu sudah ter-offset dari database
            for row in rows:
                ws.append(row)
            
            # PERBAIKAN: Auto-adjust column widths
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

            # PERBAIKAN: Use temp directory and better filename with Indonesia time
            temp_dir = "/tmp" if os.path.exists("/tmp") else "."
            filename = os.path.join(temp_dir, f"data_suhu_dryer2_{get_indonesia_time().strftime('%Y%m%d_%H%M')}.xlsx")
            
            wb.save(filename)
            logger.info(f"Excel file created: {filename} with {len(rows)} records")
            
            # Send file using async function with Indonesia time
            caption = f"📊 **Data Suhu Dryer2 - {len(rows)} records**\n🕐 {format_indonesia_time()}\n📅 Data 1 jam terakhir\n🌡️ Interval: {DATA_SAVE_INTERVAL//60} menit\n⚙️ Offset: +{TEMPERATURE_OFFSET}°C"
            success = run_async_in_thread(send_telegram_document(filename, caption))
            
            if success:
                logger.info(f"Excel file sent successfully: {filename}")
            else:
                logger.error(f"Failed to send Excel file: {filename}")
            
            # Clean up
            try:
                os.remove(filename)
                logger.info(f"Temporary file deleted: {filename}")
            except OSError as e:
                logger.warning(f"Could not delete temporary file: {e}")
                
        except Exception as e:
            logger.error(f"Error in send_excel_task: {e}")
            
        # PERBAIKAN: Always wait full interval regardless of success/failure
        logger.info(f"Waiting {EXCEL_SEND_INTERVAL} seconds for next Excel report...")
        time.sleep(EXCEL_SEND_INTERVAL)

def keepalive_task():
    logger.info("Starting keepalive task")
    while True:
        try:
            time.sleep(1800)  # 30 minutes
            app_url = os.getenv("FLY_APP_NAME", "")
            if app_url:
                import requests
                response = requests.get(f"https://{app_url}.fly.dev/keepalive", timeout=10)
                logger.info(f"Self-ping sent at {format_indonesia_time()}, status: {response.status_code}")
        except Exception as e:
            logger.error(f"Keepalive error: {e}")

# PERBAIKAN: Better error handling for threads
def start_background_tasks():
    try:
        # Start data saving task
        save_thread = threading.Thread(target=save_data_task, daemon=True, name="SaveDataTask")
        save_thread.start()
        logger.info("Save data task started")
        
        # Start Excel sending task
        excel_thread = threading.Thread(target=send_excel_task, daemon=True, name="SendExcelTask")
        excel_thread.start()
        logger.info("Send Excel task started")
        
        # Start keepalive task
        keepalive_thread = threading.Thread(target=keepalive_task, daemon=True, name="KeepaliveTask")
        keepalive_thread.start()
        logger.info("Keepalive task started")
        
    except Exception as e:
        logger.error(f"Error starting background tasks: {e}")

start_background_tasks()

# === Adding Command Handler ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler with inline keyboard"""
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

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses"""
    query = update.callback_query
    await query.answer()

    if query.data == "test":
        # Test message functionality
        current_time = format_indonesia_time()
        with data_lock:
            raw_temp = latest_suhu
            adjusted_temp = apply_temperature_offset(raw_temp)
            
        test_message = f"""🧪 Test Message dari Temperature Monitor

🕐 Waktu: {current_time}
🌡️ Suhu Dryer 2: {adjusted_temp:.1f}°C 
⚙️ Offset: +{TEMPERATURE_OFFSET}°C
💾 Save: {DATA_SAVE_INTERVAL} detik
📊 Excel: {EXCEL_SEND_INTERVAL} detik

✅ Bot berfungsi normal!"""

        await query.edit_message_text(test_message)

    elif query.data == "data":
        # Show recent data
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT waktu, suhu FROM suhu ORDER BY id DESC LIMIT 5")
            recent_data = c.fetchall()
            conn.close()
            
            if recent_data:
                data_text = "📊 5 Data Terakhir Dryer 2:\n\n"
                for row in recent_data:
                    data_text += f"🕐 {row[0]} WIB\n🌡️ {row[1]:.1f}°C\n\n"
            else:
                data_text = "❌ Tidak ada data tersedia"
                
            await query.edit_message_text(data_text)
            
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {str(e)}")

    elif query.data == "force_excel":
        # Force Excel generation
        await query.edit_message_text("📊 Generating Excel... Please wait...")
        
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM suhu ORDER BY id DESC LIMIT 100")
            rows = c.fetchall()
            conn.close()
            
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
            filename = os.path.join(temp_dir, f"dryer2_suhu_{get_indonesia_time().strftime('%Y%m%d_%H%M')}.xlsx")
            wb.save(filename)
            
            caption = f"📊 Data Suhu Dryer 2 - {len(rows)} records\n🕐 {format_indonesia_time()}\n⚙️ Offset: +{TEMPERATURE_OFFSET}°C"
            
            # Send document
            bot = Bot(token=TELEGRAM_TOKEN)
            with open(filename, "rb") as file:
                await bot.send_document(chat_id=query.message.chat_id, document=file, caption=caption)
            
            try:
                os.remove(filename)
            except:
                pass
                
            await query.edit_message_text(f"✅ Excel sent! {len(rows)} records")
            
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {str(e)}")

# === FLASK APP ===
app = Flask(__name__)

@app.route("/")
def index():
    """Menampilkan halaman utama dengan menggunakan tempalte HTML"""
    with data_lock:
        current_raw_suhu = latest_suhu

        if current_raw_suhu is None: 
            adjusted_suhu_string = "Data Belum Diterima"
        else:
            current_adjusted_suhu = apply_temperature_offset(current_raw_suhu)
            adjusted_suhu_str = f"{current_adjusted_suhu:.1f}"
        
    context = {
        "db_path": DB_PATH,
        "current_time": format_indonesia_time(),
        "save_interval": DATA_SAVE_INTERVAL,
        "excel_interval": EXCEL_SEND_INTERVAL,
        "current_suhu": adjusted_suhu_str,
        "timezone": "Asia/Jakarta (WIB)"
    }
    return render_template("index.html", **context)

@app.route("/status")
def status():
    """Status endpoint untuk monitoring"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM suhu")
        total = c.fetchone()[0]
        
        c.execute("SELECT * FROM suhu ORDER BY id DESC LIMIT 5")
        latest_records = c.fetchall()
        
        # PERBAIKAN: Get statistics for last 24 hours
        yesterday = (get_indonesia_time() - datetime.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("SELECT AVG(suhu), MIN(suhu), MAX(suhu) FROM suhu WHERE datetime(waktu) >= datetime(?)", (yesterday,))
        stats = c.fetchone()
        
        conn.close()
        
        with data_lock:
            current_mqtt_data = latest_suhu
            adjusted_mqtt_data = apply_temperature_offset(current_mqtt_data)
        
        return {
            "status": "running",
            "database_path": DB_PATH,
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
            "temperature_offset": TEMPERATURE_OFFSET,
            "intervals": {
                "data_save_seconds": DATA_SAVE_INTERVAL,
                "excel_send_seconds": EXCEL_SEND_INTERVAL
            },
            "mqtt_config": {
                "broker": MQTT_BROKER,
                "topic": MQTT_TOPIC,
                "connected": mqtt_connected
            },
            "timestamp": format_indonesia_time(),
            "timezone": "Asia/Jakarta (WIB)"
        }
    except Exception as e:
        logger.error(f"Status endpoint error: {e}")
        return {"error": str(e)}, 500

@app.route("/keepalive")
def keepalive():
    """Endpoint untuk keep container alive"""
    with data_lock:
        current_suhu = latest_suhu
        adjusted_suhu = apply_temperature_offset(current_suhu)
        
    return {
        "status": "alive", 
        "timestamp": format_indonesia_time(),
        "latest_suhu": {
            "raw": current_suhu,
            "adjusted": adjusted_suhu
        },
        "temperature_offset": TEMPERATURE_OFFSET,
        "timezone": "WIB",
        "next_save": f"{DATA_SAVE_INTERVAL} seconds",
        "next_excel": f"{EXCEL_SEND_INTERVAL} seconds"
    }

@app.route("/test-telegram")
def test_telegram():
    """Test Telegram bot connection"""
    try:
        current_time = format_indonesia_time()
        with data_lock:
            raw_temp = latest_suhu
            adjusted_temp = apply_temperature_offset(raw_temp)
            
        message = f"🧪 **Test Message dari Temperature Monitor**\n🕐 {current_time}\n💾 Save: setiap {DATA_SAVE_INTERVAL} detik\n📊 Excel: setiap {EXCEL_SEND_INTERVAL} detik\n🌡️ Latest Suhu Dryer 2: {adjusted_temp:.1f}°C"
        success = run_async_in_thread(send_telegram_message(message))
        
        if success:
            return {"status": "success", "message": "Test message sent", "time": current_time}
        else:
            return {"status": "error", "message": "Failed to send message"}, 500
            
    except Exception as e:
        logger.error(f"Telegram test failed: {e}")
        return {"error": str(e)}, 500

@app.route("/force-excel")
def force_excel():
    """Force send Excel report (for testing)"""
    try:
        logger.info(f"Force Excel requested at {format_indonesia_time()}")
        
        # Get recent data
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM suhu ORDER BY id DESC LIMIT 100")
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            return {"status": "error", "message": "No data available"}, 404
            
        wb = Workbook()
        ws = wb.active
        ws.title = "Data Suhu (Manual)"
        ws.append(["ID", "Waktu (WIB)", "Suhu (°C)"])
        
        for row in rows:
            ws.append(row)
            
        temp_dir = "/tmp" if os.path.exists("/tmp") else "."
        filename = os.path.join(temp_dir, f"manual_data_suhu_dryer2_{get_indonesia_time().strftime('%Y%m%d_%H%M%S')}.xlsx")
        wb.save(filename)
        
        caption = f"🔧 **Manual Excel Report**\n📊 {len(rows)} records\n🕐 {format_indonesia_time()}\n📤 Sent manually\n⚙️ Offset: +{TEMPERATURE_OFFSET}°C"
        success = run_async_in_thread(send_telegram_document(filename, caption))
        
        try:
            os.remove(filename)
        except:
            pass
            
        if success:
            return {"status": "success", "message": f"Manual Excel sent with {len(rows)} records"}
        else:
            return {"status": "error", "message": "Failed to send Excel"}, 500
            
    except Exception as e:
        logger.error(f"Force Excel failed: {e}")
        return {"error": str(e)}, 500

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    logger.info(f"Webhook data received at {format_indonesia_time()}: {data}")
    return "OK", 200

if __name__ == "__main__":
    def run_flask():
        port = int(os.environ.get("PORT", 8080))
        logger.info(f"Starting Flask app on port {port} at {format_indonesia_time()}")
        logger.info(f"Temperature offset configured: +{TEMPERATURE_OFFSET}°C")
        app.run(host="0.0.0.0", port=port)

    flask_thread = threading.Thread(target=run_flask, daemon=True, name="FlaskThread")

    flask_thread.start()

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Dispatcher
    application.add_handler(MessageHandler(filters.Regex('^Mulai$'), start))
    application.add_handler(CallbackQueryHandler(button))

    application.run_polling() 

