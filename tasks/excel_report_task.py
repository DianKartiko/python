import datetime
import time
import logging
import os
from openpyxl import Workbook
from .base_task import BackgroundTask

logger = logging.getLogger(__name__)

class DailyExcelReportTask(BackgroundTask):
    """Task untuk membuat laporan Excel harian"""
    
    def __init__(self, config, db_manager, telegram_service):
        super().__init__(-1, "DailyExcelReportTask")
        self.config = config
        self.db_manager = db_manager
        self.telegram_service = telegram_service
        
    def run(self):
        """Override run method untuk daily scheduling"""
        self.is_running = True
        logger.info(f"Starting {self.name}. Laporan akan dikirim setiap pukul 00:00.")
        
        while self.is_running:
            try:
                now = self.config.get_indonesia_time()
                tomorrow = now + datetime.timedelta(days=1)
                midnight = tomorrow.replace(hour=0, minute=0, second=5, microsecond=0)
                seconds_to_wait = (midnight - now).total_seconds()
                
                logger.info(f"Laporan harian berikutnya dalam {seconds_to_wait / 3600:.2f} jam.")
                
                sleep_end_time = time.time() + seconds_to_wait
                while time.time() < sleep_end_time and self.is_running:
                    time.sleep(1)
                
                if self.is_running:
                    self.task()
                    
            except Exception as e:
                logger.error(f"Error di dalam loop {self.name}: {e}")
                time.sleep(300)
    
    def task(self):
        """Generate daily Excel report untuk semua sistem"""
        yesterday = (self.config.get_indonesia_time() - datetime.timedelta(days=1))
        yesterday_str = yesterday.strftime('%Y-%m-%d')
        
        logger.info(f"Memulai pembuatan laporan Excel untuk tanggal: {yesterday_str}")
        
        # Create workbook dengan multiple sheets
        wb = Workbook()
        systems = [
            ("dryer", ["Waktu (WIB)", "Dryer 1 (°C)", "Dryer 2 (°C)", "Dryer 3 (°C)"]),
            ("kedi", ["Waktu (WIB)", "Kedi 1 (°C)", "Kedi 2 (°C)"]),
            ("boiler", ["Waktu (WIB)", "Boiler 1 (°C)", "Boiler 2 (°C)"])
        ]
        
        has_data = False
        
        for i, (system, headers) in enumerate(systems):
            if i == 0:
                ws = wb.active
                ws.title = f"Data {system.title()} {yesterday_str}"
            else:
                ws = wb.create_sheet(title=f"Data {system.title()} {yesterday_str}")
            
            rows = self.db_manager.get_data_by_date_pivoted(yesterday_str, table_type=system)
            
            ws.append(headers)
            for row in rows:
                ws.append(list(row))
                
            if rows:
                has_data = True
                logger.info(f"Data {system} untuk {yesterday_str}: {len(rows)} records")
        
        if not has_data:
            logger.warning(f"Tidak ada data untuk dilaporkan pada tanggal {yesterday_str}.")
            return
        
        # Save and send file
        temp_dir = "/tmp" if os.path.exists("/tmp") else "."
        filename = os.path.join(temp_dir, f"laporan_harian_{yesterday_str}.xlsx")
        wb.save(filename)
        
        caption = f"📊 *Laporan Harian Semua Sistem - {yesterday.strftime('%d %B %Y')}*"
        self.telegram_service.send_document(filename, caption)
        
        time.sleep(10)
        try: 
            os.remove(filename)
        except OSError: 
            pass