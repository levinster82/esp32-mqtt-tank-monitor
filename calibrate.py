"""
Tank Calibration Script
Save this as calibrate.py on your ESP32
Run when tank is empty to determine calibration offset
"""

from mqtt_tank_monitor import TankLevelMonitor
import time

def main():
    print("=" * 50)
    print("      TANK LEVEL CALIBRATION")
    print("=" * 50)
    print()
    print("IMPORTANT: Make sure your tank is COMPLETELY EMPTY")
    print("before running this calibration!")
    print()
    print("This will:")
    print("1. Take 10 distance measurements")
    print("2. Calculate the average")
    print("3. Tell you what CALIBRATION_OFFSET to use")
    print()
    
    # Wait for user confirmation
    try:
        input("Press Enter when tank is empty and you're ready...")
    except (EOFError, KeyboardInterrupt):
        # EOFError: input not available (non-interactive)
        # KeyboardInterrupt: user cancelled
        print("Waiting 5 seconds, then starting...")
        time.sleep(5)
    
    print()
    print("Starting calibration...")
    
    try:
        # Create monitor and run calibration
        monitor = TankLevelMonitor()
        print()
        monitor.calibrate_empty(num_readings=10)
        
        print()
        print("=" * 50)
        print("CALIBRATION COMPLETE!")
        print("=" * 50)
        print()
        print("Next steps:")
        print("1. The calibration has been automatically saved to config/config.json")
        print("2. Restart your ESP32 to use the new calibration")
        print("3. Test with known water levels to verify accuracy")
        print("4. If needed, you can manually edit config/config.json")
        
    except Exception as e:
        print("Calibration failed: {}".format(str(e)))
        print()
        print("Troubleshooting:")
        print("- Check sensor connections")
        print("- Make sure config/config.json exists and is configured")
        print("- Verify sensor is working with quick test")
        print("- Check that vl53l1x.py and config_manager.py are uploaded")

if __name__ == "__main__":
    main()