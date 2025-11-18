"""
Setup Script for ESP32 Tank Monitor
Run this script to configure your tank monitoring system
MicroPython 1.25 Compatible
"""

import json
import os
from config_manager import create_default_config, ConfigManager, ConfigError

def setup_wizard():
    """Interactive setup wizard for first-time configuration"""
    print("=" * 60)
    print("     ESP32 TANK MONITOR - SETUP WIZARD")
    print("=" * 60)
    print()
    print("This wizard will help you configure your tank monitor.")
    print("You'll need:")
    print("- WiFi network name and password")
    print("- MQTT broker IP address and credentials")
    print("- Tank height measurement")
    print()

    try:
        # Check if config already exists
        if os.path.exists("config/config.json"):
            print("Configuration file already exists.")
            response = input_with_fallback("Do you want to overwrite it? (y/n): ", "n")
            if response.lower() != 'y':
                print("Setup cancelled.")
                return False

        # Create default config from template
        if not create_default_config():
            print("Failed to create configuration file.")
            return False

        # Load the config for editing
        with open("config/config.json", 'r') as f:
            config = json.load(f)

        print("\n--- WiFi Configuration ---")
        ssid = input_with_fallback("WiFi Network Name (SSID): ", "")
        if not ssid:
            print("WiFi SSID is required!")
            return False

        password = input_with_fallback("WiFi Password: ", "")
        if not password:
            print("WiFi password is required!")
            return False

        config['wifi']['ssid'] = ssid
        config['wifi']['password'] = password

        print("\n--- MQTT Configuration ---")

        # Validate MQTT broker IP
        while True:
            broker = input_with_fallback("MQTT Broker IP Address: ", "192.168.1.100")
            if validate_ip_address(broker):
                break
            print("ERROR: Invalid IP address format. Please use format: 192.168.1.100")

        # Validate MQTT port
        while True:
            port_str = input_with_fallback("MQTT Port (8883 for SSL): ", "8883")
            if validate_port(port_str):
                port = port_str
                break
            print("ERROR: Invalid port number. Must be between 1 and 65535")

        username = input_with_fallback("MQTT Username: ", "")
        mqtt_password = input_with_fallback("MQTT Password: ", "")

        print("\n--- SSL Configuration ---")
        print("SSL is REQUIRED for MQTT connections.")
        ssl_insecure = input_with_fallback("Allow insecure SSL (skip cert verification)? (y/n): ", "n")
        ssl_insecure_bool = ssl_insecure.lower() == 'y'
        if ssl_insecure_bool:
            print("WARNING: SSL certificate verification will be disabled")

        if not username or not mqtt_password:
            print("MQTT credentials are required!")
            return False

        config['mqtt']['broker'] = broker
        config['mqtt']['port'] = int(port)
        config['mqtt']['username'] = username
        config['mqtt']['password'] = mqtt_password
        config['mqtt']['ssl'] = True
        config['mqtt']['ssl_insecure'] = ssl_insecure_bool

        print("\n--- Tank Configuration ---")

        # Validate tank height
        while True:
            height_str = input_with_fallback("Tank Height (inches): ", "44")
            try:
                height = float(height_str)
                if height > 0 and height <= 1000:  # Reasonable max
                    break
                print("ERROR: Tank height must be between 0 and 1000 inches")
            except ValueError:
                print("ERROR: Invalid number format")

        config['tank']['height'] = height

        print("\n--- Hardware Configuration ---")

        # Validate SDA pin
        while True:
            sda_pin_str = input_with_fallback("I2C SDA Pin (21): ", "21")
            if validate_pin(sda_pin_str):
                sda_pin = int(sda_pin_str)
                break
            print("ERROR: Invalid GPIO pin. Common pins: 21, 22, 23, 25, 26, 27, 32, 33")

        # Validate SCL pin
        while True:
            scl_pin_str = input_with_fallback("I2C SCL Pin (22): ", "22")
            if validate_pin(scl_pin_str):
                scl_pin = int(scl_pin_str)
                if scl_pin != sda_pin:
                    break
                print("ERROR: SCL pin must be different from SDA pin")
            else:
                print("ERROR: Invalid GPIO pin. Common pins: 21, 22, 23, 25, 26, 27, 32, 33")

        config['hardware']['sda_pin'] = sda_pin
        config['hardware']['scl_pin'] = scl_pin

        # Save updated configuration
        with open("config/config.json", 'w') as f:
            f.write(json.dumps(config))

        print("\n" + "=" * 60)
        print("     CONFIGURATION SAVED!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Upload all files to your ESP32")
        print("2. Run calibrate.py when tank is empty")
        print("3. Restart ESP32 to begin monitoring")
        print()
        print("Configuration saved to: config/config.json")

        return True

    except Exception as e:
        print("Setup failed: {}".format(str(e)))
        return False

