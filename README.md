# ESP32 MQTT Tank Level Monitor

Monitor liquid levels in tanks using an ESP32 and VL53L1X laser distance sensor. Automatically publishes data to Home Assistant via MQTT with auto-discovery support.

Perfect for monitoring heating oil tanks, water tanks, propane tanks, and other liquid storage systems.

## Features

- **Accurate Distance Measurement** - VL53L1X time-of-flight laser sensor (40mm to 4000mm range)
- **Home Assistant Integration** - MQTT auto-discovery with multiple sensor entities
- **Non-Linear Tank Support** - Accurate volume calculations for oval/irregular tank shapes
- **Secure Configuration** - Automatic password encryption using device MAC address
- **Ultra-Resilient Operation** - Watchdog timer, auto-reconnect, boot loop prevention
- **Easy Setup** - Interactive setup wizard and calibration script
- **MicroPython 1.25** - Optimized for ESP32 microcontrollers

## Hardware Requirements

| Component | Specification |
|-----------|--------------|
| **Microcontroller** | ESP32 development board |
| **Sensor** | VL53L1X Time-of-Flight distance sensor |
| **Power** | 5V via USB or external supply |
| **Network** | WiFi with MQTT broker (SSL required) |

### Wiring

| VL53L1X Pin | ESP32 Pin | Notes |
|-------------|-----------|-------|
| VCC | 3.3V | Do not use 5V |
| GND | GND | Common ground |
| SDA | GPIO 21 | Configurable in config.json |
| SCL | GPIO 22 | Configurable in config.json |

## Quick Start

### 1. Install MicroPython on ESP32

