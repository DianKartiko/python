from flask import Flask, request
import threading
import sqlite3
import datetime
import time
from zoneinfo import ZoneInfo  # Python 3.9+
# Alternatif untuk Python < 3.9: pip install pytz
import paho.mqtt.client as mqtt
from openpyxl import Workbook
import telegram
import asyncio
from dotenv import load_dotenv
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# === KONFIGURASI ===
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = 1883
MQTT_TOPIC = os.getenv("MQTT_TOPIC")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# === INTERVAL KONFIGURASI ===
DATA_SAVE_INTERVAL = 300  # 5 menit (300 detik)
EXCEL_SEND_INTERVAL = 10800  # 3 jam (10800 detik)

# Validasi konfigurasi
if not all([MQTT_BROKER, MQTT_TOPIC, TELEGRAM_TOKEN, CHAT_ID]):
    logger.error("Missing required environment variables")
    exit(1)

logger.info(f"Config loaded - Broker: {MQTT_BROKER}, Topic: {MQTT_TOPIC}, Chat ID: {CHAT_ID}")
logger.info(f"Intervals - Data Save: {DATA_SAVE_INTERVAL//60} minutes, Excel Send: {EXCEL_SEND_INTERVAL//3600} hours")

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

# === TIMEZONE CONFIGURATION ===
INDONESIA_TZ = ZoneInfo("Asia/Jakarta")  # WIB (GMT+7)
# INDONESIA_TZ = ZoneInfo("Asia/Makassar")  # WITA (GMT+8) 
# INDONESIA_TZ = ZoneInfo("Asia/Jayapura")  # WIT (GMT+9)

def get_indonesia_time():
    """Get current time in Indonesia timezone"""
    return datetime.datetime.now(INDONESIA_TZ)

def format_indonesia_time(dt=None):
    """Format time in Indonesian format with timezone"""
    if dt is None:
        dt = get_indonesia_time()
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")  # Include timezone info

# === VARIABEL PENAMPUNG ===
latest_suhu = None
data_lock = threading.Lock()  # PERBAIKAN: Thread safety

# === MQTT CALLBACK ===
def on_message(client, userdata, msg):
    global latest_suhu
    try:
        suhu = float(msg.payload.decode())
        with data_lock:
            latest_suhu = suhu
        logger.info(f"MQTT Data received: {suhu + 30}°C")
    except Exception as e:
        logger.error(f"Error parsing MQTT data: {e}")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("MQTT Connected successfully")
        client.subscribe(MQTT_TOPIC)
    else:
        logger.error(f"MQTT Connection failed with code {rc}")

def on_disconnect(client, userdata, rc):
    logger.warning(f"MQTT Disconnected with code {rc}")

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
                time.sleep(10)
    return False

connect_mqtt()

# === BACKGROUND TASKS ===
def save_data_task():
    global latest_suhu
    logger.info(f"Starting data save task - saving every {DATA_SAVE_INTERVAL//60} minutes")
    
    while True:
        try:
            time.sleep(DATA_SAVE_INTERVAL)  # 5 menit (300 detik)
            
            with data_lock:
                current_suhu = latest_suhu
            
            if current_suhu is not None:
                # Tambahkan offset 30 derajat
                adjusted_suhu = current_suhu + 30
                
                conn = get_db_connection()
                c = conn.cursor()
                waktu = format_indonesia_time()  # Menggunakan waktu Indonesia
                c.execute("INSERT INTO suhu (waktu, suhu) VALUES (?, ?)", (waktu, adjusted_suhu))
                conn.commit()
                conn.close()
                logger.info(f"Data saved: {waktu} | {adjusted_suhu:.2f}°C")
            else:
                logger.warning("No temperature data received from MQTT")
                
        except Exception as e:
            logger.error(f"Error saving data: {e}")

async def send_telegram_message(message):
    """Helper function to send telegram message asynchronously"""
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=CHAT_ID, text=message)
        return True
    except Exception as e:
        logger.error(f"Failed to send telegram message: {e}")
        return False