def input_with_fallback(prompt, default):
    """Get user input with fallback for MicroPython compatibility"""
    try:
        response = input(prompt)
        return response if response.strip() else default
    except (EOFError, KeyboardInterrupt):
        # EOFError: input() not available (non-interactive mode)
        # KeyboardInterrupt: user cancelled
        print("{} (using default: {})".format(prompt, str(default)))
        return default

def validate_ip_address(ip_str):
    """Validate IP address format (basic validation for MicroPython)"""
    try:
        parts = ip_str.split('.')
        if len(parts) != 4:
            return False
        for part in parts:
            num = int(part)
            if num < 0 or num > 255:
                return False
        return True
    except:
        return False

def validate_port(port_str):
    """Validate port number"""
    try:
        port = int(port_str)
        return 1 <= port <= 65535
    except:
        return False

def validate_pin(pin_str):
    """Validate GPIO pin number for ESP32"""
    try:
        pin = int(pin_str)
        # ESP32 valid GPIO pins (common ones)
        valid_pins = [0, 1, 2, 3, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33, 34, 35, 36, 39]
        return pin in valid_pins
    except:
        return False

def test_configuration():
    """Test the current configuration"""
    print("=" * 60)
    print("     CONFIGURATION TEST")
    print("=" * 60)

    try:
        config = ConfigManager()
        print("✓ Configuration loaded successfully")

        # Test WiFi config
        wifi_config = config.get_wifi_config()
        print("✓ WiFi SSID: {}".format(wifi_config['ssid']))

        # Test MQTT config
        mqtt_config = config.get_mqtt_config()
        print("✓ MQTT Broker: {}".format(mqtt_config['broker']))
        print("✓ MQTT Username: {}".format(mqtt_config['username']))

        # Test tank config
        tank_config = config.get_tank_config()
        print("✓ Tank Height: {} inches".format(tank_config['height']))

        # Test hardware config
        hw_config = config.get_hardware_config()
        print("✓ I2C Pins: SDA={}, SCL={}".format(hw_config['sda_pin'], hw_config['scl_pin']))

        print("\nConfiguration test PASSED!")
        return True

    except ConfigError as e:
        print("Configuration error: {}".format(str(e)))
        return False
    except Exception as e:
        print("Test failed: {}".format(str(e)))
        return False

def show_current_config():
    """Display current configuration"""
    try:
        with open("config/config.json", 'r') as f:
            config = json.load(f)

        print("=" * 60)
        print("     CURRENT CONFIGURATION")
        print("=" * 60)

        print("\nWiFi:")
        print("  SSID: {}".format(config['wifi']['ssid']))
        print("  Password: {}".format("*" * len(config['wifi']['password'])))

        print("\nMQTT:")
        print("  Broker: {}".format(config['mqtt']['broker']))
        print("  Port: {}".format(config['mqtt']['port']))
        print("  Username: {}".format(config['mqtt']['username']))
        print("  Password: {}".format("*" * len(config['mqtt']['password'])))
        print("  SSL: {}".format(config['mqtt'].get('ssl', True)))
        print("  SSL Insecure: {}".format(config['mqtt'].get('ssl_insecure', False)))

        print("\nTank:")
        print("  Height: {} inches".format(config['tank']['height']))
        print("  Calibration Offset: {}".format(config['tank']['calibration_offset']))

        print("\nHardware:")
        print("  SDA Pin: {}".format(config['hardware']['sda_pin']))
        print("  SCL Pin: {}".format(config['hardware']['scl_pin']))

    except Exception as e:
        print("Failed to show configuration: {}".format(str(e)))

def main():
    """Main setup function"""
    print("ESP32 Tank Monitor Setup")
    print("1. Run setup wizard")
    print("2. Test configuration")
    print("3. Show current configuration")
    print("4. Exit")

    choice = input_with_fallback("Choose option (1-4): ", "1")

    if choice == "1":
        setup_wizard()
    elif choice == "2":
        test_configuration()
    elif choice == "3":
        show_current_config()
    else:
        print("Exiting setup.")

if __name__ == "__main__":
    main()