Download MicroPython 1.25 or later from [micropython.org](https://micropython.org/download/ESP32_GENERIC/) and flash to your ESP32:

```bash
esptool.py --port /dev/ttyUSB0 erase_flash
esptool.py --port /dev/ttyUSB0 write_flash -z 0x1000 esp32-micropython-1.25.bin
```

### 2. Upload Files to ESP32

Using [Thonny IDE](https://thonny.org/) (recommended for beginners):
1. Open Thonny
2. Select "MicroPython (ESP32)" as interpreter
3. Upload all `.py` files to the ESP32 root directory
4. Upload the `lib/` folder
5. Upload the `config/` folder

Or using `ampy` command-line tool:

```bash
# Install ampy
pip install adafruit-ampy

# Upload all files
ampy --port /dev/ttyUSB0 put boot.py
ampy --port /dev/ttyUSB0 put main.py
ampy --port /dev/ttyUSB0 put mqtt_tank_monitor.py
ampy --port /dev/ttyUSB0 put config_manager.py
ampy --port /dev/ttyUSB0 put tank_profiles.py
ampy --port /dev/ttyUSB0 put vl53l1x.py
ampy --port /dev/ttyUSB0 put setup.py
ampy --port /dev/ttyUSB0 put calibrate.py
ampy --port /dev/ttyUSB0 put lib
```

### 3. Configure Your System

**Option A: Interactive Setup (Recommended)**

1. Connect to ESP32 via serial console (Thonny or screen/minicom)
2. Run the setup wizard:
   ```python
   import setup
   setup.setup_wizard()
   ```
3. Follow the prompts to enter WiFi and MQTT credentials

**Option B: Manual Configuration**

1. Copy `config/config.json.template` to `config/config.json`
2. Edit `config/config.json` with your settings:
   ```json
   {
     "wifi": {
       "ssid": "YourWiFiNetwork",
       "password": "YourWiFiPassword"
     },
     "mqtt": {
       "broker": "192.168.1.100",
       "port": 8883,
       "username": "mqtt_user",
       "password": "mqtt_password",
       "ssl": true
     },
     "tank": {
       "height": 44,
       "profile": "275_vertical_oval"
     }
   }
   ```
3. Upload `config/config.json` to ESP32

**Note:** Passwords will be automatically encrypted on first boot using your ESP32's unique MAC address.

### 4. Calibrate Empty Tank

With your tank **completely empty**:

```python
import calibrate
calibrate.main()
```

This measures the distance when empty and calculates the calibration offset automatically.

### 5. Start Monitoring

Restart your ESP32. The system will automatically:
1. Connect to WiFi
2. Connect to MQTT broker
3. Send Home Assistant discovery messages
4. Begin publishing tank level data every 30 seconds

## Home Assistant Integration

### Automatic Discovery

The system automatically creates these entities in Home Assistant:

| Entity | Description | Unit |
|--------|-------------|------|
| **Tank Level** | Liquid depth in tank | inches |
| **Tank Level Percentage** | Percentage full | % |
| **Tank Volume** | Actual gallons (if using tank profile) | gallons |
| **Tank Distance Sensor** | Raw sensor reading | mm |
| **Tank Monitor WiFi Signal** | Signal strength | dBm |
| **Tank Monitor Memory** | ESP32 available RAM | bytes |

### Alert Automation Example

```yaml
automation:
  - alias: "Low Fuel Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.tank_monitor_level_percentage
        below: 20
    action:
      - service: notify.mobile_app
        data:
          message: "Tank level low: {{ states('sensor.tank_monitor_level_percentage') }}%"
```

## Tank Profiles

### Supported Tank Types

- **275_vertical_oval** - 275-gallon vertical oval oil tank (44" height)
- **linear** - Generic cylindrical/rectangular tank (linear calculation)

### Using Tank Profiles

Tank profiles provide accurate volume calculations for non-cylindrical tanks by using lookup tables that account for curved geometry.

Set in `config.json`:
```json
"tank": {
  "height": 44,
  "profile": "275_vertical_oval"
}
```

Use `"profile": "linear"` for cylindrical tanks or if you only need depth/percentage.

## Configuration Reference

### WiFi Settings

| Parameter | Description | Example |
|-----------|-------------|---------|
| `ssid` | Network name | `"MyNetwork"` |
| `password` | Network password (auto-encrypted) | `"MyPassword"` |

### MQTT Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| `broker` | MQTT broker IP address | `"192.168.1.100"` |
| `port` | MQTT port (SSL required) | `8883` |
| `username` | MQTT username | - |
| `password` | MQTT password (auto-encrypted) | - |
| `ssl` | Enable SSL/TLS | `true` (required) |

### Tank Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| `height` | Tank height in inches | `44` |
| `calibration_offset` | Calibration offset (auto-set) | `0.0` |
| `empty_level` | Minimum readable level | `0` |
| `profile` | Tank profile name | `"275_vertical_oval"` |

### Intervals

| Parameter | Description | Default |
|-----------|-------------|---------|
| `measurement` | Seconds between sensor readings | `5.0` |
| `publish` | Seconds between MQTT publishes | `30.0` |
| `wifi_check` | Seconds between WiFi checks | `300` |

### Hardware Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| `sda_pin` | I2C data pin | `21` |
| `scl_pin` | I2C clock pin | `22` |
| `i2c_freq` | I2C frequency | `400000` |

## Troubleshooting

### Sensor Not Found

**Error:** `VL53L1X sensor not found at address 0x29`

**Solutions:**
- Verify wiring (VCC to 3.3V, not 5V)
- Check I2C connections (SDA/SCL not swapped)
- Confirm pins match config.json settings
- Try I2C scan:
  ```python
  import machine
  i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21))
  print(i2c.scan())  # Should show [41] (0x29 in decimal)
  ```

### WiFi Connection Failed

**Error:** `WiFi connection failed after all retries`

**Solutions:**
- Verify SSID and password in config.json
- Check WiFi signal strength at ESP32 location
- Ensure 2.4GHz WiFi (ESP32 doesn't support 5GHz)
- Restart router if necessary

### MQTT Connection Failed

**Error:** `MQTT connection failed`

**Solutions:**
- Verify broker IP address is correct
- Check MQTT username and password
- Ensure broker is running and accessible
- Verify port 8883 is open for SSL/TLS
- Check MQTT broker supports SSL (required)
- Test MQTT broker with another client

### SSL Errors

**Error:** `SSL module not available`

**Solutions:**
- Use MicroPython firmware with SSL support
- Ensure you flashed the correct ESP32 firmware
- Some minimal MicroPython builds exclude SSL

### Password Encryption Errors

**Error:** `Device MAC unavailable - encryption failed`

**Solutions:**
- Ensure WiFi hardware is initialized (happens automatically in boot.py)
- Check network module is available
- Restart ESP32

### System Keeps Restarting

**Cause:** Boot loop prevention or watchdog resets

**Solutions:**
- Check sensor connections (consecutive failures trigger restart)
- Verify WiFi and MQTT are accessible
- Review serial console for error messages
- System waits 60s between restarts to prevent rapid boot loops

### Inaccurate Readings

**Solutions:**
- Run calibration again with empty tank
- Verify tank height in config.json is correct
- Check sensor is mounted securely
- Ensure nothing obstructs sensor view
- Select correct tank profile

## Recovery Mode

If the application fails to start after 3 attempts, the system enters **Recovery Mode** with REPL access.

Available commands:
```python
restart()      # Restart ESP32
test_sensor()  # Basic sensor test
check_files()  # List files on ESP32
help()         # Show recovery mode help
```

## Advanced Usage

### Manual Testing

```python
# Test configuration loading
from config_manager import ConfigManager
config = ConfigManager()

# Test sensor reading
from mqtt_tank_monitor import TankLevelMonitor
monitor = TankLevelMonitor()
reading = monitor.read_tank_level()
print(reading)

# Test tank profile calculations
from tank_profiles import depth_to_gallons, TANK_275_VERTICAL_OVAL
gallons = depth_to_gallons(22.0, TANK_275_VERTICAL_OVAL)
print("22 inches = {} gallons".format(gallons))
```

### Watchdog Timer

The system includes a 120-second watchdog timer that automatically resets the ESP32 if it hangs. The watchdog is fed throughout normal operations but will trigger if:
- WiFi connection hangs
- MQTT operations freeze
- Sensor reading blocks indefinitely

### Changing Measurement Frequency

Edit `config.json`:
```json
"intervals": {
  "measurement": 10.0,
  "publish": 60.0
}
```

Lower values provide more frequent updates but use more power and network bandwidth.

## Security Notes

- **Password Encryption**: WiFi and MQTT passwords are automatically encrypted using the ESP32's unique MAC address
- **SSL/TLS Required**: MQTT connections must use SSL (enforced by configuration validation)
- **Config Protection**: Encrypted passwords are device-specific and cannot be decrypted on other devices
- **No Plaintext Storage**: Passwords are automatically migrated to encrypted format on first boot

## Project Structure

```
esp32_mqtt_tank_monitor/
├── boot.py                    # Boot configuration (runs first)
├── main.py                    # Main entry point with watchdog
├── mqtt_tank_monitor.py       # Core monitoring application
├── config_manager.py          # Configuration with encryption
├── tank_profiles.py           # Tank volume lookup tables
├── vl53l1x.py                 # Sensor driver
├── setup.py                   # Interactive setup wizard
├── calibrate.py               # Calibration utility
├── lib/
│   └── umqtt/
│       ├── __init__.py
│       └── simple.py          # MQTT client library
└── config/
    ├── config.json.template   # Configuration template
    └── config.json            # Your configuration (create from template)
```
