import sqlite3
import logging
from flask_login import UserMixin
from werkzeug.security import generate_password_hash

logger = logging.getLogger(__name__)

class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

class DatabaseManager:
    """Class untuk mengelola operasi database untuk multi-system monitoring"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.initialize_database()
        
    def initialize_database(self):
        """Initialize database dengan table untuk semua sistem"""
        with self.get_connection() as conn:
            c = conn.cursor()
            
            # Tabel untuk Dryer (existing)
            c.execute("""
                CREATE TABLE IF NOT EXISTS suhu (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    waktu TEXT,
                    dryer_id TEXT, 
                    suhu REAL
                )
            """)
            
            # Tabel untuk Kedi
            c.execute("""
                CREATE TABLE IF NOT EXISTS kedi_suhu (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    waktu TEXT,
                    kedi_id TEXT, 
                    suhu REAL
                )
            """)
            
            # Tabel untuk Boiler
            c.execute("""
                CREATE TABLE IF NOT EXISTS boiler_suhu (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    waktu TEXT,
                    boiler_id TEXT, 
                    suhu REAL
                )
            """)
            
            # Tabel untuk Users (existing)
            c.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    username TEXT UNIQUE NOT NULL, 
                    password TEXT NOT NULL
                )
            """)
            
        logger.info(f"Database multi-system initialized at: {self.db_path}")
    
    def get_connection(self):
        """Mendapatkan koneksi database yang thread-safe"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    
    # === User Management Methods (existing) ===
    def get_user_by_username(self, username):
        try:
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
        """Membuat user awal jika belum ada"""
        if not self.get_user_by_username(username):
            logger.info(f"User '{username}' tidak ditemukan, mencoba membuat user baru...")
            try:
                with self.get_connection() as conn:
                    c = conn.cursor()
                    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
                    c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
                    conn.commit()
                    logger.info(f"User '{username}' berhasil dibuat dari environment secrets.")
            except Exception as e:
                logger.error(f"Gagal membuat initial user: {e}")
    
    # === Generic Temperature Methods ===
    def insert_temperature(self, waktu, device_id, suhu, table_type="dryer"):
        """Insert data suhu ke database dengan menyertakan ID device dan tipe tabel"""
        table_map = {
            "dryer": "suhu",
            "kedi": "kedi_suhu", 
            "boiler": "boiler_suhu"
        }
        
        column_map = {
            "dryer": "dryer_id",
            "kedi": "kedi_id",
            "boiler": "boiler_id"
        }
        
        table_name = table_map.get(table_type, "suhu")
        column_name = column_map.get(table_type, "dryer_id")
        
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(f"INSERT INTO {table_name} (waktu, {column_name}, suhu) VALUES (?, ?, ?)", 
                         (waktu, device_id, suhu))
            return True
        except Exception as e:
            logger.error(f"Error inserting temperature to {table_name}: {e}")
            return False
    
    def get_data_by_date_pivoted(self, date_str, latest_only=False, table_type="dryer"):
        """Mendapatkan data untuk tanggal tertentu dengan pivot"""
        table_map = {
            "dryer": ("suhu", "dryer_id", ["dryer1", "dryer2", "dryer3"]),
            "kedi": ("kedi_suhu", "kedi_id", ["kedi1", "kedi2"]),
            "boiler": ("boiler_suhu", "boiler_id", ["boiler1", "boiler2"])
        }
        
        table_name, id_column, device_list = table_map.get(table_type, table_map["dryer"])
        
        try:
            start_time = f"{date_str} 00:00:00"
            end_time = f"{date_str} 23:59:59"
            
            # Build CASE statements dynamically
            case_statements = []
            for device in device_list:
                case_statements.append(f"MAX(CASE WHEN {id_column} = '{device}' THEN suhu END) as {device}_suhu")
            
            case_clause = ",\n                ".join(case_statements)
            
            sql = f"""
            SELECT
                strftime('%Y-%m-%d %H:%M:%S', waktu) as timestamp,
                {case_clause}
            FROM {table_name}
            WHERE waktu BETWEEN ? AND ?
            GROUP BY timestamp
            """
            
            if latest_only:
                sql += " ORDER BY timestamp DESC LIMIT 1"
            else:
                sql += " ORDER BY timestamp ASC"

            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(sql, (start_time, end_time))
                return c.fetchall()
        except Exception as e:
            logger.error(f"Error getting pivoted data for date {date_str} from {table_name}: {e}")
            return []
    
    def get_data_since(self, since_time, table_type="dryer"):
        """Mendapatkan data sejak waktu tertentu"""
        table_map = {
            "dryer": "suhu",
            "kedi": "kedi_suhu",
            "boiler": "boiler_suhu"
        }
        
        table_name = table_map.get(table_type, "suhu")
        
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(f"SELECT * FROM {table_name} WHERE datetime(waktu) >= datetime(?) ORDER BY waktu", (since_time,))
                return c.fetchall()
        except Exception as e:
            logger.error(f"Error getting data since {since_time} from {table_name}: {e}")
            return []
    
    def get_recent_data(self, limit=5, table_type="dryer"):
        """Mendapatkan data terbaru"""
        table_map = {
            "dryer": ("suhu", "dryer_id"),
            "kedi": ("kedi_suhu", "kedi_id"),
            "boiler": ("boiler_suhu", "boiler_id")
        }
        
        table_name, id_column = table_map.get(table_type, table_map["dryer"])
        
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(f"SELECT waktu, {id_column}, suhu FROM {table_name} ORDER BY id DESC LIMIT ?", (limit,))
                return c.fetchall()
        except Exception as e:
            logger.error(f"Error getting recent data from {table_name}: {e}")
            return []