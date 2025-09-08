import threading
import logging
import os
from queue import Queue
from flask import Flask
from flask_login import LoginManager
from datetime import timedelta

from config.settings import TemperatureMonitorConfig
from database.manager import DatabaseManager
from services.mqtt_service import MQTTService
from services.telegram_service import TelegramService
from tasks.data_save_task import DataSaveTask
from tasks.excel_report_task import DailyExcelReportTask
from web.routes import WebRoutes

logger = logging.getLogger(__name__)


class TemperatureMonitor:
    """Main monitor class yang mengelola seluruh sistem monitoring"""

    def __init__(self):
        self.config = TemperatureMonitorConfig()

        # Data storage structure untuk semua sistem
        self.latest_temperatures = {
            "dryer": {"dryer1": None, "dryer2": None, "dryer3": None},
            "kedi": {"kedi1": None, "kedi2": None},
            "boiler": {"boiler1": None, "boiler2": None},
        }

        self.latest_humidity = {
            "kedi": {"kedi1": None, "kedi2": None, "kedi3": None, "kedi4": None}
        }

        self.data_lock = threading.Lock()

        # Alert status untuk semua sistem
        self.alert_status = {
            "dryer1": "NORMAL",
            "dryer2": "NORMAL",
            "dryer3": "NORMAL",
            "kedi1": "NORMAL",
            "kedi2": "NORMAL",
            "boiler1": "NORMAL",
            "boiler2": "NORMAL",
            "kedi1_humidity": "NORMAL",
            "kedi2_humidity": "NORMAL",
            "kedi3_humidity": "NORMAL",
            "kedi4_humidity": "NORMAL",
        }

        # Initialize components
        self.db_manager = DatabaseManager(self.config.DB_PATH)
        self.telegram_service = TelegramService(self.config, self.db_manager)
        self.mqtt_service = MQTTService(
            self.config, self._on_mqtt_message, self._on_mqtt_humidity_message
        )
        self.tasks = []
        self.notification_queue = Queue()

    def _on_mqtt_message(self, raw_temperature, humidity_value, topic):
        """Callback untuk setiap pesan MQTT. Memproses suhu dan mengirim notifikasi."""
        device_info = self._get_device_info_from_topic(topic)
        if not device_info:
            return

        system_type, device_id = device_info
        adjusted_temperature = self.config.apply_temperature_offset(raw_temperature)

        # Update memory
        with self.data_lock:
            self.latest_temperatures[system_type][device_id] = adjusted_temperature
            self.latest_humidity[system_type][device_id] = humidity_value

        logger.info(f"Data {{{device_id}}} diterima: {adjusted_temperature:.2f}°C")
        logger.info(f"Humidity {{{device_id}}} diterima: {humidity_value:.1f}%")

        # Check alerts and send notifications
        self._check_temperature_alerts(device_id, adjusted_temperature, humidity_value)

    def _on_mqtt_humidity_message(self, humidity_value, topic):
        """Callback untuk setiap pesan MQTT humidity. Memproses kelembaban dan mengirim notifikasi."""
        device_info = self._get_humidity_device_info_from_topic(topic)
        if not device_info:
            return

        system_type, device_id = device_info

        # Update memory untuk humidity
        with self.data_lock:
            self.latest_humidity[system_type][device_id] = humidity_value

        logger.info(f"Humidity {{{device_id}}} diterima: {humidity_value:.1f}%")

        # Check humidity alerts
        self._check_humidity_alerts(device_id, humidity_value)

    def _get_device_info_from_topic(self, topic):
        """Extract device info from MQTT topic"""
        topic_mapping = {
            # Dryer topics
            self.config.MQTT_TOPICS.get("dryer1"): ("dryer", "dryer1"),
            self.config.MQTT_TOPICS.get("dryer2"): ("dryer", "dryer2"),
            self.config.MQTT_TOPICS.get("dryer3"): ("dryer", "dryer3"),
            # Kedi topics
            self.config.MQTT_TOPICS.get("kedi1"): ("kedi", "kedi1"),
            self.config.MQTT_TOPICS.get("kedi2"): ("kedi", "kedi2"),
            # Boiler topics
            self.config.MQTT_TOPICS.get("boiler1"): ("boiler", "boiler1"),
            self.config.MQTT_TOPICS.get("boiler2"): ("boiler", "boiler2"),
            # Humidity
            self.config.MQTT_HUMIDITY_TOPICS.get("kedi1_humidity"): ("kedi", "kedi1"),
            self.config.MQTT_HUMIDITY_TOPICS.get("kedi2_humidity"): ("kedi", "kedi2"),
            self.config.MQTT_HUMIDITY_TOPICS.get("kedi3_humidity"): ("kedi", "kedi3"),
            self.config.MQTT_HUMIDITY_TOPICS.get("kedi4_humidity"): ("kedi", "kedi4"),
        }

        return topic_mapping.get(topic)

    # TAMBAHAN: Method untuk extract humidity device info dari topic
    def _get_humidity_device_info_from_topic(self, topic):
        """Extract humidity device info from MQTT topic"""
        topic_mapping = {
            self.config.MQTT_HUMIDITY_TOPICS.get("kedi1_humidity"): ("kedi", "kedi1"),
            self.config.MQTT_HUMIDITY_TOPICS.get("kedi2_humidity"): ("kedi", "kedi2"),
            self.config.MQTT_HUMIDITY_TOPICS.get("kedi3_humidity"): ("kedi", "kedi3"),
            self.config.MQTT_HUMIDITY_TOPICS.get("kedi4_humidity"): ("kedi", "kedi4"),
        }

        return topic_mapping.get(topic)

    def _check_temperature_alerts(self, device_id, temperature):
        """Check temperature alerts dan kirim notifikasi jika diperlukan"""
        waktu_kejadian = self.config.format_indonesia_time()
        telegram_message = None
        notification_payload = None

        # Check high temperature
        if temperature > self.config.MAX_TEMP_ALERT:
            if self.alert_status[device_id] != "HIGH":
                title = f"🔥 Suhu Tinggi ({device_id.upper()})"
                message = f"Suhu mencapai {temperature:.1f}°C, melebihi batas normal {self.config.MAX_TEMP_ALERT}°C."

                telegram_message = f"*{title}*\n\n🌡️ Suhu: *{temperature:.1f}°C*\n🕒 Waktu: {waktu_kejadian}"
                notification_payload = {"title": title, "message": message}
                self.alert_status[device_id] = "HIGH"

        # Check low temperature
        elif temperature < self.config.MIN_TEMP_ALERT:
            if self.alert_status[device_id] != "LOW":
                title = f"❄️ Suhu Rendah ({device_id.upper()})"
                message = f"Suhu turun menjadi {temperature:.1f}°C, di bawah batas normal {self.config.MIN_TEMP_ALERT}°C."

                telegram_message = f"*{title}*\n\n🌡️ Suhu: *{temperature:.1f}°C*\n🕒 Waktu: {waktu_kejadian}"
                notification_payload = {"title": title, "message": message}
                self.alert_status[device_id] = "LOW"

        # Temperature normal
        else:
            if self.alert_status[device_id] != "NORMAL":
                self.alert_status[device_id] = "NORMAL"

        # Send notifications if needed
        if telegram_message:
            current_hour = self.config.get_indonesia_time().hour
            if 6 <= current_hour < 17:
                self.telegram_service.send_message(telegram_message)

        if notification_payload:
            self.notification_queue.put(notification_payload)

    def _check_humidity_alerts(self, device_id, humidity):
        """Check humidity alerts dan kirim notifikasi jika diperlukan"""
        waktu_kejadian = self.config.format_indonesia_time()
        telegram_message = None
        notification_payload = None
        alert_key = f"{device_id}_humidity"

        # Check high humidity
        if humidity > self.config.MAX_HUMIDITY_ALERT:
            if self.alert_status[alert_key] != "HIGH":
                title = f"💧 Kelembaban Tinggi ({device_id.upper()})"
                message = f"Kelembaban mencapai {humidity:.1f}%, melebihi batas normal {self.config.MAX_HUMIDITY_ALERT}%."

                telegram_message = f"*{title}*\n\n💧 Kelembaban: *{humidity:.1f}%*\n🕒 Waktu: {waktu_kejadian}"
                notification_payload = {"title": title, "message": message}
                self.alert_status[alert_key] = "HIGH"

        # Check low humidity
        elif humidity < self.config.MIN_HUMIDITY_ALERT:
            if self.alert_status[alert_key] != "LOW":
                title = f"🏜️ Kelembaban Rendah ({device_id.upper()})"
                message = f"Kelembaban turun menjadi {humidity:.1f}%, di bawah batas normal {self.config.MIN_HUMIDITY_ALERT}%."

                telegram_message = f"*{title}*\n\n💧 Kelembaban: *{humidity:.1f}%*\n🕒 Waktu: {waktu_kejadian}"
                notification_payload = {"title": title, "message": message}
                self.alert_status[alert_key] = "LOW"

        # Humidity normal
        else:
            if self.alert_status[alert_key] != "NORMAL":
                self.alert_status[alert_key] = "NORMAL"

        # Send notifications if needed
        if telegram_message:
            current_hour = self.config.get_indonesia_time().hour
            if 6 <= current_hour < 17:
                self.telegram_service.send_message(telegram_message)

        if notification_payload:
            self.notification_queue.put(notification_payload)

    def get_latest_humidity(self):
        """Mendapatkan semua kelembaban terbaru dari memori"""
        with self.data_lock:
            return self.latest_humidity.copy()

    def _queue_humidity_save(self, device_id, humidity):
        """Queue humidity data untuk disave ke database"""
        # Implement ini di background task seperti DataSaveTask
        pass

    def get_latest_temperatures(self):
        """Mendapatkan semua suhu terbaru dari memori"""
        with self.data_lock:
            return {
                "temperatures": self.latest_temperatures.copy(),
                "humidity": self.latest_humidity.copy(),
            }

    def start_background_tasks(self):
        """Memulai semua background tasks"""
        # Import tasks yang diperlukan
        from tasks.keepalive_task import KeepaliveTask
        from tasks.monitor_data_task import MonitorDataTask

        self.tasks.append(DataSaveTask(self.config, self, self.db_manager))
        self.tasks.append(
            DailyExcelReportTask(self.config, self.db_manager, self.telegram_service)
        )
        self.tasks.append(KeepaliveTask(self.config))
        self.tasks.append(
            MonitorDataTask(self.config, self.db_manager, self.telegram_service)
        )

        for task in self.tasks:
            task.start()

        logger.info("All background tasks started")

    def stop_background_tasks(self):
        """Stop semua background tasks"""
        for task in self.tasks:
            task.stop()
        logger.info("All background tasks stopped")

    def create_flask_app(self):
        """Create dan configure Flask application"""
        app = Flask(__name__, template_folder="../templates", static_folder="../static")
        app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "default-secret-key-for-dev")

        # Session configuration
        app.config.update(
            PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SECURE=False,
            SESSION_COOKIE_SAMESITE="Lax",
        )

        # Setup Flask-Login
        login_manager = LoginManager()
        login_manager.init_app(app)
        login_manager.login_view = "login"
        login_manager.session_protection = "strong"

        @login_manager.user_loader
        def load_user(user_id):
            return self.db_manager.get_user_by_id(user_id)

        @login_manager.unauthorized_handler
        def unauthorized():
            from flask import request, redirect, url_for

            if request.endpoint != "login":
                return redirect(url_for("login", next=request.url))
            return redirect(url_for("login"))

        # Register routes
        web_routes = WebRoutes(self.config, self.db_manager, self)
        web_routes.register_routes(app)

        return app

    def run(self):
        """Run the complete monitoring system"""
        # Create initial admin user
        admin_user = os.getenv("ADMIN_USER")
        admin_pass = os.getenv("ADMIN_PASSWORD")
        if admin_user and admin_pass:
            self.db_manager.create_initial_user(admin_user, admin_pass)
        else:
            logger.warning("ADMIN_USER dan ADMIN_PASSWORD tidak diatur.")

        try:
            # Start services
            self.mqtt_service.connect()
            self.telegram_service.start_worker()
            self.start_background_tasks()

            # Start Flask app
            app = self.create_flask_app()
            flask_thread = threading.Thread(
                target=lambda: app.run(
                    host="0.0.0.0", port=int(os.environ.get("PORT", 8080))
                ),
                daemon=True,
            )
            flask_thread.start()

            # Start Telegram polling
            self.telegram_service.start_polling()

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.stop_background_tasks()
            self.telegram_service.stop_worker()
            self.mqtt_service.disconnect()
