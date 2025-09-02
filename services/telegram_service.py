from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Bot
from telegram.ext import ContextTypes, ApplicationBuilder, CallbackQueryHandler, MessageHandler, filters
import asyncio
import threading
import logging
from queue import Queue, Empty
from openpyxl import Workbook
import os

logger = logging.getLogger(__name__)

class TelegramService:
    """Class untuk mengelola komunikasi Telegram dengan antrean dan worker."""
    
    def __init__(self, config, db_manager):
        self.config = config
        self.db_manager = db_manager
        self.bot = Bot(token=config.TELEGRAM_TOKEN)
        self.application = ApplicationBuilder().token(self.config.TELEGRAM_TOKEN).build()
        self._setup_handlers()
        self.message_queue = Queue()
        self.worker_thread = None
        self.is_worker_running = False

    def _setup_handlers(self):
        self.application.add_handler(MessageHandler(filters.Regex('^Mulai$'), self.start))
        self.application.add_handler(CallbackQueryHandler(self.button))

    async def _send_message_async(self, message):
        try:
            await self.bot.send_message(chat_id=self.config.CHAT_ID, text=message, parse_mode="Markdown")
            logger.info("Pesan Telegram berhasil dikirim dari worker.")
        except Exception as e:
            logger.error(f"Gagal mengirim pesan dari worker: {e}")

    async def _send_document_async(self, file_path, caption):
        try:
            with open(file_path, "rb") as file:
                await self.bot.send_document(chat_id=self.config.CHAT_ID, document=file, caption=caption, parse_mode="Markdown")
            logger.info(f"Dokumen {file_path} berhasil dikirim dari worker.")
        except Exception as e:
            logger.error(f"Gagal mengirim dokumen dari worker: {e}")

    def _process_queue(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while self.is_worker_running:
            try:
                task_type, *args = self.message_queue.get(timeout=1) 
                if task_type == 'message':
                    loop.run_until_complete(self._send_message_async(args[0]))
                elif task_type == 'document':
                    loop.run_until_complete(self._send_document_async(args[0], args[1]))
                self.message_queue.task_done()
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error di dalam Telegram worker thread: {e}")

    def start_worker(self):
        if not self.is_worker_running:
            self.is_worker_running = True
            self.worker_thread = threading.Thread(target=self._process_queue, daemon=True, name="TelegramWorker")
            self.worker_thread.start()
            logger.info("Telegram worker thread dimulai.")

    def stop_worker(self):
        self.is_worker_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
            logger.info("Telegram worker thread dihentikan.")

    def send_message(self, message):
        self.message_queue.put(('message', message))

    def send_document(self, file_path, caption):
        self.message_queue.put(('document', file_path, caption))
    
    async def start(self, update, context):
        keyboard = [
            [InlineKeyboardButton("Test Message", callback_data="test")],
            [InlineKeyboardButton("Data Dryers", callback_data="data_dryer")],
            [InlineKeyboardButton("Data Kedi", callback_data="data_kedi")],
            [InlineKeyboardButton("Data Boiler", callback_data="data_boiler")],
            [InlineKeyboardButton("Force Excel", callback_data="force_excel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Pilih opsi:", reply_markup=reply_markup)
    
    async def button(self, query, context):
        query = update.callback_query
        await query.answer()
        
        if query.data == "test":
            await self._handle_test(query)
        elif query.data == "data_dryer":
            await self._handle_data(query, "dryer")
        elif query.data == "data_kedi":
            await self._handle_data(query, "kedi")
        elif query.data == "data_boiler":
            await self._handle_data(query, "boiler")
        elif query.data == "force_excel":
            await self._handle_force_excel(query)
    
    async def _handle_test(self, query):
        current_time = self.config.format_indonesia_time()
        test_message = f"🧪 Test Message\n🕐 Waktu: {current_time}\n✅ Bot berfungsi normal!"
        await query.edit_message_text(test_message)
    
    async def _handle_data(self, query, system_type):
        recent_data = self.db_manager.get_recent_data(5, system_type)
        if recent_data:
            data_text = f"📊 5 Data Terakhir {system_type.upper()}:\n\n"
            for row in recent_data:
                data_text += f"*{row[1].upper()}*:\n🕐 {row[0]} WIB\n🌡️ {row[2]:.1f}°C\n\n"
        else:
            data_text = f"❌ Tidak ada data tersedia untuk {system_type}"
        await query.edit_message_text(data_text)
    
    async def _handle_force_excel(self, query):
        await query.edit_message_text("📊 Generating Excel... Please wait...")
        today_str = self.config.get_indonesia_time().strftime('%Y-%m-%d')
        
        # Generate Excel untuk semua sistem
        systems = ["dryer", "kedi", "boiler"]
        temp_dir = "/tmp" if os.path.exists("/tmp") else "."
        filename = os.path.join(temp_dir, f"manual_report_all_systems_{today_str}.xlsx")
        
        wb = Workbook()
        
        for i, system in enumerate(systems):
            if i == 0:
                ws = wb.active
                ws.title = f"Data {system.title()} {today_str}"
            else:
                ws = wb.create_sheet(title=f"Data {system.title()} {today_str}")
            
            rows = self.db_manager.get_data_by_date_pivoted(today_str, table_type=system)
            
            if system == "dryer":
                ws.append(["Waktu (WIB)", "Dryer 1 (°C)", "Dryer 2 (°C)", "Dryer 3 (°C)"])
            elif system == "kedi":
                ws.append(["Waktu (WIB)", "Kedi 1 (°C)", "Kedi 2 (°C)"])
            elif system == "boiler":
                ws.append(["Waktu (WIB)", "Boiler 1 (°C)", "Boiler 2 (°C)"])
            
            for row in rows: 
                ws.append(list(row))
        
        wb.save(filename)
        caption = f"📊 Laporan Manual Semua Sistem - {today_str}"
        
        with open(filename, "rb") as file:
            await self.bot.send_document(chat_id=query.message.chat_id, document=file, caption=caption)
        
        try: 
            os.remove(filename)
        except: 
            pass
            
        await query.edit_message_text(f"✅ Excel sent! All systems data")
    
    def start_polling(self):
        if self.application:
            self.application.run_polling()