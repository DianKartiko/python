import json
import logging
import paho.mqtt.client as mqtt
import threading
import time
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)

class MQTTService:
    """Service untuk mengelola koneksi MQTT dengan support JSON parsing"""
    
    def __init__(self, config, message_callback: Callable[[Any, str], None]):
        self.config = config
        self.message_callback = message_callback
        self.client = None
        self.is_connected = False
        self.reconnect_thread = None
        self.should_reconnect = True
        
        # Subscribe to all configured topics
        self.subscribed_topics = []
        for device_id, topic in self.config.MQTT_TOPICS.items():
            if topic:  # Only add non-empty topics
                self.subscribed_topics.append(topic)
    
    def connect(self):
        """Establish MQTT connection"""
        try:
            self.client = mqtt.Client()
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect
            
            logger.info(f"Connecting to MQTT broker: {self.config.MQTT_BROKER}:{self.config.MQTT_PORT}")
            self.client.connect(self.config.MQTT_BROKER, self.config.MQTT_PORT, 60)
            
            # Start network loop in background
            self.client.loop_start()
            
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            self._start_reconnect_thread()
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.should_reconnect = False
        
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            
        if self.reconnect_thread and self.reconnect_thread.is_alive():
            self.reconnect_thread.join()
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback ketika terkoneksi ke MQTT broker"""
        if rc == 0:
            self.is_connected = True
            logger.info("Connected to MQTT broker successfully")
            
            # Subscribe to all configured topics
            for topic in self.subscribed_topics:
                client.subscribe(topic)
                logger.info(f"Subscribed to topic: {topic}")
                
        else:
            logger.error(f"Failed to connect to MQTT broker with code: {rc}")
            self._start_reconnect_thread()
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback ketika terputus dari MQTT broker"""
        self.is_connected = False
        logger.warning(f"Disconnected from MQTT broker with code: {rc}")
        
        if self.should_reconnect and rc != 0:
            self._start_reconnect_thread()
    
    def _on_message(self, client, userdata, msg):
        """Callback ketika menerima pesan MQTT"""
        try:
            topic = msg.topic
            raw_payload = msg.payload.decode('utf-8')
            
            logger.debug(f"Received MQTT message - Topic: {topic}, Payload: {raw_payload}")
            
            # Parse payload berdasarkan format
            parsed_data = self._parse_payload(raw_payload, topic)
            
            if parsed_data is not None:
                # Call main application callback
                self.message_callback(parsed_data, topic)
            else:
                logger.warning(f"Failed to parse payload from topic {topic}: {raw_payload}")
                
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
            logger.error(f"Topic: {topic}, Raw payload: {raw_payload}")
    
    def _parse_payload(self, payload: str, topic: str) -> Optional[Any]:
        """Parse MQTT payload - supports both JSON and simple numeric formats"""
        try:
            # Remove whitespace
            payload = payload.strip()
            
            # Try to parse as JSON first
            if payload.startswith('{') and payload.endswith('}'):
                return self._parse_json_payload(payload)
            
            # Try to parse as simple numeric value
            else:
                return self._parse_numeric_payload(payload)
                
        except Exception as e:
            logger.error(f"Error parsing payload from {topic}: {e}")
            return None
    
    def _parse_json_payload(self, payload: str) -> Optional[Dict[str, Any]]:
        """Parse JSON format payload"""
        try:
            data = json.loads(payload)
            
            # Validate that it's a dictionary
            if not isinstance(data, dict):
                logger.warning(f"JSON payload is not a dictionary: {payload}")
                return None
            
            # Validate and convert numeric fields
            parsed_result = {}
            
            for key, value in data.items():
                if key in ['temperature', 'humidity', 'pressure', 'water_level']:
                    try:
                        parsed_result[key] = float(value)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid numeric value for {key}: {value}")
                        parsed_result[key] = None
                else:
                    # Keep other fields as-is
                    parsed_result[key] = value
            
            return parsed_result
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing JSON payload: {e}")
            return None
    
    def _parse_numeric_payload(self, payload: str) -> Optional[float]:
        """Parse simple numeric payload"""
        try:
            return float(payload)
        except ValueError:
            logger.error(f"Cannot convert to float: {payload}")
            return None
    
    def _start_reconnect_thread(self):
        """Start reconnection thread"""
        if self.reconnect_thread and self.reconnect_thread.is_alive():
            return
            
        if self.should_reconnect:
            self.reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
            self.reconnect_thread.start()
    
    def _reconnect_loop(self):
        """Reconnection loop with exponential backoff"""
        retry_delay = 5  # Start with 5 seconds
        max_delay = 300  # Maximum 5 minutes
        
        while self.should_reconnect and not self.is_connected:
            try:
                logger.info(f"Attempting to reconnect to MQTT broker in {retry_delay} seconds...")
                time.sleep(retry_delay)
                
                if not self.should_reconnect:
                    break
                
                # Attempt reconnection
                if self.client:
                    self.client.loop_stop()
                    self.client.disconnect()
                
                # Create new client instance
                self.client = mqtt.Client()
                self.client.on_connect = self._on_connect
                self.client.on_message = self._on_message
                self.client.on_disconnect = self._on_disconnect
                
                self.client.connect(self.config.MQTT_BROKER, self.config.MQTT_PORT, 60)
                self.client.loop_start()
                
                # Wait a bit to see if connection succeeds
                time.sleep(2)
                
                if not self.is_connected:
                    # Exponential backoff
                    retry_delay = min(retry_delay * 2, max_delay)
                else:
                    logger.info("MQTT reconnection successful")
                    break
                    
            except Exception as e:
                logger.error(f"Reconnection attempt failed: {e}")
                retry_delay = min(retry_delay * 2, max_delay)
    
    def publish(self, topic: str, payload: str, qos: int = 0):
        """Publish message to MQTT topic"""
        try:
            if self.client and self.is_connected:
                result = self.client.publish(topic, payload, qos)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    logger.debug(f"Published to {topic}: {payload}")
                    return True
                else:
                    logger.error(f"Failed to publish to {topic}: {result.rc}")
                    return False
            else:
                logger.warning("Cannot publish: MQTT not connected")
                return False
        except Exception as e:
            logger.error(f"Error publishing to {topic}: {e}")
            return False
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status"""
        return {
            "connected": self.is_connected,
            "broker": self.config.MQTT_BROKER,
            "port": self.config.MQTT_PORT,
            "subscribed_topics": self.subscribed_topics,
            "client_id": self.client._client_id.decode() if self.client else None
        }
    
    def test_connection(self) -> bool:
        """Test MQTT connection"""
        try:
            test_client = mqtt.Client()
            test_client.connect(self.config.MQTT_BROKER, self.config.MQTT_PORT, 10)
            test_client.disconnect()
            return True
        except Exception as e:
            logger.error(f"MQTT connection test failed: {e}")
            return False

# Example usage and testing
if __name__ == "__main__":
    # Mock config for testing
    class MockConfig:
        def __init__(self):
            self.MQTT_BROKER = "localhost"
            self.MQTT_PORT = 1883
            self.MQTT_TOPICS = {
                "dryer1": "esp32/dryer1/temp",
                "dryer2": "esp32/dryer2/temp", 
                "dryer3": "esp32/dryer3/temp",
                "kedi1": "esp32/kedi1/temp",
                "kedi2": "esp32/kedi2/temp",
                "kedi3": "esp32/kedi3/temp",
                "kedi4": "esp32/kedi4/temp",
                "boiler1": "esp32/boiler1/temp",
                "boiler2": "esp32/boiler2/temp",
                "humidity4": "esp32/humidity4"
            }
    
    def test_callback(parsed_data, topic):
        print(f"Received from {topic}: {parsed_data}")
    
    # Test the service
    config = MockConfig()
    mqtt_service = MQTTService(config, test_callback)
    
    # Test payload parsing
    print("Testing payload parsing:")
    print("=" * 40)
    
    test_payloads = [
        '{"temperature":28.5, "humidity":47.6}',
        '{"temperature":25.3}',
        '28.5',
        '{"humidity":60.2}',
        '{"pressure":1013.25}',
        '{"water_level":75.5}',
        'invalid_payload'
    ]
    
    for payload in test_payloads:
        result = mqtt_service._parse_payload(payload, "test/topic")
        print(f"'{payload}' -> {result}")