async def send_telegram_document(file_path, caption):
    """Helper function to send telegram document asynchronously"""
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
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
    logger.info(f"Starting Excel send task - sending every {EXCEL_SEND_INTERVAL//3600} hours")
    
    # Wait for initial data (10 minutes to ensure we have some data)
    initial_wait = 600  # 10 minutes
    logger.info(f"Waiting {initial_wait//60} minutes for initial data...")
    time.sleep(initial_wait)
    
    while True:
        try:
            logger.info("Attempting to send Excel report...")
            
            # Check if bot token and chat_id are valid
            if not TELEGRAM_TOKEN or not CHAT_ID:
                logger.error("Missing Telegram credentials")
                time.sleep(EXCEL_SEND_INTERVAL)
                continue
            
            # Get data from last 3 hours (in Indonesia time)
            hours_back = EXCEL_SEND_INTERVAL // 3600  # Convert seconds to hours
            waktu_awal = (get_indonesia_time() - datetime.timedelta(hours=hours_back)).strftime("%Y-%m-%d %H:%M:%S")
            
            conn = get_db_connection()
            c = conn.cursor()
            # Remove timezone from query since database stores without timezone info
            c.execute("SELECT * FROM suhu WHERE datetime(waktu) >= datetime(?) ORDER BY waktu", (waktu_awal,))
            rows = c.fetchall()
            conn.close()
            
            if not rows:
                logger.warning(f"No data to send in Excel report (looking for data since {waktu_awal})")
                time.sleep(EXCEL_SEND_INTERVAL)
                continue

            # Create Excel file with better formatting
            wb = Workbook()
            ws = wb.active
            ws.title = "Data Suhu"
            
            # Header with styling
            headers = ["ID", "Waktu", "Suhu (°C)"]
            ws.append(headers)
            
            # Make header bold (if openpyxl supports it)
            try:
                from openpyxl.styles import Font
                for col in range(1, len(headers) + 1):
                    ws.cell(row=1, column=col).font = Font(bold=True)
            except ImportError:
                pass  # Skip styling if not available
            
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
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    ws.column_dimensions[column_letter].width = adjusted_width
            except:
                pass  # Skip if auto-adjust fails

            # Use temp directory and better filename
            temp_dir = "/tmp" if os.path.exists("/tmp") else "."
            filename = os.path.join(temp_dir, f"data_suhu_{get_indonesia_time().strftime('%Y%m%d_%H%M')}.xlsx")
            
            wb.save(filename)
            logger.info(f"Excel file created: {filename} with {len(rows)} records")
            
            # Send file using async function
            current_time = format_indonesia_time()
            time_range = f"{hours_back} jam terakhir"
            caption = f"📊 **Data Suhu - {len(rows)} records**\n🕐 {current_time}\n📅 Data dari {time_range}\n📍 Interval: {DATA_SAVE_INTERVAL//60} menit"
            
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
            
        # Wait for next cycle
        logger.info(f"Waiting {EXCEL_SEND_INTERVAL//3600} hours for next Excel report...")
        time.sleep(EXCEL_SEND_INTERVAL)  # 3 hours

def keepalive_task():
    logger.info("Starting keepalive task")
    while True:
        try:
            time.sleep(1800)  # 30 minutes
            app_url = os.getenv("FLY_APP_NAME", "")
            if app_url:
                import requests
                response = requests.get(f"https://{app_url}.fly.dev/keepalive", timeout=10)
                logger.info(f"Self-ping sent, status: {response.status_code}")
        except Exception as e:
            logger.error(f"Keepalive error: {e}")

# Better error handling for threads
def start_background_tasks():
    try:
        threading.Thread(target=save_data_task, daemon=True, name="SaveDataTask").start()
        logger.info("Save data task started")
        
        threading.Thread(target=send_excel_task, daemon=True, name="SendExcelTask").start()
        logger.info("Send Excel task started")
        
        threading.Thread(target=keepalive_task, daemon=True, name="KeepaliveTask").start()
        logger.info("Keepalive task started")
        
    except Exception as e:
        logger.error(f"Error starting background tasks: {e}")

