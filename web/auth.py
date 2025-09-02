from flask import request, url_for, redirect, session, flash
from flask_login import current_user, logout_user
from urllib.parse import urlparse, urljoin
from functools import wraps
import time
import logging

logger = logging.getLogger(__name__)

def is_safe_url(target):
    """Validasi URL untuk mencegah open redirect vulnerability"""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

def check_session_timeout(f):
    """Decorator untuk mengecek apakah session sudah timeout"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated:
            # Cek apakah ada timestamp login di session
            if 'login_timestamp' in session:
                login_time = session['login_timestamp']
                current_time = time.time()
                
                # Hitung durasi login (24 jam = 86400 detik)
                session_duration = current_time - login_time
                max_session_duration = 24 * 60 * 60  # 24 jam dalam detik
                
                if session_duration > max_session_duration:
                    # Session expired, logout otomatis
                    logout_user()
                    session.clear()  # Bersihkan semua session data
                    flash('Your session has expired after 24 hours. Please log in again.', 'warning')
                    return redirect(url_for('login'))
                else:
                    # Session masih valid, update last activity
                    session['last_activity'] = current_time
            else:
                # Tidak ada timestamp login, anggap session tidak valid
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
    remaining_time = (24 * 60 * 60) - session_age  # sisa waktu dalam detik
    
    return {
        'login_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(login_time)),
        'session_age_hours': session_age / 3600,
        'remaining_hours': max(0, remaining_time / 3600),
        'remaining_minutes': max(0, (remaining_time % 3600) / 60),
        'is_expiring_soon': remaining_time < (2 * 3600),  # kurang dari 2 jam
        'expires_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(login_time + (24 * 60 * 60)))
    }