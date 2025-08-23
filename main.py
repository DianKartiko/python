import asyncio
import sqlite3
import datetime
import paho.mqtt.client as mqtt
from openpyxl import Workbook
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler
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
conn = sqlite3.connect("data_suhu.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS suhu (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        waktu TEXT,
        suhu REAL
    )
""")
conn.commit()

# === VARIABEL PENAMPUNG ===
latest_suhu = None  # hanya simpan data terbaru

# === MQTT CALLBACK ===
def on_message(client, userdata, msg):
    global latest_suhu
    try:
        suhu = float(msg.payload.decode())
        latest_suhu = suhu
        print(f"[MQTT] Data diterima: {suhu + 30}")
    except Exception as e:
        print("Error parsing data:", e)

client = mqtt.Client()
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.subscribe(MQTT_TOPIC)
client.loop_start()

# === SIMPAN DATA SETIAP 10 MENIT ===
async def save_data_task():
    global latest_suhu
    while True:
        await asyncio.sleep(600)  # 10 menit
        if latest_suhu is not None:
            waktu = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("INSERT INTO suhu (waktu, suhu) VALUES (?, ?)", (waktu, latest_suhu))
            conn.commit()
            print(f"[DB] Data disimpan: {waktu} | {latest_suhu:.2f}")
        else:
            print("[DB] Belum ada data suhu diterima dari MQTT")

# === KIRIM FILE EXCEL SETIAP 3 MENIT ===
async def send_excel_task():
    bot = Bot(token=TELEGRAM_TOKEN)
    while True:
        await asyncio.sleep(10800)  # 3 menit

        # Ambil data 15 menit terakhir
        waktu_awal = (datetime.datetime.now() - datetime.timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("SELECT * FROM suhu WHERE waktu >= ?", (waktu_awal,))
        rows = c.fetchall()

        if not rows:
            print("[BOT] Tidak ada data untuk dikirim.")
            continue

        # Buat Excel
        wb = Workbook()
        ws = wb.active
        ws.title = "Data Suhu"
        ws.append(["ID", "Waktu", "Suhu (°C)"])
        for row in rows:
            ws.append(row)

        filename = f"data_suhu_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        wb.save(filename)

        # Kirim ke Telegram
        await bot.send_document(chat_id=CHAT_ID, document=open(filename, "rb"))
        print(f"[BOT] File dikirim: {filename}")

# === MAIN ===
async def main():
    await asyncio.gather(
        save_data_task(),
        send_excel_task(),
    )

if __name__ == "__main__":
    asyncio.run(main())
