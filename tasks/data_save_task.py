import logging
from .base_task import BackgroundTask

logger = logging.getLogger(__name__)

class DataSaveTask(BackgroundTask):
    """Task untuk menyimpan data ke database setiap interval tertentu."""
    
    def __init__(self, config, data_provider, db_manager):
        super().__init__(config.DATA_SAVE_INTERVAL, "DataSaveTask")
        self.config = config
        self.data_provider = data_provider
        self.db_manager = db_manager
    
    def task(self):
        """Menyimpan data suhu terakhir dari memori ke database."""
        latest_temps = self.data_provider.get_latest_temperatures()
        waktu = self.config.format_indonesia_time_simple()
        
        logger.info(f"Menjalankan DataSaveTask pada {waktu}. Menyimpan data terakhir...")
        
        # Save dryer data
        dryer_data = latest_temps.get('dryer', {})
        for dryer_id, temp in dryer_data.items():
            if temp is not None:
                success = self.db_manager.insert_temperature(waktu, dryer_id, temp, "dryer")
                if success:
                    logger.info(f"Data tersimpan untuk {dryer_id}: {waktu} | {temp:.2f}°C")
                else:
                    logger.error(f"Gagal menyimpan data untuk {dryer_id}")
        
        # Save kedi data
        kedi_data = latest_temps.get('kedi', {})
        for kedi_id, temp in kedi_data.items():
            if temp is not None:
                success = self.db_manager.insert_temperature(waktu, kedi_id, temp, "kedi")
                if success:
                    logger.info(f"Data tersimpan untuk {kedi_id}: {waktu} | {temp:.2f}°C")
                else:
                    logger.error(f"Gagal menyimpan data untuk {kedi_id}")
        
        # Save boiler data
        boiler_data = latest_temps.get('boiler', {})
        for boiler_id, temp in boiler_data.items():
            if temp is not None:
                success = self.db_manager.insert_temperature(waktu, boiler_id, temp, "boiler")
                if success:
                    logger.info(f"Data tersimpan untuk {boiler_id}: {waktu} | {temp:.2f}°C")
                else:
                    logger.error(f"Gagal menyimpan data untuk {boiler_id}")