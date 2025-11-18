"""
Configuration Manager for ESP32 Tank Monitor
Handles secure loading and validation of configuration data
MicroPython 1.25 Compatible

Copyright (C) 2025
SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import os
import gc
import ubinascii
import network

class ConfigError(Exception):
    """Configuration related errors"""
    pass

class ConfigManager:
    """Manages secure configuration loading and validation"""

    def __init__(self, config_path="config/config.json"):
        self.config_path = config_path
        self.config_template_path = "config/config.json.template"
        self.config = None
        self._device_mac = None
        self._load_config()

    def _load_config(self):
        """Load configuration from file with fallback to template"""
        try:
            # Try to load the actual config file
            if self._file_exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    self.config = json.load(f)
                    print("Configuration loaded from {}".format(self.config_path))
            else:
                # Config file doesn't exist, check for template
                if self._file_exists(self.config_template_path):
                    print("Config file not found. Please:")
                    print("1. Copy config/config.json.template to config/config.json")
                    print("2. Edit config/config.json with your credentials")
                    print("3. Restart the system")
                    raise ConfigError("Configuration file missing - see template")
                else:
                    raise ConfigError("No configuration files found")

            # Validate loaded configuration
            self._validate_config()

            # Auto-migrate plaintext passwords to encrypted format
            self._migrate_plaintext_passwords()

            gc.collect()  # Clean up after JSON parsing

        except (OSError, ValueError) as e:
            raise ConfigError("Failed to load configuration: " + str(e))

    def _file_exists(self, path):
        """Check if file exists (MicroPython compatible)"""
        try:
            with open(path, 'r'):
                pass
            return True
        except OSError:
            return False

    def _get_device_mac(self):
        """Get device MAC address for encryption key - strict mode"""
        if self._device_mac is None:
            try:
                mac = ubinascii.hexlify(network.WLAN().config('mac')).decode()
                self._device_mac = mac
                print("Device MAC acquired for secure encryption: {}...".format(mac[:6]))
            except Exception as e:
                print("=" * 60)
                print("ENCRYPTION ERROR: Cannot access device MAC address")
                print("=" * 60)
                print("Reason: {}".format(str(e)))
                print("")
                print("TROUBLESHOOTING:")
                print("1. Ensure WiFi hardware is properly initialized")
                print("2. Check that network module is available")
                print("3. Restart the ESP32 device")
                print("4. Verify MicroPython firmware supports network.WLAN()")
                print("")
                print("SECURITY NOTICE:")
                print("This system requires device-specific encryption.")
                print("Cannot proceed without valid MAC address.")
                print("=" * 60)
                raise ConfigError("Device MAC unavailable - encryption failed. See troubleshooting above.")
        return self._device_mac

    def _encrypt_password(self, password):
        """Encrypt password using device MAC as key"""
        if not password:
            return ""

        mac_key = self._get_device_mac()  # Will fail completely if MAC unavailable
        encrypted = bytearray()

        for i, char in enumerate(password):
            key_char = mac_key[i % len(mac_key)]
            encrypted.append(ord(char) ^ ord(key_char))

        # Base64 encode for JSON storage with prefix to indicate encryption method
        encrypted_b64 = ubinascii.b2a_base64(encrypted).decode().strip()
        return "mac_xor:" + encrypted_b64

    def _decrypt_password(self, encrypted_value):
        """Decrypt password using device MAC as key - strict mode"""
        if not encrypted_value:
            return ""

        # Check if it's MAC-encrypted
        if not encrypted_value.startswith("mac_xor:"):
            raise ConfigError("Invalid encryption format. Expected 'mac_xor:' prefix.")

        encrypted_b64 = encrypted_value[8:]  # Remove "mac_xor:" prefix
        mac_key = self._get_device_mac()  # Will fail completely if MAC unavailable

        try:
            encrypted = ubinascii.a2b_base64(encrypted_b64)
        except Exception as e:
            print("DECRYPTION ERROR: Invalid Base64 data")
            print("This may indicate:")
            print("- Corrupted configuration file")
            print("- Wrong encryption method")
            print("- File tampering")
            raise ConfigError("Password decryption failed - invalid data format")

        decrypted = ""
        for i, byte in enumerate(encrypted):
            key_char = mac_key[i % len(mac_key)]
            decrypted += chr(byte ^ ord(key_char))

        return decrypted

    def _migrate_plaintext_passwords(self):
        """Auto-migrate plaintext passwords to encrypted format"""
        config_changed = False

        # Check WiFi password
        if 'wifi' in self.config and 'password' in self.config['wifi']:
            plaintext_password = self.config['wifi']['password']
            if plaintext_password and not plaintext_password.startswith('mac_xor:'):
                print("Migrating WiFi password to encrypted format...")
                encrypted_password = self._encrypt_password(plaintext_password)
                self.config['wifi']['password'] = encrypted_password
                config_changed = True

        # Check MQTT password
        if 'mqtt' in self.config and 'password' in self.config['mqtt']:
            plaintext_password = self.config['mqtt']['password']
            if plaintext_password and not plaintext_password.startswith('mac_xor:'):
                print("Migrating MQTT password to encrypted format...")
                encrypted_password = self._encrypt_password(plaintext_password)
                self.config['mqtt']['password'] = encrypted_password
                config_changed = True

        # Save updated configuration if passwords were migrated
        if config_changed:
            print("Saving configuration with encrypted passwords...")
            self._save_config()
            print("✓ Password migration completed successfully")

    def _validate_config(self):
        """Validate configuration structure and required fields"""
        if not isinstance(self.config, dict):
            raise ConfigError("Configuration must be a JSON object")

        # Required top-level sections
        required_sections = ['wifi', 'mqtt', 'tank', 'hardware']
        for section in required_sections:
            if section not in self.config:
                raise ConfigError("Missing required section: " + section)

        # Validate WiFi configuration
        wifi = self.config['wifi']
        if not wifi.get('ssid') or wifi['ssid'] == "YOUR_WIFI_SSID":
            raise ConfigError("WiFi SSID not configured")
        if not wifi.get('password') or wifi['password'] == "YOUR_WIFI_PASSWORD":
            raise ConfigError("WiFi password not configured")

        # Validate MQTT configuration
        mqtt = self.config['mqtt']
        if not mqtt.get('broker'):
            raise ConfigError("MQTT broker not configured")
        # Check for template placeholder values
        if mqtt['broker'] == "mqtt.example.com" or mqtt['broker'] == "your.mqtt.broker":
            raise ConfigError("MQTT broker still has placeholder value - update config.json")
        if not mqtt.get('username'):
            raise ConfigError("MQTT username not configured")
        if not mqtt.get('password') or mqtt['password'] == "YOUR_MQTT_PASSWORD":
            raise ConfigError("MQTT password not configured")

        # Validate SSL configuration
        ssl_enabled = mqtt.get('ssl', True)
        if not ssl_enabled:
            raise ConfigError("SSL is required for MQTT connections - set 'ssl': true")

        # Validate port for SSL
        port = mqtt.get('port', 8883)
        if ssl_enabled and port == 1883:
            print("WARNING: Using SSL with port 1883 - consider using port 8883 for SSL MQTT")

        # Validate tank configuration
        tank = self.config['tank']
        if not isinstance(tank.get('height'), (int, float)) or tank['height'] <= 0:
            raise ConfigError("Tank height must be a positive number")

        # Validate hardware configuration
        hardware = self.config['hardware']
        required_pins = ['sda_pin', 'scl_pin']
        for pin in required_pins:
            if not isinstance(hardware.get(pin), int):
                raise ConfigError("Hardware pin " + pin + " must be an integer")

        print("Configuration validation successful")

    def get(self, section, key=None, default=None):
        """Get configuration value"""
        if not self.config:
            raise ConfigError("Configuration not loaded")

        if key is None:
            # Return entire section
            return self.config.get(section, default)
        else:
            # Return specific key from section
            section_data = self.config.get(section, {})
            return section_data.get(key, default)

    def get_wifi_config(self):
        """Get WiFi configuration with decrypted password"""
        encrypted_password = self.get('wifi', 'password')
        return {
            'ssid': self.get('wifi', 'ssid'),
            'password': self._decrypt_password(encrypted_password)
        }

    def get_mqtt_config(self):
        """Get MQTT configuration with decrypted password"""
        encrypted_password = self.get('mqtt', 'password')
        return {
            'broker': self.get('mqtt', 'broker'),
            'port': self.get('mqtt', 'port', 8883),
            'username': self.get('mqtt', 'username'),
            'password': self._decrypt_password(encrypted_password),
            'client_id_prefix': self.get('mqtt', 'client_id_prefix', 'tank_monitor'),
            'ssl': self.get('mqtt', 'ssl', True)
        }

    def get_tank_config(self):
        """Get tank configuration"""
        return {
            'height': self.get('tank', 'height'),
            'calibration_offset': self.get('tank', 'calibration_offset', 0.0),
            'empty_level': self.get('tank', 'empty_level', 0)
        }

    def get_thresholds(self):
        """Get alert thresholds"""
        return {
            'low_level': self.get('thresholds', 'low_level', 10.0),
            'high_level': self.get('thresholds', 'high_level', 95.0)
        }

    def get_intervals(self):
        """Get timing intervals"""
        return {
            'measurement': self.get('intervals', 'measurement', 5.0),
            'publish': self.get('intervals', 'publish', 30.0),
            'wifi_check': self.get('intervals', 'wifi_check', 300)
        }

    def get_hardware_config(self):
        """Get hardware configuration"""
        return {
            'sda_pin': self.get('hardware', 'sda_pin'),
            'scl_pin': self.get('hardware', 'scl_pin'),
            'i2c_freq': self.get('hardware', 'i2c_freq', 400000)
        }

    def update_calibration_offset(self, offset):
        """Update calibration offset and save to file"""
        try:
            if not self.config:
                raise ConfigError("Configuration not loaded")

            # Update in-memory configuration
            if 'tank' not in self.config:
                self.config['tank'] = {}
            self.config['tank']['calibration_offset'] = float(offset)

            # Save updated configuration
            self._save_config()
            print("Calibration offset updated: {}".format(offset))

        except Exception as e:
            raise ConfigError("Failed to update calibration: " + str(e))

    def _save_config(self):
        """Save current configuration to file"""
        try:
            # Use json.dumps() for MicroPython compatibility
            json_str = json.dumps(self.config)
            with open(self.config_path, 'w') as f:
                f.write(json_str)
            print("Configuration saved to {}".format(self.config_path))
        except (OSError, ValueError) as e:
            raise ConfigError("Failed to save configuration: " + str(e))

def create_default_config():
    """Create a default configuration file from template"""
    try:
        template_path = "config/config.json.template"
        config_path = "config/config.json"

        if not ConfigManager()._file_exists(template_path):
            print("Template file not found: {}".format(template_path))
            return False

        # Copy template to config file
        with open(template_path, 'r') as template:
            content = template.read()

        with open(config_path, 'w') as config:
            config.write(content)

        print("Default configuration created: {}".format(config_path))
        print("Please edit this file with your actual credentials")
        return True

    except Exception as e:
        print("Failed to create default config: {}".format(str(e)))
        return False

# Test function for development
def test_config():
    """Test configuration loading and validation"""
    try:
        config = ConfigManager()
        print("WiFi Config:", config.get_wifi_config())
        print("MQTT Config:", config.get_mqtt_config())
        print("Tank Config:", config.get_tank_config())
        print("Configuration test successful!")
        return True
    except ConfigError as e:
        print("Configuration error: {}".format(str(e)))
        return False

if __name__ == "__main__":
    test_config()