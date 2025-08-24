from flask import Flask, request
import threading
import sqlite3
import datetime
import time
import paho.mqtt.client as mqtt
from openpyxl import Workbook
from telegram import Bot
from dotenv import load_dotenv
import os

load_dotenv()

# === KONFIGURASI ===
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = 1883
MQTT_TOPIC = os.getenv("MQTT_TOPIC")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# === DATABASE === 
# PERBAIKAN: Gunakan path yang lebih persistent jika ada volume
DB_PATH = "/data/data_suhu.db" if os.path.exists("/data") else "data_suhu.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS suhu (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        waktu TEXT,
        suhu REAL
    )
""")
conn.commit()
print(f"[DB] Database initialized at: {DB_PATH}")

# === VARIABEL PENAMPUNG ===
latest_suhu = None

# === MQTT CALLBACK ===
def on_message(client, userdata, msg):
    global latest_suhu
    try:
        suhu = float(msg.payload.decode())
        latest_suhu = suhu
        print(f"[MQTT] Data diterima: {suhu + 30}")
    except Exception as e:
        print("Error parsing data:", e)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Connected successfully")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"[MQTT] Connection failed with code {rc}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.subscribe(MQTT_TOPIC)
    client.loop_start()
    print("[MQTT] Client started")
except Exception as e:
    print(f"[MQTT] Connection error: {e}")

# === BACKGROUND TASKS ===
def save_data_task():
    global latest_suhu
    while True:
        try:
            time.sleep(60)  # 1 menit
            if latest_suhu is not None:
                waktu = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                c.execute("INSERT INTO suhu (waktu, suhu) VALUES (?, ?)", (waktu, latest_suhu))
                conn.commit()
                print(f"[DB] Data disimpan: {waktu} | {latest_suhu:.2f}")
            else:
                print("[DB] Belum ada data suhu diterima dari MQTT")
        except Exception as e:
            print(f"[DB] Error saving data: {e}")

def send_excel_task():
    bot = Bot(token=TELEGRAM_TOKEN)
    while True:
        try:
            time.sleep(3600)  # 1 jam
            waktu_awal = (datetime.datetime.now() - datetime.timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
            c.execute("SELECT * FROM suhu WHERE waktu >= ?", (waktu_awal,))
            rows = c.fetchall()
            if not rows:
                print("[BOT] Tidak ada data untuk dikirim.")
                continue

            wb = Workbook()
            ws = wb.active
            ws.title = "Data Suhu"
            ws.append(["ID", "Waktu", "Suhu (°C)"])
            for row in rows:
                ws.append(row)

            filename = f"data_suhu_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            wb.save(filename)
            
            # PERBAIKAN: Pastikan file ditutup dengan benar
            with open(filename, "rb") as file:
                bot.send_document(chat_id=CHAT_ID, document=file, caption=f"Data Suhu - {len(rows)} records")
            
            # PERBAIKAN: Hapus file temporary
            try:
                os.remove(filename)
                print(f"[BOT] File dikirim dan dihapus: {filename}")
            except OSError:
                print(f"[BOT] Warning: Could not delete {filename}")
                
        except Exception as e:
            print(f"[BOT] Error sending Excel: {e}")

# PERBAIKAN: Tambah keep-alive task
def keepalive_task():
    while True:
        try:
            time.sleep(1800)  # 30 menit
            app_url = os.getenv("FLY_APP_NAME", "")
            if app_url:
                import requests
                requests.get(f"https://{app_url}.fly.dev/", timeout=10)
                print("[KEEPALIVE] Self-ping sent")
        except Exception as e:
            print(f"[KEEPALIVE] Error: {e}")

# === START THREADS ===
threading.Thread(target=save_data_task, daemon=True).start()
threading.Thread(target=send_excel_task, daemon=True).start()
threading.Thread(target=keepalive_task, daemon=True).start()

# === FLASK APP ===
app = Flask(__name__)

@app.route("/")
def index():
    return f"Server is running! Database: {DB_PATH}"

@app.route("/status")
def status():
    """Status endpoint untuk monitoring"""
    try:
        c.execute("SELECT COUNT(*) FROM suhu")
        total = c.fetchone()[0]
        
        c.execute("SELECT * FROM suhu ORDER BY id DESC LIMIT 1")
        latest = c.fetchone()
        
        return {
            "status": "running",
            "database_path": DB_PATH,
            "total_records": total,
            "latest_data": latest,
            "latest_mqtt": latest_suhu
        }
    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/keepalive")
def keepalive():
    """Endpoint untuk keep container alive"""
    return {
        "status": "alive", 
        "timestamp": datetime.datetime.now().isoformat(),
        "latest_suhu": latest_suhu
    }

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print(f"[WEBHOOK] Data diterima: {data}")
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)