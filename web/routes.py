from flask import render_template, request, jsonify, Response, redirect, url_for, flash, session
from flask_login import login_required, login_user, logout_user, current_user
from werkzeug.security import check_password_hash
from openpyxl import Workbook
from io import BytesIO
import json
import time
import logging
from .auth import check_session_timeout, is_safe_url

logger = logging.getLogger(__name__)

class WebRoutes:
    """Class untuk mengelola semua web routes"""
    
    def __init__(self, config, db_manager, monitor_instance):
        self.config = config
        self.db_manager = db_manager
        self.monitor = monitor_instance
        
    def register_routes(self, app):
        """Register semua routes ke Flask app"""
        
        # === Authentication Routes ===
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
                    
                    flash(f'Welcome back, {user.username}! Session valid for 24 hours.', 'success')
                    logger.info(f"User {user.username} logged in successfully from {request.remote_addr}")
                    return redirect(next_page)
                else:
                    flash('Username atau password salah', 'danger')
                    logger.warning(f"Failed login attempt for username: {username} from {request.remote_addr}")
            
            return render_template('login.html')
        
        @app.route('/logout')
        @login_required
        def logout():
            logout_user()
            flash('You have been logged out successfully.', 'info')
            return redirect(url_for('login'))
        
        # === Main Dashboard Routes ===
        @app.route("/")
        @login_required
        @check_session_timeout
        def index():
            return render_template("index.html", active_page='dryer')
        
        @app.route("/dwidaya")
        @login_required
        @check_session_timeout
        def dwidaya():
            with self.monitor.data_lock:
                context = {
                    "dryer_temps": self.monitor.latest_temperatures.get('dryer', {}),
                    "kedi_temps": self.monitor.latest_temperatures.get('kedi', {}),
                    "boiler_temps": self.monitor.latest_temperatures.get('boiler', {}),
                    "current_time": self.config.format_indonesia_time(),
                    "timezone": str(self.config.INDONESIA_TZ)
                }
            return render_template("dwidaya.html", **context)
        
        @app.route('/kedi')
        @login_required
        @check_session_timeout
        def kedi():
            return render_template('navigation/kedi.html', active_page='kedi')
        
        @app.route('/boiler')
        @login_required
        @check_session_timeout
        def boiler():
            return render_template('navigation/boiler.html', active_page='boiler')
        
        # === Data API Routes ===
        @app.route("/data")
        @login_required
        def get_data_api():
            selected_date = request.args.get('date')
            system_type = request.args.get('type', 'dryer')  # default to dryer
            
            rows = self.db_manager.get_data_by_date_pivoted(selected_date, latest_only=True, table_type=system_type)
            
            # Format data berdasarkan sistem
            if system_type == "dryer":
                data = [{"waktu": r[0], "dryer1": r[1], "dryer2": r[2], "dryer3": r[3]} for r in rows]
            elif system_type == "kedi":
                data = [{"waktu": r[0], "kedi1": r[1], "kedi2": r[2]} for r in rows]
            elif system_type == "boiler":
                data = [{"waktu": r[0], "boiler1": r[1], "boiler2": r[2]} for r in rows]
            else:
                data = []
                
            return jsonify(data)
        
        @app.route("/chart-data")
        @login_required
        def get_chart_data():
            try:
                selected_date = request.args.get('date', self.config.get_indonesia_time().strftime('%Y-%m-%d'))
                system_type = request.args.get('type', 'dryer')
                
                rows = self.db_manager.get_data_by_date_pivoted(selected_date, table_type=system_type)
                
                if not rows:
                    return jsonify({"labels": [], "datasets": []})
                
                labels = []
                datasets_data = {}
                
                for row in rows:
                    waktu = row[0].split(' ')[1][:5]  # HH:MM
                    labels.append(waktu)
                    
                    # Dynamic dataset creation based on system type
                    if system_type == "dryer":
                        datasets_data.setdefault("Dryer 1", []).append(row[1])
                        datasets_data.setdefault("Dryer 2", []).append(row[2])
                        datasets_data.setdefault("Dryer 3", []).append(row[3])
                    elif system_type == "kedi":
                        datasets_data.setdefault("Kedi 1", []).append(row[1])
                        datasets_data.setdefault("Kedi 2", []).append(row[2])
                    elif system_type == "boiler":
                        datasets_data.setdefault("Boiler 1", []).append(row[1])
                        datasets_data.setdefault("Boiler 2", []).append(row[2])
                
                # Color mapping untuk chart
                colors = [
                    ("rgba(255, 99, 132, 1)", "rgba(255, 99, 132, 0.2)"),
                    ("rgba(54, 162, 235, 1)", "rgba(54, 162, 235, 0.2)"),
                    ("rgba(75, 192, 192, 1)", "rgba(75, 192, 192, 0.2)"),
                ]
                
                datasets = []
                for i, (label, data) in enumerate(datasets_data.items()):
                    color_idx = i % len(colors)
                    datasets.append({
                        "label": label,
                        "data": data,
                        "borderColor": colors[color_idx][0],
                        "backgroundColor": colors[color_idx][1],
                        "fill": True,
                        "tension": 0.4
                    })
                
                chart_data = {
                    "labels": labels,
                    "datasets": datasets
                }
                return jsonify(chart_data)
                
            except Exception as e:
                logger.error(f"Error getting chart data: {e}")
                return jsonify({"error": str(e)}), 500
        
        # === Stream Routes ===
        @app.route("/stream-data")
        @login_required
        def stream_data():
            def generate_data():
                try:
                    while True:
                        with self.monitor.data_lock:
                            all_temps = self.monitor.latest_temperatures.copy()
                        
                        # Format semua data sistem
                        data_payload = {}
                        
                        # Dryer data
                        dryer_data = all_temps.get('dryer', {})
                        for key, temp in dryer_data.items():
                            data_payload[key] = f"{temp:.1f}" if temp is not None else "N/A"
                        
                        # Kedi data
                        kedi_data = all_temps.get('kedi', {})
                        for key, temp in kedi_data.items():
                            data_payload[key] = f"{temp:.1f}" if temp is not None else "N/A"
                        
                        # Boiler data
                        boiler_data = all_temps.get('boiler', {})
                        for key, temp in boiler_data.items():
                            data_payload[key] = f"{temp:.1f}" if temp is not None else "N/A"
                        
                        yield f"data: {json.dumps(data_payload)}\n\n"
                        time.sleep(2)
                        
                except GeneratorExit:
                    logger.info("Koneksi stream data ditutup oleh klien.")
            
            return Response(generate_data(), mimetype='text/event-stream')
        
        @app.route('/stream-notifications')
        @login_required
        def stream_notifications():
            def generate():
                logger.info("[SSE Stream] Klien baru terhubung ke stream notifikasi.")
                try:
                    while True:
                        try:
                            notification = self.monitor.notification_queue.get(timeout=25)
                            logger.info(f"[SSE Stream] MENGIRIM NOTIFIKASI KE KLIEN: {notification}")
                            yield f"data: {json.dumps(notification)}\n\n"
                        except:
                            yield ": heartbeat\n\n"
                except GeneratorExit:
                    logger.info("[SSE Stream] Klien terputus dari stream notifikasi.")
            
            return Response(generate(), mimetype='text/event-stream')
        
        # === Download Routes ===
        @app.route("/download")
        @login_required
        def download_excel():
            selected_date = request.args.get('date')
            system_type = request.args.get('type', 'dryer')
            
            rows = self.db_manager.get_data_by_date_pivoted(selected_date, table_type=system_type)
            if not rows: 
                return "Tidak ada data.", 404
            
            wb = Workbook()
            ws = wb.active
            
            # Header berdasarkan sistem
            if system_type == "dryer":
                ws.append(["Waktu (WIB)", "Dryer 1 (°C)", "Dryer 2 (°C)", "Dryer 3 (°C)"])
            elif system_type == "kedi":
                ws.append(["Waktu (WIB)", "Kedi 1 (°C)", "Kedi 2 (°C)"])
            elif system_type == "boiler":
                ws.append(["Waktu (WIB)", "Boiler 1 (°C)", "Boiler 2 (°C)"])
            
            for row in rows: 
                ws.append(list(row))
            
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            
            filename = f"laporan_{system_type}_{selected_date}.xlsx"
            return Response(buffer, 
                          mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                          headers={'Content-Disposition': f'attachment;filename={filename}'})
        
        # === Utility Routes ===
        @app.route("/keepalive")
        def keepalive():
            return {"status": "alive", "timestamp": self.config.format_indonesia_time()}
        
        @app.route("/test-telegram")
        @login_required
        def test_telegram():
            message = f"🧪 **Test Message**\n🕐 {self.config.format_indonesia_time()}"
            self.monitor.telegram_service.send_message(message)
            return {"status": "success", "message": "Test message queued"}