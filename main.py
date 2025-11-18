# main.py - Ultra-resilient version with automatic restart
# This runs automatically after boot.py
# MicroPython 1.25 Compatible Version with Integrated Watchdog

import machine
import time
import sys

def watchdog_timer():
    """Setup watchdog timer for automatic recovery"""
    try:
        # ESP32 watchdog timer - resets system if hanging
        wdt = machine.WDT(timeout=120000)  # 120 second timeout (increased for resilience)
        return wdt
    except (AttributeError, OSError, ValueError) as e:
        # AttributeError: WDT not supported on this hardware
        # OSError: watchdog initialization failed
        # ValueError: invalid timeout value
        print("Watchdog not available: {}".format(str(e)))
        return None

def main_application():
    """Run the main tank monitoring application with watchdog integration"""
    try:
        print("Loading tank monitor...")
        
        # Create watchdog timer
        wdt = watchdog_timer()
        if wdt:
            wdt.feed()
            print("Watchdog timer active (120s timeout)")
        
        # Import your tank monitor (delay import to handle missing files)
        from mqtt_tank_monitor import TankLevelMonitor
        
        if wdt:
            wdt.feed()
        
        print("Creating monitor instance...")
        monitor = TankLevelMonitor()
        
        # Pass watchdog to the monitor for continuous feeding
        monitor.wdt = wdt
        if wdt:
            wdt.feed()
        
        print("Starting monitoring loop...")
        monitor.monitor_loop()
        
    except ImportError as e:
        print("Import error: {}".format(str(e)))
        print("Required files missing - check vl53l1x.py, mqtt config")
        return False
    except Exception as e:
        print("Application error: {}".format(str(e)))
        return False
    
    return True

def recovery_mode():
    """Simple recovery mode with basic functionality"""
    print("="*40)
    print("RECOVERY MODE ACTIVE")
    print("="*40)
    print("Main application failed to start")
    print("Available commands:")
    print("- help() - Show this message")
    print("- restart() - Restart ESP32")
    print("- test_sensor() - Basic sensor test")
    print("- check_files() - List files")
    print("="*40)
    
    def restart():
        print("Restarting ESP32...")
        machine.reset()
    
    def test_sensor():
        try:
            import machine
            from vl53l1x import VL53L1X
            i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21), freq=400000)
            sensor = VL53L1X(i2c)
            distance = sensor.read()
            print("Sensor reading: {} mm".format(distance))
        except Exception as e:
            print("Sensor test failed: {}".format(str(e)))
    
    def check_files():
        import os
        print("Files on ESP32:")
        for file in os.listdir():
            print("  {}".format(file))
    
    def help():
        recovery_mode()
    
    # Make functions available in REPL
    globals()['restart'] = restart
    globals()['test_sensor'] = test_sensor
    globals()['check_files'] = check_files
    globals()['help'] = help

def safe_main():
    """Main function with comprehensive error handling"""
    print("="*40)
    print("Tank Monitor Starting...")
    print("="*40)
    
    retry_count = 0
    max_retries = 3
    
    while retry_count < max_retries:
        try:
            print("Attempt {}/{}".format(retry_count + 1, max_retries))
            
            if main_application():
                print("Application ended normally")
                break
            else:
                print("Application failed, retrying...")
                retry_count += 1
                time.sleep(10)  # Wait before retry
                
        except KeyboardInterrupt:
            print("\nApplication stopped by user (Ctrl+C)")
            break
        except Exception as e:
            print("Unexpected error: {}".format(str(e)))
            retry_count += 1
            if retry_count < max_retries:
                print("Retrying in 10 seconds... ({}/{})".format(
                    retry_count, max_retries))
                time.sleep(10)
    
    if retry_count >= max_retries:
        print("Max retries ({}) reached - entering recovery mode".format(
            max_retries))
        recovery_mode()
    
    print("Entering REPL mode...")

# Auto-run check - only run if this is the main execution
if __name__ == "__main__":
    safe_main()
else:
    # If imported, just define functions but don't auto-run
    pass

# Note: Removed duplicate safe_main() call that was unreachable
# The system will start automatically when main.py is executed