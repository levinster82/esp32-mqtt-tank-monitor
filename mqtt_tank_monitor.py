"""
Tank Level Monitor with MQTT and Home Assistant Integration
MicroPython implementation for ESP32 - MicroPython 1.25 COMPATIBLE
Ultra-Resilient Version with Integrated Watchdog Support

Copyright (C) 2025

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import machine
import time
import network
import json
import gc
import sys
import ubinascii

# Constants
VL53L1X_I2C_ADDRESS = 0x29
SENSOR_MIN_READING_MM = 0
SENSOR_MAX_READING_MM = 8000  # Reasonable max range for VL53L1X
MM_TO_INCHES = 25.4
MQTT_KEEPALIVE_SEC = 60
MQTT_CONNECT_TIMEOUT_SEC = 10
MAX_CONSECUTIVE_FAILURES = 10
RESTART_COOLDOWN_SEC = 60
OFFLINE_STATUS_DELAY_SEC = 0.5

# Try to import MQTT library with fallback
try:
    from umqtt.simple import MQTTClient
    MQTT_AVAILABLE = True
except ImportError:
    print("Warning: umqtt.simple not available - install with: import upip; upip.install('micropython-umqtt.simple')")
    MQTT_AVAILABLE = False

# Try to import sensor driver
try:
    from vl53l1x import VL53L1X
    SENSOR_AVAILABLE = True
except ImportError:
    print("Warning: vl53l1x.py not found - upload the sensor driver file")
    SENSOR_AVAILABLE = False

# Try to import configuration manager
try:
    from config_manager import ConfigManager, ConfigError
    CONFIG_AVAILABLE = True
except ImportError:
    print("Warning: config_manager.py not found - using fallback configuration")
    CONFIG_AVAILABLE = False
    ConfigError = Exception

# Try to import tank profiles for non-linear calculations
try:
    from tank_profiles import depth_to_gallons, get_tank_profile, TANK_275_VERTICAL_OVAL
    TANK_PROFILES_AVAILABLE = True
except ImportError:
    print("Warning: tank_profiles.py not found - using linear calculation")
    TANK_PROFILES_AVAILABLE = False

# Generate unique client ID based on MAC address
def get_client_id(prefix="tank_monitor"):
    """
    Generate unique MQTT client ID based on device MAC address

    Args:
        prefix: Client ID prefix (default: "tank_monitor")

    Returns:
        str: Unique client ID in format "prefix_XXXXXX" where X is last 6 MAC chars
    """
    mac = ubinascii.hexlify(network.WLAN().config('mac')).decode()
    return prefix + "_" + mac[-6:]

class TankLevelMonitor:
    def __init__(self):
        """Initialize tank monitor with MQTT support"""
        self.wifi = None
        self.mqtt = None
        self.sensor = None
        self.last_publish = 0
        self.last_wifi_check = 0
        self.wifi_retry_count = 0
        self.mqtt_retry_count = 0
        self.wdt = None  # Watchdog will be set by main.py
        self.shutdown_requested = False  # Flag for graceful shutdown
        self.tank_profile = None  # Tank profile for non-linear calculations

        # Load configuration
        self.config = self._load_configuration()

        # Load tank profile if available
        self._load_tank_profile()

        # Generate device identifiers
        self.client_id = get_client_id(self.config.get_mqtt_config().get('client_id_prefix', 'tank_monitor'))
        self.device_id = self.client_id
        self.mqtt_base_topic = "homeassistant/sensor/" + self.device_id
        self.mqtt_state_topic = self.mqtt_base_topic + "/state"

        # Check dependencies
        if not SENSOR_AVAILABLE:
            raise RuntimeError("Sensor driver not available")
        if not MQTT_AVAILABLE:
            raise RuntimeError("MQTT library not available")
        if not CONFIG_AVAILABLE:
            raise RuntimeError("Configuration manager not available")
        
        # Initialize hardware
        self.init_hardware()
        
        # Connect to WiFi
        self.connect_wifi()
        
        # Initialize MQTT
        self.init_mqtt()
        
        # Send Home Assistant discovery config
        self.send_ha_discovery()
        
        print("Tank Monitor with MQTT ready!")
    
    def feed_watchdog(self):
        """Feed the watchdog timer if available"""
        try:
            if hasattr(self, 'wdt') and self.wdt:
                self.wdt.feed()
        except (AttributeError, OSError) as e:
            # Watchdog feeding failed - log but don't crash
            # AttributeError: wdt object issue
            # OSError: watchdog hardware error
            pass
    
    def _load_configuration(self):
        """Load and validate configuration"""
        try:
            config = ConfigManager()
            print("Configuration loaded successfully")
            return config
        except ConfigError as e:
            print("Configuration error: {}".format(str(e)))
            raise RuntimeError("Failed to load configuration: " + str(e))

    def _load_tank_profile(self):
        """Load tank profile for non-linear volume calculations"""
        if not TANK_PROFILES_AVAILABLE:
            print("Tank profiles not available - using linear calculation")
            return

        # Get tank type from config (default to 275 gallon vertical oval)
        tank_type = self.config.get('tank', 'profile', '275_vertical_oval')

        if tank_type == 'linear':
            print("Using linear tank calculation (configured)")
            self.tank_profile = None
            return

        # Load the profile
        profile = get_tank_profile(tank_type)
        if profile:
            self.tank_profile = profile
            print("Loaded tank profile: {}".format(profile['name']))
            print("  Capacity: {} gallons, Height: {} inches".format(
                profile['capacity_gallons'], profile['height_inches']))
        else:
            print("Warning: Tank profile '{}' not found - using linear calculation".format(tank_type))
            self.tank_profile = None
    
    def init_hardware(self):
        """
        Initialize I2C bus and VL53L1X sensor

        Scans I2C bus for devices and initializes the VL53L1X sensor at address 0x29.
        Uses pin configuration from config file.

        Raises:
            RuntimeError: If sensor not found at expected address or I2C initialization fails
        """
        print("Initializing hardware...")
        self.feed_watchdog()
        
        try:
            # Get hardware configuration
            hw_config = self.config.get_hardware_config()

            # Initialize I2C
            self.i2c = machine.I2C(0,
                                 scl=machine.Pin(hw_config['scl_pin']),
                                 sda=machine.Pin(hw_config['sda_pin']),
                                 freq=hw_config['i2c_freq'])
            
            # Scan for devices
            devices = self.i2c.scan()
            device_list = [hex(addr) for addr in devices]
            print("I2C devices found: {}".format(device_list))

            if VL53L1X_I2C_ADDRESS not in devices:
                raise RuntimeError("VL53L1X sensor not found at address {}".format(hex(VL53L1X_I2C_ADDRESS)))

            # Initialize sensor
            self.sensor = VL53L1X(self.i2c, address=VL53L1X_I2C_ADDRESS)
            print("Sensor initialized")
            self.feed_watchdog()
            
        except Exception as e:
            print("Hardware initialization failed: {}".format(str(e)))
            raise
    
    def connect_wifi(self, max_retries=3):
        """
        Connect to WiFi network with automatic retry

        Args:
            max_retries: Maximum number of connection attempts (default: 3)

        Returns:
            bool: True if connected successfully, False if all attempts failed

        Note:
            Each attempt has a 30-second timeout. Feeds watchdog during connection.
        """
        print("Connecting to WiFi...")
        self.wifi = network.WLAN(network.STA_IF)
        self.wifi.active(True)
        self.feed_watchdog()
        
        for attempt in range(max_retries):
            if self.wifi.isconnected():
                ip = self.wifi.ifconfig()[0]
                print("Already connected: {}".format(ip))
                return True
            
            print("Attempt {}/{}".format(attempt + 1, max_retries))

            # Get WiFi configuration
            wifi_config = self.config.get_wifi_config()
            self.wifi.connect(wifi_config['ssid'], wifi_config['password'])
            
            # Wait for connection with timeout
            timeout = 30
            while not self.wifi.isconnected() and timeout > 0:
                time.sleep(1)
                timeout -= 1
                self.feed_watchdog()  # Feed watchdog during WiFi connection
                if timeout % 5 == 0:
                    print("  Waiting... {}s left".format(timeout))
            
            if self.wifi.isconnected():
                ip = self.wifi.ifconfig()[0]
                print("Connected to WiFi: {}".format(ip))
                self.feed_watchdog()
                return True
            else:
                print("WiFi connection failed (attempt {})".format(attempt + 1))
                time.sleep(5)
                self.feed_watchdog()
        
        # If we get here, all attempts failed
        print("WiFi connection failed after all retries")
        print("Possible issues:")
        print("  - Wrong SSID or password")
        print("  - WiFi network not available")
        print("  - ESP32 WiFi hardware issue")
        return False
    
    def check_wifi_connection(self):
        """Check WiFi connection and reconnect if needed"""
        current_time = time.time()
        wifi_check_interval = self.config.get_intervals()['wifi_check']
        if (current_time - self.last_wifi_check) < wifi_check_interval:
            return True  # Too soon to check again
        
        self.last_wifi_check = current_time
        self.feed_watchdog()
        
        if not self.wifi.isconnected():
            print("WiFi disconnected, attempting reconnect...")
            if self.connect_wifi(max_retries=2):
                # Reinitialize MQTT after WiFi reconnection
                self.init_mqtt()
                return True
            else:
                print("WiFi reconnection failed")
                return False
        return True
    
    def init_mqtt(self):
        """Initialize MQTT client with error handling"""
        print("Initializing MQTT...")
        self.feed_watchdog()
        
        try:
            # Disconnect existing connection if any
            if self.mqtt:
                try:
                    self.mqtt.disconnect()
                except (OSError, AttributeError):
                    # OSError: connection already closed
                    # AttributeError: MQTT object invalid
                    pass
            
            # Get MQTT configuration
            mqtt_config = self.config.get_mqtt_config()

            # Create new MQTT client with SSL support
            ssl_enabled = mqtt_config.get('ssl', True)

            if ssl_enabled:
                try:
                    import ssl
                    print("SSL encryption enabled (transport encryption only)")
                    ssl_context = True
                except ImportError:
                    raise RuntimeError("SSL module not available - required for secure MQTT")
            else:
                ssl_context = None

            self.mqtt = MQTTClient(
                self.client_id,
                mqtt_config['broker'],
                port=mqtt_config['port'],
                user=mqtt_config['username'] if mqtt_config['username'] else None,
                password=mqtt_config['password'] if mqtt_config['password'] else None,
                keepalive=MQTT_KEEPALIVE_SEC,
                ssl=ssl_context
            )

            # Connect with timeout
            self.mqtt.connect(clean_session=True, timeout=MQTT_CONNECT_TIMEOUT_SEC)
            print("Connected to MQTT broker at {}".format(mqtt_config['broker']))
            self.mqtt_retry_count = 0
            self.feed_watchdog()
            return True
            
        except Exception as e:
            print("MQTT connection failed: {}".format(str(e)))
            self.mqtt_retry_count += 1
            return False
    
    def send_ha_discovery(self):
        """Send Home Assistant MQTT Discovery configuration"""
        print("Sending Home Assistant discovery config...")
        self.feed_watchdog()
        
        device_info = {
            "identifiers": [self.device_id],
            "name": "Tank Level Monitor",
            "model": "ESP32 VL53L1X",
            "manufacturer": "DIY"
        }

        # Create sensor configs with optimized string formatting and shared device_info
        base_config = {
            "state_topic": self.mqtt_state_topic,
            "device": device_info
        }

        configs = [
            ("Tank Level", "{}_level_inches".format(self.device_id),
             "{{ value_json.level_inches | round(2) }}", "in", "distance", "mdi:water-level"),
            ("Tank Level Percentage", "{}_level_percentage".format(self.device_id),
             "{{ value_json.level_percentage | round(1) }}", "%", None, "mdi:water-percent"),
            ("Tank Distance Sensor", "{}_distance_mm".format(self.device_id),
             "{{ value_json.distance_mm | round(0) }}", "mm", "distance", "mdi:ruler"),
            ("Tank Monitor Memory", "{}_free_memory".format(self.device_id),
             "{{ value_json.free_memory | round(0) }}", "bytes", None, "mdi:memory"),
            ("Tank Monitor WiFi Signal", "{}_wifi_rssi".format(self.device_id),
             "{{ value_json.wifi_rssi }}", "dBm", "signal_strength", "mdi:wifi")
        ]

        # Add gallons sensor if using non-linear tank profile
        if self.tank_profile:
            configs.append(
                ("Tank Volume", "{}_gallons".format(self.device_id),
                 "{{ value_json.gallons | round(1) }}", "gal", "volume", "mdi:gauge")
            )

        # Publish discovery configs
        try:
            for name, unique_id, value_template, unit, device_class, icon in configs:
                config = base_config.copy()
                config.update({
                    "name": name,
                    "unique_id": unique_id,
                    "value_template": value_template,
                    "unit_of_measurement": unit,
                    "icon": icon
                })
                if device_class:
                    config["device_class"] = device_class

                topic = "homeassistant/sensor/{}/config".format(unique_id)
                self.mqtt.publish(topic, json.dumps(config), retain=True)
                self.feed_watchdog()
            print("Home Assistant discovery sent")
        except Exception as e:
            print("Discovery config failed: {}".format(str(e)))
    
    def read_tank_level(self):
        """
        Read current tank level from sensor and calculate fill percentage

        Performs the following steps:
        1. Reads distance from VL53L1X sensor (in mm)
        2. Validates reading is within acceptable range
        3. Converts to inches and calculates water level
        4. Applies calibration offset
        5. Calculates percentage full

        Returns:
            dict or None: Dictionary with keys:
                - distance_mm: Raw sensor reading in millimeters
                - distance_inches: Distance in inches
                - level_inches: Calculated water level
                - level_percentage: Tank fill percentage (0-100)
                - timestamp: Reading timestamp
            Returns None if sensor read fails or reading invalid
        """
        try:
            self.feed_watchdog()
            distance_mm = self.sensor.read()
            
            # Validate sensor reading
            if distance_mm is None:
                print("Sensor returned None")
                return None

            if distance_mm <= SENSOR_MIN_READING_MM or distance_mm > SENSOR_MAX_READING_MM:
                print("Invalid sensor reading: {} mm (valid range: {}-{})".format(
                    distance_mm, SENSOR_MIN_READING_MM, SENSOR_MAX_READING_MM))
                return None

            # Get tank configuration
            tank_config = self.config.get_tank_config()
            tank_height = tank_config['height']
            calibration_offset = tank_config['calibration_offset']
            empty_level = tank_config['empty_level']

            # Convert distance to inches
            distance_inches = distance_mm / MM_TO_INCHES

            # Calculate liquid depth (distance from top to surface)
            liquid_depth = tank_height - distance_inches + calibration_offset

            # Constrain depth to valid range
            liquid_depth = max(empty_level, min(liquid_depth, tank_height))

            # Calculate volume using tank profile or linear method
            if self.tank_profile:
                # Use non-linear lookup table
                gallons = depth_to_gallons(liquid_depth, self.tank_profile)
                tank_capacity = self.tank_profile['capacity_gallons']

                # Calculate percentage based on actual capacity
                if tank_capacity > 0:
                    percentage = (gallons / tank_capacity) * 100.0
                else:
                    percentage = 0.0
            else:
                # Use linear calculation (legacy method)
                tank_level = liquid_depth
                gallons = None  # Not calculated in linear mode

                # Calculate percentage (avoid division by zero)
                if tank_height > 0:
                    percentage = (tank_level / tank_height) * 100.0
                else:
                    percentage = 0.0
            
            # Build response dictionary
            response = {
                'distance_mm': round(distance_mm, 1),
                'distance_inches': round(distance_inches, 2),
                'level_inches': round(liquid_depth, 2),
                'level_percentage': round(percentage, 1),
                'timestamp': time.time()
            }

            # Add gallons if using non-linear calculation
            if gallons is not None:
                response['gallons'] = round(gallons, 1)

            return response
            
        except Exception as e:
            print("Sensor read error: {}".format(str(e)))
            return None
    
    def publish_data(self, reading):
        """Publish data to MQTT with error handling"""
        if reading is None or not self.mqtt:
            return False
        
        try:
            self.feed_watchdog()
            
            # Add additional metadata using .update() method (MicroPython 1.25 compatible)
            payload = {}
            payload.update(reading)
            payload['tank_height'] = self.config.get_tank_config()['height']
            payload['device_id'] = self.device_id
            payload['alerts'] = self.get_alerts(reading)
            
            # Add system info
            try:
                # WiFi signal strength
                if self.wifi and self.wifi.isconnected():
                    payload['wifi_rssi'] = self.wifi.status('rssi')

                # Free memory
                payload['free_memory'] = gc.mem_free()
            except (OSError, AttributeError, ValueError):
                # OSError: WiFi error
                # AttributeError: object not initialized
                # ValueError: invalid status parameter
                pass  # System info not critical
            
            # Publish to MQTT
            json_payload = json.dumps(payload)
            self.mqtt.publish(self.mqtt_state_topic, json_payload)
            
            print("Published: {}in ({}%)".format(
                reading['level_inches'], reading['level_percentage']))
            self.feed_watchdog()
            return True
            
        except Exception as e:
            print("MQTT publish error: {}".format(str(e)))
            return False
    
    def get_alerts(self, reading):
        """Get current alerts"""
        alerts = []
        percentage = reading['level_percentage']
        level = reading['level_inches']

        # Get thresholds from configuration
        thresholds = self.config.get_thresholds()
        tank_height = self.config.get_tank_config()['height']

        if percentage < thresholds['low_level']:
            alerts.append("low_level")
        if percentage > thresholds['high_level']:
            alerts.append("high_level")
        if level <= 0:
            alerts.append("empty")
        if level >= tank_height - 1:
            alerts.append("full")

        return alerts

    def shutdown(self):
        """
        Gracefully shutdown the tank monitor

        Performs clean shutdown sequence:
        1. Sets shutdown_requested flag
        2. Publishes offline status to MQTT
        3. Disconnects MQTT client
        4. Disconnects and deactivates WiFi

        This method is called automatically on KeyboardInterrupt or exceptions.
        """
        print("Initiating graceful shutdown...")
        self.shutdown_requested = True

        # Disconnect MQTT
        if self.mqtt:
            try:
                # Send offline status
                offline_payload = json.dumps({
                    'status': 'offline',
                    'timestamp': time.time()
                })
                self.mqtt.publish(self.mqtt_state_topic, offline_payload)
                time.sleep(OFFLINE_STATUS_DELAY_SEC)  # Brief delay for message delivery

                self.mqtt.disconnect()
                print("MQTT disconnected cleanly")
            except (OSError, AttributeError) as e:
                print("MQTT disconnect error: {}".format(str(e)))

        # Disconnect WiFi
        if self.wifi:
            try:
                self.wifi.disconnect()
                self.wifi.active(False)
                print("WiFi disconnected")
            except (OSError, AttributeError) as e:
                print("WiFi disconnect error: {}".format(str(e)))

        print("Shutdown complete")

    def calibrate_empty(self, num_readings=10):
        """Calibrate empty tank reading"""
        print("Starting empty tank calibration...")
        print("Taking " + str(num_readings) + " distance measurements...")

        readings = []
        for i in range(num_readings):
            try:
                self.feed_watchdog()
                distance = self.sensor.read()
                if distance is not None and distance > 0:
                    readings.append(distance)
                    print("Reading " + str(i + 1) + ": " + str(distance) + "mm")
                else:
                    print("Invalid reading " + str(i + 1) + ", skipping...")
                time.sleep(1)
            except Exception as e:
                print("Error during reading " + str(i + 1) + ": " + str(e))

        if len(readings) < num_readings // 2:
            print("Too few valid readings for calibration")
            return False

        # Calculate average distance in inches
        avg_distance_mm = sum(readings) / len(readings)
        avg_distance_inches = avg_distance_mm / 25.4

        # Calculate calibration offset
        tank_height = self.config.get_tank_config()['height']
        calibration_offset = tank_height - avg_distance_inches

        print("\nCalibration Results:")
        print("Average distance: " + str(round(avg_distance_mm, 1)) + "mm (" + str(round(avg_distance_inches, 2)) + "in)")
        print("Tank height: " + str(tank_height) + "in")
        print("Calculated CALIBRATION_OFFSET: " + str(round(calibration_offset, 2)))

        try:
            # Update configuration with new offset
            self.config.update_calibration_offset(calibration_offset)
            print("\nCalibration saved successfully!")
            return True
        except Exception as e:
            print("Failed to save calibration: " + str(e))
            return False

    def monitor_loop(self):
        """Main monitoring loop with comprehensive error handling and watchdog support"""
        # Get configuration intervals
        intervals = self.config.get_intervals()
        measurement_interval = intervals['measurement']
        publish_interval = intervals['publish']

        print("Starting tank monitoring with MQTT...")
        print("Device ID: {}".format(self.device_id))
        print("Measurement interval: {}s".format(measurement_interval))
        print("Publish interval: {}s".format(publish_interval))
        
        # Show watchdog status
        if hasattr(self, 'wdt') and self.wdt:
            print("Watchdog protection: ACTIVE")
        else:
            print("Watchdog protection: DISABLED")
            
        print("Press Ctrl+C to stop")
        print("-" * 60)
        
        consecutive_failures = 0
        last_restart_time = 0

        try:
            while True:
                # Check for shutdown request
                if self.shutdown_requested:
                    print("Shutdown requested, exiting monitor loop...")
                    break

                # Feed watchdog at the start of each loop iteration
                self.feed_watchdog()

                # Periodic garbage collection
                gc.collect()
                
                # Check WiFi connection periodically
                if not self.check_wifi_connection():
                    consecutive_failures += 1
                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        current_time = time.time()
                        time_since_last_restart = current_time - last_restart_time
                        if time_since_last_restart < RESTART_COOLDOWN_SEC:
                            wait_time = RESTART_COOLDOWN_SEC - time_since_last_restart
                            print("Cooldown active - waiting {}s before restart to prevent boot loop".format(int(wait_time)))
                            time.sleep(wait_time)
                        print("Too many consecutive failures - restarting...")
                        machine.reset()
                    time.sleep(measurement_interval)
                    continue
                
                # Read sensor
                reading = self.read_tank_level()
                
                if reading:
                    consecutive_failures = 0  # Reset failure counter
                    
                    # Always print locally
                    print("Level: {}in ({}%) | Distance: {}mm | Free mem: {}".format(
                        reading['level_inches'], reading['level_percentage'],
                        reading['distance_mm'], gc.mem_free()))
                    
                    # Publish to MQTT if it's time
                    current_time = time.time()
                    if (current_time - self.last_publish) >= publish_interval:
                        if self.publish_data(reading):
                            self.last_publish = current_time
                        else:
                            # Try to reconnect MQTT if publish failed
                            if self.init_mqtt():
                                # Retry publish once
                                if self.publish_data(reading):
                                    self.last_publish = current_time
                else:
                    consecutive_failures += 1
                    print("Sensor read failed ({}/{})".format(
                        consecutive_failures, MAX_CONSECUTIVE_FAILURES))

                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        current_time = time.time()
                        time_since_last_restart = current_time - last_restart_time
                        if time_since_last_restart < RESTART_COOLDOWN_SEC:
                            wait_time = RESTART_COOLDOWN_SEC - time_since_last_restart
                            print("Cooldown active - waiting {}s before restart to prevent boot loop".format(int(wait_time)))
                            time.sleep(wait_time)
                        print("Too many sensor failures - restarting...")
                        machine.reset()
                
                # Feed watchdog before sleep
                self.feed_watchdog()
                time.sleep(measurement_interval)
                
        except KeyboardInterrupt:
            print("\nKeyboard interrupt detected...")
            self.shutdown()
        except Exception as e:
            print("Monitor error: {}".format(str(e)))
            self.shutdown()
            print("Restarting in 10 seconds...")
            time.sleep(10)
            machine.reset()
        finally:
            # Ensure clean shutdown if not already done
            if not self.shutdown_requested:
                self.shutdown()

def main():
    """Main function with comprehensive error checking"""
    print("=== Tank Level Monitor with MQTT ===")

    # Pre-flight checks
    if not SENSOR_AVAILABLE:
        print("Error: Sensor driver not available")
        print("Solution: Upload vl53l1x.py to your ESP32")
        return

    if not MQTT_AVAILABLE:
        print("Error: MQTT library not available")
        print("Solution: Run 'import upip; upip.install(\"micropython-umqtt.simple\")'")
        return

    if not CONFIG_AVAILABLE:
        print("Error: Configuration manager not available")
        print("Solution: Upload config_manager.py to your ESP32")
        return
    
    try:
        monitor = TankLevelMonitor()
        monitor.monitor_loop()
        
    except Exception as e:
        print("Fatal error: {}".format(str(e)))
        print("")
        print("Troubleshooting checklist:")
        print("1. Check WiFi credentials in script")
        print("2. Verify MQTT broker IP and credentials")
        print("3. Ensure sensor connections are correct:")
        print("   - VCC to 3.3V, GND to GND")
        print("   - SDA to GPIO 21, SCL to GPIO 22 (default pins)")
        print("   - Check config/config.json for actual pin configuration")
        print("4. Verify vl53l1x.py is uploaded")
        print("5. Check Home Assistant MQTT integration")

if __name__ == "__main__":
    main()
