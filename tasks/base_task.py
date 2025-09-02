import threading
import time
import logging

logger = logging.getLogger(__name__)

class BackgroundTask:
    """Base class untuk background tasks"""
    
    def __init__(self, interval, name="BackgroundTask"):
        self.interval = interval
        self.name = name
        self.thread = None
        self.is_running = False
        
    def task(self):
        """Method yang harus di-override oleh subclass"""
        raise NotImplementedError
        
    def run(self):
        """Main run loop for the background task"""
        self.is_running = True
        while self.is_running:
            try:
                if self.is_running: 
                    self.task()
            except Exception as e:
                logger.error(f"Error in {self.name}: {e}")
            if self.interval > 0:
                time.sleep(self.interval)
                
    def start(self):
        """Start the background task in a separate thread"""
        self.thread = threading.Thread(target=self.run, daemon=True, name=self.name)
        self.thread.start()
        
    def stop(self):
        """Stop the background task"""
        self.is_running = False
        if self.thread: 
            self.thread.join(timeout=5)