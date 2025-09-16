#!/usr/bin/env python3
# Flask Requirements
from flask import Flask, request, render_template, jsonify, Response, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse, urljoin
# Threading and Request
import threading
import requests
# Database System
import sqlite3
# Timezone Requirements
import datetime
import time
from datetime import timedelta
from zoneinfo import ZoneInfo
# MQTT Service 
import paho.mqtt.client as mqtt
# Operating System Requirements
from dotenv import load_dotenv
import os
# Logging System
import logging
# Excel Requirements
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
# Input dan Output
from queue import Queue, Empty
from io import BytesIO
from functools import wraps
import json
import sys

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(base_dir, "monitoring_website", ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    load_dotenv()  # Load from current directory

sys.path.insert(0, os.path.dirname(__file__))

# Configuration for subdirectory deployment
SUBDIRECTORY = os.getenv('SUBDIRECTORY', '/monitoring_website')
logger.info(f"Application configured for subdirectory: {SUBDIRECTORY}")

# --- LOGIN SYSTEM: User Class ---
class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

def is_safe_url(target):
    """Validasi URL untuk mencegah open redirect vulnerability"""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

# SESSION TIMEOUT DECORATOR
def check_session_timeout(f):
    """Decorator untuk mengecek apakah session sudah timeout"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated:
            if 'login_timestamp' in session:
                login_time = session['login_timestamp']
                current_time = time.time()
                
                session_duration = current_time - login_time
                max_session_duration = 24 * 60 * 60
                
                if session_duration > max_session_duration:
                    logout_user()
                    session.clear()
                    flash('Your session has expired after 24 hours. Please log in again.', 'warning')
                    return redirect(url_for('login'))
                else:
                    session['last_activity'] = current_time
            else:
                logout_user()
                session.clear()
                flash('Invalid session. Please log in again.', 'warning')
                return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function

def get_session_info():
    """Helper untuk mendapatkan informasi session"""
    if not current_user.is_authenticated or 'login_timestamp' not in session:
        return None
    
    login_time = session['login_timestamp']
    current_time = time.time()
    session_age = current_time - login_time
    remaining_time = (24 * 60 * 60) - session_age
    
    return {
        'login_time': datetime.datetime.fromtimestamp(login_time).strftime('%Y-%m-%d %H:%M:%S'),
        'session_age_hours': session_age / 3600,
        'remaining_hours': max(0, remaining_time / 3600),
        'remaining_minutes': max(0, (remaining_time % 3600) / 60),
        'is_expiring_soon': remaining_time < (2 * 3600),
        'expires_at': datetime.datetime.fromtimestamp(login_time + (24 * 60 * 60)).strftime('%Y-%m-%d %H:%M:%S')
    }

# Basic Configuration
class TemperatureMonitorConfig:
    """Class untuk mengelola konfigurasi aplikasi"""
    
    def __init__(self):
        self.MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
        self.MQTT_PORT = 1883
        self.MQTT_TOPICS = {
            "dryer1": os.getenv("MQTT_TOPIC_1", "esp32/suhu1"),
            "dryer2": os.getenv("MQTT_TOPIC_2", "esp32/suhu"),
            "dryer3": os.getenv("MQTT_TOPIC_3", "esp32/suhu3"),
            "humidity1": os.getenv("MQTT_TOPIC_KEDI_1_HUMIDITY", "kedi/kedi1/humidity"),
        }
        self.DATA_SAVE_INTERVAL = 600
        self.TEMPERATURE_OFFSET = 12.6
        self.MIN_HUMIDITY_ALERT = float(30)
        self.MAX_HUMIDITY_ALERT = float(90)
        self.INDONESIA_TZ = ZoneInfo("Asia/Jakarta")
        self.MIN_TEMP_ALERT = float(120)
        self.MAX_TEMP_ALERT = float(155)
        self.DB_PATH = "/data/data_suhu_multi.db" if os.path.exists("/data") else "data_suhu_multi.db"
        
        # Disable background tasks untuk shared hosting
        self.ENABLE_BACKGROUND_TASKS = os.getenv('ENABLE_BACKGROUND_TASKS', 'false').lower() == 'true'
        
        self.validate()
        
    def validate(self):
        """Validasi konfigurasi yang diperlukan"""
        if not self.MQTT_BROKER:
            logger.error("Missing MQTT_BROKER environment variable")
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

class DatabaseManager:
    """Class untuk mengelola operasi database"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.connection_lock = threading.Lock()
        self.initialize_database()
        
    def initialize_database(self):
        """Initialize database dengan table yang diperlukan"""
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS suhu (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    waktu TEXT,
                    dryer_id TEXT, 
                    suhu REAL
                )
            """)
            
            c.execute("""
                CREATE TABLE IF NOT EXISTS humidity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    waktu TEXT,
                    sensor_id TEXT,
                    humidity REAL
                )
            """)
            
            c.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    username TEXT UNIQUE NOT NULL, 
                    password TEXT NOT NULL
                )
            """)
            
            # Create indexes for better performance
            c.execute("CREATE INDEX IF NOT EXISTS idx_suhu_waktu ON suhu(waktu)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_humidity_waktu ON humidity(waktu)")
            
        logger.info(f"Database initialized at: {self.db_path}")
    
    def get_connection(self):
        """Thread-safe database connection with optimizations"""
        conn = sqlite3.connect(
            self.db_path, 
            check_same_thread=False, 
            timeout=10.0,
            isolation_level=None  # Autocommit mode
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        return conn
    
    def get_user_by_username(self, username):
        try:
            with self.connection_lock:
                with self.get_connection() as conn:
                    c = conn.cursor()
                    c.execute("SELECT * FROM users WHERE username = ?", (username,))
                    user_data = c.fetchone()
                    if user_data:
                        return User(id=user_data[0], username=user_data[1], password=user_data[2])
            return None
        except Exception as e:
            logger.error(f"Error getting user by username: {e}")
            return None

    def get_user_by_id(self, user_id):
        try:
            with self.connection_lock:
                with self.get_connection() as conn:
                    c = conn.cursor()
                    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                    user_data = c.fetchone()
                    if user_data:
                        return User(id=user_data[0], username=user_data[1], password=user_data[2])
            return None
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            return None
    
    def create_initial_user(self, username, password):
        """Create initial user if not exists"""
        if not self.get_user_by_username(username):
            logger.info(f"Creating initial user: {username}")
            try:
                with self.connection_lock:
                    with self.get_connection() as conn:
                        c = conn.cursor()
                        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
                        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
                        logger.info(f"User '{username}' created successfully")
            except Exception as e:
                logger.error(f"Failed to create initial user: {e}")
    
    def insert_temperature(self, waktu, dryer_id, suhu):
        """Insert temperature data"""
        try:
            with self.connection_lock:
                with self.get_connection() as conn:
                    c = conn.cursor()
                    c.execute("INSERT INTO suhu (waktu, dryer_id, suhu) VALUES (?, ?, ?)", (waktu, dryer_id, suhu))
            return True
        except Exception as e:
            logger.error(f"Error inserting temperature: {e}")
            return False
    
    def insert_humidity(self, waktu, sensor_id, humidity):
        """Insert humidity data"""
        try:
            with self.connection_lock:
                with self.get_connection() as conn:
                    c = conn.cursor()
                    c.execute("INSERT INTO humidity (waktu, sensor_id, humidity) VALUES (?, ?, ?)", (waktu, sensor_id, humidity))
            return True
        except Exception as e:
            logger.error(f"Error inserting humidity: {e}")
            return False
    
    def get_humidity_by_date(self, date_str, sensor_id="humidity1", latest_only=False):
        """Get humidity data for specific date"""
        try:
            start_time = f"{date_str} 00:00:00"
            end_time = f"{date_str} 23:59:59"
            
            sql = """
            SELECT waktu, humidity
            FROM humidity
            WHERE waktu BETWEEN ? AND ? AND sensor_id = ?
            """
            
            if latest_only:
                sql += " ORDER BY waktu DESC LIMIT 1"
            else:
                sql += " ORDER BY waktu ASC"

            with self.connection_lock:
                with self.get_connection() as conn:
                    c = conn.cursor()
                    c.execute(sql, (start_time, end_time, sensor_id))
                    return c.fetchall()
        except Exception as e:
            logger.error(f"Error getting humidity data for date {date_str}: {e}")
            return []
    
    def get_data_by_date_pivoted(self, date_str, latest_only=False):
        """Get pivoted temperature data for specific date"""
        try:
            start_time = f"{date_str} 00:00:00"
            end_time = f"{date_str} 23:59:59"
            
            sql = """
            SELECT
                strftime('%Y-%m-%d %H:%M:%S', waktu) as timestamp,
                MAX(CASE WHEN dryer_id = 'dryer1' THEN suhu END) as dryer1_suhu,
                MAX(CASE WHEN dryer_id = 'dryer2' THEN suhu END) as dryer2_suhu,
                MAX(CASE WHEN dryer_id = 'dryer3' THEN suhu END) as dryer3_suhu
            FROM suhu
            WHERE waktu BETWEEN ? AND ?
            GROUP BY timestamp
            """
            
            if latest_only:
                sql += " ORDER BY timestamp DESC LIMIT 1"
            else:
                sql += " ORDER BY timestamp ASC"

            with self.connection_lock:
                with self.get_connection() as conn:
                    c = conn.cursor()
                    c.execute(sql, (start_time, end_time))
                    return c.fetchall()
        except Exception as e:
            logger.error(f"Error getting pivoted data for date {date_str}: {e}")
            return []

class MQTTService:
    """Optimized MQTT Service"""
    
    def __init__(self, config, data_callback):
        self.config = config
        self.data_callback = data_callback
        self.client = mqtt.Client()
        self.is_connected = False
        self.connection_lock = threading.Lock()
        self.setup_callbacks()
        
    def setup_callbacks(self):
        """Setup MQTT callbacks"""
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        # MQTT optimizations
        self.client.keepalive = 60
        self.client.max_inflight_messages_set(20)
        self.client.max_queued_messages_set(0)
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connect callback"""
        with self.connection_lock:
            if rc == 0:
                self.is_connected = True
                logger.info(f"MQTT Connected at {self.config.format_indonesia_time()}")
                for topic in self.config.MQTT_TOPICS.values():
                    if topic: 
                        self.client.subscribe(topic)
                        logger.info(f"Subscribed to: {topic}")
            else:
                logger.error(f"MQTT Connection failed with code {rc}")
    
    def _on_message(self, client, userdata, msg):
        """MQTT message callback - non-blocking"""
        try:
            raw_value = float(msg.payload.decode())
            if self.data_callback:
                threading.Thread(
                    target=self.data_callback, 
                    args=(raw_value, msg.topic), 
                    daemon=True
                ).start()
        except Exception as e:
            logger.error(f"Error parsing MQTT data from {msg.topic}: {e}")
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnect callback"""
        with self.connection_lock:
            self.is_connected = False
            logger.warning(f"MQTT Disconnected with code {rc}")
    
    def connect(self):
        """Connect to MQTT broker with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.client.connect(self.config.MQTT_BROKER, self.config.MQTT_PORT, 60)
                self.client.loop_start()
                logger.info("MQTT Client started")
                return True
            except Exception as e:
                logger.error(f"MQTT Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                continue
        return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        with self.connection_lock:
            self.client.loop_stop()
            self.client.disconnect()

class DataSaveTask:
    """Background task for data saving"""
    def __init__(self, config, data_provider, db_manager):
        self.config = config
        self.data_provider = data_provider
        self.db_manager = db_manager
        self.is_running = False
        self.thread = None
        self.stop_event = threading.Event()
    
    def start(self):
        if not self.config.ENABLE_BACKGROUND_TASKS:
            logger.info("Background tasks disabled for shared hosting")
            return
            
        self.is_running = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("DataSaveTask started")
    
    def stop(self):
        self.is_running = False
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
    
    def _run(self):
        while self.is_running and not self.stop_event.is_set():
            try:
                if self.stop_event.wait(self.config.DATA_SAVE_INTERVAL):
                    break  # Stop event was set
                if self.is_running:
                    self._save_data()
            except Exception as e:
                logger.error(f"Error in DataSaveTask: {e}")
    
    def _save_data(self):
        """Save latest data to database"""
        latest_temps = self.data_provider.get_latest_temperatures()
        latest_humidity = self.data_provider.get_latest_humidity()
        waktu = self.config.format_indonesia_time_simple()
        
        logger.info(f"Saving data at {waktu}")
        
        for dryer_id, temp in latest_temps.items():
            if temp is not None:
                self.db_manager.insert_temperature(waktu, dryer_id, temp)
        
        for sensor_id, humidity in latest_humidity.items():
            if humidity is not None:
                self.db_manager.insert_humidity(waktu, sensor_id, humidity)

class TemperatureMonitor:
    """Main application class optimized for subdirectory deployment"""
    
    def __init__(self):
        self.config = TemperatureMonitorConfig()
        self.latest_temperatures = {"dryer1": None, "dryer2": None, "dryer3": None}
        self.latest_humidity = {"humidity1": None}
        self.data_lock = threading.RLock()
        self.alert_status = {"dryer1": "NORMAL", "dryer2": "NORMAL", "dryer3": "NORMAL"}
        self.humidity_alert_status = {"humidity1": "NORMAL"}
        self.db_manager = DatabaseManager(self.config.DB_PATH)
        self.mqtt_service = MQTTService(self.config, self._on_mqtt_message)
        self.data_save_task = None
    
    def _on_mqtt_message(self, raw_value, topic):
        """Handle MQTT messages"""
        dryer_id = None
        humidity_sensor_id = None
        
        for id, t in self.config.MQTT_TOPICS.items():
            if t == topic:
                if "humidity" in id:
                    humidity_sensor_id = id
                else:
                    dryer_id = id
                break

        if dryer_id:
            adjusted_temperature = self.config.apply_temperature_offset(raw_value)
            with self.data_lock:
                self.latest_temperatures[dryer_id] = adjusted_temperature
            logger.info(f"Temperature {dryer_id}: {adjusted_temperature:.2f}°C")
            self._check_temperature_alerts(dryer_id, adjusted_temperature)
        
        elif humidity_sensor_id:
            with self.data_lock:
                self.latest_humidity[humidity_sensor_id] = raw_value
            logger.info(f"Humidity {humidity_sensor_id}: {raw_value:.2f}%")
            self._check_humidity_alerts(humidity_sensor_id, raw_value)
    
    def _check_temperature_alerts(self, dryer_id, temperature):
        """Check temperature alerts"""
        if temperature > self.config.MAX_TEMP_ALERT:
            if self.alert_status[dryer_id] != "HIGH":
                logger.warning(f"HIGH TEMP ALERT - {dryer_id}: {temperature:.1f}°C")
                self.alert_status[dryer_id] = 'HIGH'
        elif temperature < self.config.MIN_TEMP_ALERT:
            if self.alert_status[dryer_id] != "LOW":
                logger.warning(f"LOW TEMP ALERT - {dryer_id}: {temperature:.1f}°C")
                self.alert_status[dryer_id] = 'LOW'
        else:
            if self.alert_status[dryer_id] != 'NORMAL':
                logger.info(f"Temperature normalized - {dryer_id}: {temperature:.1f}°C")
                self.alert_status[dryer_id] = 'NORMAL'
    
    def _check_humidity_alerts(self, sensor_id, humidity):
        """Check humidity alerts"""
        if humidity > self.config.MAX_HUMIDITY_ALERT:
            if self.humidity_alert_status[sensor_id] != "HIGH":
                logger.warning(f"HIGH HUMIDITY ALERT - {sensor_id}: {humidity:.1f}%")
                self.humidity_alert_status[sensor_id] = 'HIGH'
        elif humidity < self.config.MIN_HUMIDITY_ALERT:
            if self.humidity_alert_status[sensor_id] != "LOW":
                logger.warning(f"LOW HUMIDITY ALERT - {sensor_id}: {humidity:.1f}%")
                self.humidity_alert_status[sensor_id] = 'LOW'
        else:
            if self.humidity_alert_status[sensor_id] != 'NORMAL':
                logger.info(f"Humidity normalized - {sensor_id}: {humidity:.1f}%")
                self.humidity_alert_status[sensor_id] = 'NORMAL'

    def get_latest_temperatures(self):
        """Get latest temperatures"""
        with self.data_lock:
            return self.latest_temperatures.copy()
    
    def get_latest_humidity(self):
        """Get latest humidity"""
        with self.data_lock:
            return self.latest_humidity.copy()
    
    def start_background_tasks(self):
        """Start background tasks if enabled"""
        if self.config.ENABLE_BACKGROUND_TASKS:
            self.data_save_task = DataSaveTask(self.config, self, self.db_manager)
            self.data_save_task.start()
            logger.info("Background tasks started")
        else:
            logger.info("Background tasks disabled for shared hosting")
    
    def stop_background_tasks(self):
        """Stop background tasks"""
        if self.data_save_task:
            self.data_save_task.stop()
    
    def create_flask_app(self):
        """Create Flask app with subdirectory support"""
        app = Flask(__name__, 
                   template_folder='templates', 
                   static_folder='static',
                   static_url_path=f'{SUBDIRECTORY}/static')  # Important for subdirectory
        
        app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key-for-dev')
        app.config.update(
            PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SECURE=False,
            SESSION_COOKIE_SAMESITE='Lax'
        )

        # Configure Flask-Login for subdirectory
        login_manager = LoginManager()
        login_manager.init_app(app)
        login_manager.login_view = 'login'
        login_manager.session_protection = "strong"

        @login_manager.user_loader
        def load_user(user_id):
            return self.db_manager.get_user_by_id(user_id)
        
        @login_manager.unauthorized_handler
        def unauthorized():
            if request.endpoint != 'login':
                return redirect(url_for('login', next=request.url))
            return redirect(url_for('login'))

        # Routes
        @app.route("/")
        @login_required
        @check_session_timeout  
        def index():
            with self.data_lock:
                context = {
                    "current_suhu_1": f"{self.latest_temperatures['dryer1']:.1f} °C" if self.latest_temperatures['dryer1'] else "N/A",
                    "current_suhu_2": f"{self.latest_temperatures['dryer2']:.1f} °C" if self.latest_temperatures['dryer2'] else "N/A",
                    "current_suhu_3": f"{self.latest_temperatures['dryer3']:.1f} °C" if self.latest_temperatures['dryer3'] else "N/A",
                    "current_humidity_1": f"{self.latest_humidity['humidity1']:.1f} %" if self.latest_humidity['humidity1'] else "N/A",
                    "current_time": self.config.format_indonesia_time(),
                    "timezone": str(self.config.INDONESIA_TZ),
                    "subdirectory": SUBDIRECTORY  # Pass to template
                }
            return render_template("index.html", **context, active_page='dryer')

        @app.route("/dwidaya")
        @login_required
        @check_session_timeout  
        def dwidaya():
            with self.data_lock:
                context = {
                    "current_suhu_1": f"{self.latest_temperatures['dryer1']:.1f} °C" if self.latest_temperatures['dryer1'] else "N/A",
                    "current_suhu_2": f"{self.latest_temperatures['dryer2']:.1f} °C" if self.latest_temperatures['dryer2'] else "N/A",
                    "current_suhu_3": f"{self.latest_temperatures['dryer3']:.1f} °C" if self.latest_temperatures['dryer3'] else "N/A",
                    "current_humidity_1": f"{self.latest_humidity['humidity1']:.1f} %" if self.latest_humidity['humidity1'] else "N/A",
                    "current_time": self.config.format_indonesia_time(),
                    "timezone": str(self.config.INDONESIA_TZ),
                    "subdirectory": SUBDIRECTORY
                }
            return render_template("dwidaya.html", **context)

        @app.route('/login', methods=['GET', 'POST'])
        def login():
            if current_user.is_authenticated:
                return redirect(url_for('index'))
            
            if request.method == 'POST':
                username = request.form['username']
                password = request.form['password']
                user = self.db_manager.get_user_by_username(username)
                
                if user and check_password_hash(user.password, password):
                    login_user(user, remember=False)
                    session.permanent = True
                    session['login_timestamp'] = time.time()
                    session['last_activity'] = time.time()
                    session['username'] = user.username
                    
                    next_page = request.args.get('next')
                    if not next_page or not is_safe_url(next_page):
                        next_page = url_for('index')
                    
                    flash(f'Welcome back, {user.username}!', 'success')
                    logger.info(f"User {user.username} logged in from {request.remote_addr}")
                    
                    return redirect(next_page)
                else:
                    flash('Username atau password salah', 'danger')
                    logger.warning(f"Failed login attempt for {username} from {request.remote_addr}")
            
            return render_template('login.html', subdirectory=SUBDIRECTORY)
    
        @app.route('/logout')
        @login_required
        def logout():
            logout_user()
            session.clear()
            flash('You have been logged out successfully.', 'info')
            return redirect(url_for('login'))

        # API endpoint untuk polling data (mengganti SSE)
        @app.route("/current-data")
        @login_required
        def get_current_data():
            """API endpoint for current data polling"""
            try:
                with self.data_lock:
                    data_payload = {
                        "dryer1": f"{self.latest_temperatures['dryer1']:.1f}" if self.latest_temperatures['dryer1'] is not None else "N/A",
                        "dryer2": f"{self.latest_temperatures['dryer2']:.1f}" if self.latest_temperatures['dryer2'] is not None else "N/A",
                        "dryer3": f"{self.latest_temperatures['dryer3']:.1f}" if self.latest_temperatures['dryer3'] is not None else "N/A",
                        "humidity1": f"{self.latest_humidity['humidity1']:.1f}" if self.latest_humidity['humidity1'] is not None else "N/A",
                        "timestamp": self.config.format_indonesia_time(),
                        "mqtt_connected": self.mqtt_service.is_connected
                    }
                return jsonify(data_payload)
            except Exception as e:
                logger.error(f"Error getting current data: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route("/chart-data")
        @login_required
        def get_chart_data():
            """Chart data API for temperature"""
            try:
                selected_date = request.args.get('date', self.config.get_indonesia_time().strftime('%Y-%m-%d'))
                rows = self.db_manager.get_data_by_date_pivoted(selected_date)

                if not rows:
                    return jsonify({"labels": [], "datasets": []})

                labels = []
                dryer1_data = []
                dryer2_data = []
                dryer3_data = []

                for row in rows:
                    waktu = row[0].split(' ')[1][:5]
                    labels.append(waktu)
                    dryer1_data.append(row[1])
                    dryer2_data.append(row[2])
                    dryer3_data.append(row[3])

                chart_data = {
                    "labels": labels,
                    "datasets": [
                        {
                            "label": "Dryer 1",
                            "data": dryer1_data,
                            "borderColor": "rgba(255, 99, 132, 1)",
                            "backgroundColor": "rgba(255, 99, 132, 0.2)",
                            "fill": True,
                            "tension": 0.4
                        },
                        {
                            "label": "Dryer 2",
                            "data": dryer2_data,
                            "borderColor": "rgba(54, 162, 235, 1)",
                            "backgroundColor": "rgba(54, 162, 235, 0.2)",
                            "fill": True,
                            "tension": 0.4
                        },
                        {
                            "label": "Dryer 3",
                            "data": dryer3_data,
                            "borderColor": "rgba(75, 192, 192, 1)",
                            "backgroundColor": "rgba(75, 192, 192, 0.2)",
                            "fill": True,
                            "tension": 0.4
                        }
                    ]
                }
                return jsonify(chart_data)

            except Exception as e:
                logger.error(f"Error getting chart data: {e}")
                return jsonify({"error": str(e)}), 500
        
        @app.route("/humidity-chart-data")
        @login_required
        def get_humidity_chart_data():
            """Chart data API for humidity"""
            try:
                selected_date = request.args.get('date', self.config.get_indonesia_time().strftime('%Y-%m-%d'))
                rows = self.db_manager.get_humidity_by_date(selected_date, "humidity1")

                if not rows:
                    return jsonify({"labels": [], "datasets": []})

                labels = []
                humidity_data = []

                for row in rows:
                    waktu = row[0].split(' ')[1][:5]
                    labels.append(waktu)
                    humidity_data.append(row[1])

                chart_data = {
                    "labels": labels,
                    "datasets": [
                        {
                            "label": "Humidity 1",
                            "data": humidity_data,
                            "borderColor": "rgba(153, 102, 255, 1)",
                            "backgroundColor": "rgba(153, 102, 255, 0.2)",
                            "fill": True,
                            "tension": 0.4
                        }
                    ]
                }
                return jsonify(chart_data)

            except Exception as e:
                logger.error(f"Error getting humidity chart data: {e}")
                return jsonify({"error": str(e)}), 500
        
        @app.route("/data")
        @login_required
        def get_data_api():
            """Historical data API"""
            selected_date = request.args.get('date')
            latest_only = request.args.get('latest_only', 'true').lower() == 'true'
            rows = self.db_manager.get_data_by_date_pivoted(selected_date, latest_only=latest_only)
            data = [{"waktu": r[0], "dryer1": r[1], "dryer2": r[2], "dryer3": r[3]} for r in rows]
            return jsonify(data)
        
        @app.route("/humidity-data")
        @login_required
        def get_humidity_data_api():
            """Historical humidity data API"""
            selected_date = request.args.get('date')
            sensor_id = request.args.get('sensor_id', 'humidity1')
            latest_only = request.args.get('latest_only', 'true').lower() == 'true'
            rows = self.db_manager.get_humidity_by_date(selected_date, sensor_id, latest_only=latest_only)
            data = [{"waktu": r[0], "humidity": r[1]} for r in rows]
            return jsonify(data)

        @app.route("/download")
        @login_required
        def download_excel():
            """Excel download endpoint"""
            selected_date = request.args.get('date')
            rows = self.db_manager.get_data_by_date_pivoted(selected_date)
            
            if not rows: 
                return "Tidak ada data.", 404
                
            wb = Workbook()
            ws = wb.active
            ws.title = f"Data Suhu {selected_date}"
            ws.append(["Waktu (WIB)", "Dryer 1 (°C)", "Dryer 2 (°C)", "Dryer 3 (°C)"])
            
            for row in rows: 
                ws.append(list(row))
                
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            
            filename = f"laporan_{selected_date}.xlsx"
            return Response(
                buffer, 
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                headers={'Content-Disposition': f'attachment;filename={filename}'}
            )
        
        @app.route("/keepalive")
        def keepalive():
            """Health check endpoint"""
            return {
                "status": "alive", 
                "timestamp": self.config.format_indonesia_time(),
                "mqtt_connected": self.mqtt_service.is_connected,
                "subdirectory": SUBDIRECTORY,
                "latest_data": {
                    "temperatures": self.get_latest_temperatures(),
                    "humidity": self.get_latest_humidity()
                }
            }
        
        @app.route('/kedi')
        @login_required
        @check_session_timeout
        def kedi():
            return render_template('navigation/kedi.html', active_page='kedi', subdirectory=SUBDIRECTORY)
        
        @app.route('/boiler')
        @login_required
        @check_session_timeout
        def boiler():
            return render_template('navigation/boiler.html', active_page='boiler', subdirectory=SUBDIRECTORY)

        
        return app
    
    def start_app(self):
        """Start the application"""
        # Create initial user
        admin_user = os.getenv('ADMIN_USER')
        admin_pass = os.getenv('ADMIN_PASSWORD')
        if admin_user and admin_pass:
            self.db_manager.create_initial_user(admin_user, admin_pass)
        else:
            logger.warning("ADMIN_USER dan ADMIN_PASSWORD tidak diatur.")
            
        try:
            # Start MQTT connection
            mqtt_connected = self.mqtt_service.connect()
            if not mqtt_connected:
                logger.warning("MQTT connection failed, continuing without MQTT")
            
            # Start background tasks
            self.start_background_tasks()
            
            # Create Flask app
            app = self.create_flask_app()
            logger.info(f"Temperature monitoring application started for subdirectory: {SUBDIRECTORY}")
            return app
            
        except Exception as e:
            logger.error(f"Error starting application: {e}")
            self.stop_background_tasks()
            self.mqtt_service.disconnect()
            raise

# Factory function for WSGI
def create_app():
    """Factory function to create Flask application"""
    try:
        monitor = TemperatureMonitor()
        app = monitor.start_app()
        logger.info("Application factory completed successfully")
        return app
    except Exception as e:
        logger.error(f"Failed to create application: {e}")
        raise

# WSGI entry point for shared hosting
application = create_app()

if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=False)