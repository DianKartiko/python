import paho.mqtt.client as mqtt
import logging
import time
import threading

logger = logging.getLogger(__name__)

class MQTTService:
    """Class untuk mengelola koneksi dan komunikasi MQTT dengan auto-reconnection"""
    
    def __init__(self, config, data_callback):
        self.config = config
        self.data_callback = data_callback
        self.client = mqtt.Client()
        self.is_connected = False
        self.should_reconnect = True
        self.reconnect_thread = None
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_delay = 300  # 5 minutes
        self.setup_callbacks()
        
    def setup_callbacks(self):
        """Setup callback functions untuk MQTT client"""
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback ketika terhubung ke MQTT broker"""
        if rc == 0:
            self.is_connected = True
            self.reconnect_delay = 5  # Reset delay on successful connection
            logger.info(f"MQTT Connected successfully at {self.config.format_indonesia_time()}")
            
            # Subscribe to all topics
            for topic_name, topic in self.config.MQTT_TOPICS.items():
                if topic: 
                    self.client.subscribe(topic)
                    logger.info(f"Subscribed to {topic_name}: {topic}")
        else:
            logger.error(f"MQTT Connection failed with code {rc}")
            self.is_connected = False
    
    def _on_message(self, client, userdata, msg):
        """Callback ketika menerima message MQTT"""
        try:
            raw_suhu = float(msg.payload.decode())
            if self.data_callback:
                self.data_callback(raw_suhu, msg.topic)
        except Exception as e:
            logger.error(f"Error parsing MQTT data: {e}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback ketika terputus dari MQTT broker"""
        self.is_connected = False
        logger.warning(f"MQTT Disconnected with code {rc} at {self.config.format_indonesia_time()}")
        
        # Start reconnection process if needed
        if self.should_reconnect and rc != 0:  # rc != 0 means unexpected disconnect
            self._start_reconnection()
    
    def _start_reconnection(self):
        """Start the reconnection process in a separate thread"""
        if self.reconnect_thread is None or not self.reconnect_thread.is_alive():
            self.reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
            self.reconnect_thread.start()
    
    def _reconnect_loop(self):
        """Reconnection loop that runs in a separate thread"""
        while self.should_reconnect and not self.is_connected:
            try:
                logger.info(f"Attempting to reconnect to MQTT broker in {self.reconnect_delay} seconds...")
                time.sleep(self.reconnect_delay)
                
                if not self.should_reconnect:
                    break
                    
                logger.info("Reconnecting to MQTT broker...")
                self.client.connect(self.config.MQTT_BROKER, self.config.MQTT_PORT, 60)
                
                # If connection is successful, the on_connect callback will handle the rest
                # Wait a bit to see if connection was successful
                time.sleep(2)
                
                if not self.is_connected:
                    # Exponential backoff with max limit
                    self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
                    
            except Exception as e:
                logger.error(f"MQTT Reconnection failed: {e}")
                # Exponential backoff with max limit
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
    
    def connect(self):
        """Connect ke MQTT broker"""
        try:
            self.should_reconnect = True
            self.client.connect(self.config.MQTT_BROKER, self.config.MQTT_PORT, 60)
            self.client.loop_start()
            logger.info("MQTT Client started")
            return True
        except Exception as e:
            logger.error(f"MQTT Connection failed: {e}")
            # Start reconnection process
            self._start_reconnection()
            return False
    
    def disconnect(self):
        """Disconnect dari MQTT broker"""
        self.should_reconnect = False
        self.client.loop_stop()
        self.client.disconnect()
        
        # Wait for reconnect thread to finish
        if self.reconnect_thread and self.reconnect_thread.is_alive():
            self.reconnect_thread.join(timeout=5)
    
    def is_broker_connected(self):
        """Check if connected to MQTT broker"""
        return self.is_connected