start_background_tasks()

# === FLASK APP ===
app = Flask(__name__)

@app.route("/")
def index():
    return f"""
    🌡️ <b>Temperature Monitor Server</b><br><br>
    📊 Database: {DB_PATH}<br>
    ⏱️ Data Save Interval: {DATA_SAVE_INTERVAL//60} minutes<br>
    📤 Excel Send Interval: {EXCEL_SEND_INTERVAL//3600} hours<br>
    🌏 Timezone: Asia/Jakarta (WIB)<br>
    ✅ Status: Running<br><br>
    <a href="/status">Check Status</a> | 
    <a href="/test-telegram">Test Telegram</a>
    """

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
        
        # Get data from last 24 hours for statistics
        yesterday = (get_indonesia_time() - datetime.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("SELECT AVG(suhu), MIN(suhu), MAX(suhu) FROM suhu WHERE datetime(waktu) >= datetime(?)", (yesterday,))
        stats = c.fetchone()
        
        conn.close()
        
        with data_lock:
            current_mqtt_data = latest_suhu
        
        return {
            "status": "running",
            "database_path": DB_PATH,
            "total_records": total,
            "latest_records": latest_records,
            "latest_mqtt": current_mqtt_data,
            "statistics_24h": {
                "average": round(stats[0], 2) if stats[0] else None,
                "minimum": stats[1],
                "maximum": stats[2]
            },
            "configuration": {
                "data_save_interval_minutes": DATA_SAVE_INTERVAL // 60,
                "excel_send_interval_hours": EXCEL_SEND_INTERVAL // 3600,
                "mqtt_broker": MQTT_BROKER,
                "mqtt_topic": MQTT_TOPIC
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
        
    return {
        "status": "alive", 
        "timestamp": format_indonesia_time(),
        "latest_suhu": current_suhu,
        "next_data_save": f"{DATA_SAVE_INTERVAL//60} minutes",
        "next_excel_send": f"{EXCEL_SEND_INTERVAL//3600} hours"
    }

@app.route("/test-telegram")
def test_telegram():
    """Test Telegram bot connection"""
    try:
        current_time = format_indonesia_time()
        message = f"🧪 **Test Message**\n🕐 {current_time}\n⚙️ Data Save: {DATA_SAVE_INTERVAL//60} min\n📊 Excel Send: {EXCEL_SEND_INTERVAL//3600} hours"
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
        def send_now():
            logger.info("Force sending Excel report...")
            # Get recent data for testing
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM suhu ORDER BY id DESC LIMIT 50")
            rows = c.fetchall()
            conn.close()
            
            if not rows:
                return False
                
            wb = Workbook()
            ws = wb.active
            ws.title = "Data Suhu (Manual)"
            ws.append(["ID", "Waktu", "Suhu (°C)"])
            for row in rows:
                ws.append(row)
                
            temp_dir = "/tmp" if os.path.exists("/tmp") else "."
            filename = os.path.join(temp_dir, f"test_data_suhu_{get_indonesia_time().strftime('%Y%m%d_%H%M')}.xlsx")
            wb.save(filename)
            
            caption = f"🔧 **Manual Test Report**\n📊 {len(rows)} records\n🕐 {format_indonesia_time()}"
            success = run_async_in_thread(send_telegram_document(filename, caption))
            
            try:
                os.remove(filename)
            except:
                pass
                
            return success
            
        success = send_now()
        if success:
            return {"status": "success", "message": "Excel report sent manually"}
        else:
            return {"status": "error", "message": "Failed to send Excel report"}, 500
            
    except Exception as e:
        logger.error(f"Force Excel failed: {e}")
        return {"error": str(e)}, 500

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    logger.info(f"Webhook data received: {data}")
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Flask app on port {port}")
    app.run(host="0.0.0.0", port=port)