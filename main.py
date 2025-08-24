from flask import Flask, request
import threading
import sqlite3
import datetime
import time
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

# Validasi konfigurasi
if not all([MQTT_BROKER, MQTT_TOPIC, TELEGRAM_TOKEN, CHAT_ID]):
    logger.error("Missing required environment variables")
    exit(1)

logger.info(f"Config loaded - Broker: {MQTT_BROKER}, Topic: {MQTT_TOPIC}, Chat ID: {CHAT_ID}")

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
    logger.info("Starting data save task")
    
    while True:
        try:
            time.sleep(60)  # 1 menit
            
            with data_lock:
                current_suhu = latest_suhu
            
            if current_suhu is not None:
                conn = get_db_connection()
                c = conn.cursor()
                waktu = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                c.execute("INSERT INTO suhu (waktu, suhu) VALUES (?, ?)", (waktu, current_suhu))
                conn.commit()
                conn.close()
                logger.info(f"Data saved: {waktu} | {current_suhu:.2f}°C")
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
    logger.info("Starting Excel send task")
    
    # PERBAIKAN: Wait for initial data
    time.sleep(120)  # Wait 2 minutes before first run
    
    while True:
        try:
            logger.info("Attempting to send Excel report...")
            
            # PERBAIKAN: Check if bot token and chat_id are valid
            if not TELEGRAM_TOKEN or not CHAT_ID:
                logger.error("Missing Telegram credentials")
                time.sleep(3600)
                continue
            
            # Get data from last hour
            waktu_awal = (datetime.datetime.now() - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM suhu WHERE waktu >= ? ORDER BY waktu", (waktu_awal,))
            rows = c.fetchall()
            conn.close()
            
            if not rows:
                logger.warning("No data to send in Excel report")
                time.sleep(3600)
                continue

            # Create Excel file
            wb = Workbook()
            ws = wb.active
            ws.title = "Data Suhu"
            ws.append(["ID", "Waktu", "Suhu (°C)"])
            
            for row in rows:
                ws.append(row)

            # PERBAIKAN: Use temp directory and better filename
            temp_dir = "/tmp" if os.path.exists("/tmp") else "."
            filename = os.path.join(temp_dir, f"data_suhu_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")
            
            wb.save(filename)
            logger.info(f"Excel file created: {filename} with {len(rows)} records")
            
            # Send file using async function
            caption = f"📊 Data Suhu - {len(rows)} records\n🕐 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
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
            
        # PERBAIKAN: Always wait full hour regardless of success/failure
        logger.info("Waiting 1 hour for next Excel report...")
        time.sleep(3600)  # 1 hour

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

# PERBAIKAN: Better error handling for threads
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
    return f"🌡️ Temperature Monitor Server<br>Database: {DB_PATH}<br>Status: Running"

@app.route("/status")
def status():
    """Status endpoint untuk monitoring"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM suhu")
        total = c.fetchone()[0]
        
        c.execute("SELECT * FROM suhu ORDER BY id DESC LIMIT 1")
        latest = c.fetchone()
        conn.close()
        
        with data_lock:
            current_mqtt_data = latest_suhu
        
        return {
            "status": "running",
            "database_path": DB_PATH,
            "total_records": total,
            "latest_data": latest,
            "latest_mqtt": current_mqtt_data,
            "timestamp": datetime.datetime.now().isoformat()
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
        "timestamp": datetime.datetime.now().isoformat(),
        "latest_suhu": current_suhu
    }

@app.route("/test-telegram")
def test_telegram():
    """Test Telegram bot connection"""
    try:
        message = "🧪 Test message from temperature monitor"
        success = run_async_in_thread(send_telegram_message(message))
        
        if success:
            return {"status": "success", "message": "Test message sent"}
        else:
            return {"status": "error", "message": "Failed to send message"}, 500
            
    except Exception as e:
        logger.error(f"Telegram test failed: {e}")
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