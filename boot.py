# boot.py - Tank Monitor Boot Configuration
# Upload this file to the root directory of your ESP32
# This runs automatically BEFORE main.py on every boot
# MicroPython 1.25 Compatible Version

import esp
import gc
import machine
import network
import time

# Disable ESP32 debug output (reduces noise in console)
esp.osdebug(None)

# Enable automatic garbage collection
gc.enable()

print("=" * 50)
print("ESP32 Tank Monitor - Boot Sequence")
print("=" * 50)
import sys
print("MicroPython version: {}".format(str(sys.version)))
print("Free memory: {} bytes".format(gc.mem_free()))
print("Boot reason: {}".format(machine.reset_cause()))

# Optional: Set CPU frequency to save power
# Default is 240MHz, you can reduce to 160MHz or 80MHz
# machine.freq(160000000)  # 160MHz (uncomment to enable)

# Disable WiFi access point mode (saves power)
ap = network.WLAN(network.AP_IF)
ap.active(False)
print("✓ WiFi AP mode disabled")

# Pre-configure WiFi station mode (doesn't connect yet)
sta = network.WLAN(network.STA_IF)
sta.active(True)
print("✓ WiFi station mode enabled")

# Optional: Configure power management
# machine.lightsleep()  # Enable light sleep mode for power saving

# Brief delay for hardware stabilization
print("Hardware stabilization delay...")
time.sleep(2)

print("✓ Boot sequence completed")
print("Starting main application...")
print("=" * 50)

# Collect garbage before main.py starts
gc.collect()
print("Free memory after boot: {} bytes".format(gc.mem_free()))

# main.py will run automatically after this file finishes