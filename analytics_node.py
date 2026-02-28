"""
Cold-Chain Monitoring System - Analytics Node (simulates Jetson Nano)
Reads serial data from Arduino, applies moving average filter,
computes risk level, and publishes via MQTT.

Team 21 - CS131 IoT
"""

import serial
import json
import time
from collections import deque

# ===== CONFIGURATION =====
SERIAL_PORT = "COM3"
BAUD_RATE = 9600
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "coldchain/data"

# Risk thresholds
TEMP_HIGH = 25
TEMP_MED = 25.0

# Moving average filter window
FILTER_SIZE = 5

# ===== STATE =====
temp_buffer = deque(maxlen=FILTER_SIZE)
use_mqtt = False
mqtt_client = None

# ===== MQTT SETUP =====
try:
    import paho.mqtt.client as mqtt
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    use_mqtt = True
    print("[MQTT] Connected to broker at {}:{}".format(MQTT_BROKER, MQTT_PORT))
except Exception as e:
    print("[MQTT] Could not connect: {}".format(e))
    print("[MQTT] Continuing without MQTT. Install Mosquitto to enable.")

# ===== FUNCTIONS =====
def moving_average(buffer):
    """Calculate moving average of values in buffer."""
    if len(buffer) == 0:
        return 0.0
    return sum(buffer) / len(buffer)

def compute_risk(temp):
    """Compute risk level based on temperature."""
    if temp > TEMP_HIGH:
        return "HIGH"
    elif temp > TEMP_MED:
        return "MEDIUM"
    else:
        return "LOW"

# ===== MAIN LOOP =====
def main():
    print("=" * 50)
    print("Cold-Chain Analytics Node (Jetson Nano Simulator)")
    print("=" * 50)
    print("Reading from serial port: {}".format(SERIAL_PORT))
    print("Risk thresholds: HIGH > {}C, MEDIUM > {}C".format(TEMP_HIGH, TEMP_MED))
    print("")

    # Open serial connection
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
        print("[SERIAL] Connected to Arduino on {}".format(SERIAL_PORT))
    except Exception as e:
        print("[SERIAL] ERROR: Could not open {}: {}".format(SERIAL_PORT, e))
        print("Make sure Arduino is plugged in and serial monitor is CLOSED.")
        return

    time.sleep(2)  # Wait for Arduino to reset

    while True:
        try:
            # Read a line from Arduino
            line = ser.readline().decode("utf-8").strip()
            if not line:
                continue

            # Parse JSON
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue  # Skip bad lines

            # Check for error messages
            if "error" in data:
                print("[SENSOR] Error: {}".format(data["error"]))
                continue

            # Get sensor values
            temp = data.get("temp", -999)
            light = data.get("light", 0)
            door = data.get("door", 0)

            if temp == -999:
                continue

            # Apply moving average filter
            temp_buffer.append(temp)
            filtered_temp = round(moving_average(temp_buffer), 1)

            # Compute risk level
            risk = compute_risk(filtered_temp)

            # Build processed data
            processed = {
                "temp_raw": temp,
                "temp_filtered": filtered_temp,
                "light": light,
                "door": door,
                "risk": risk,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            # Print to console
            risk_symbol = {"LOW": "✓", "MEDIUM": "⚠", "HIGH": "🔴"}
            print("[{}] Temp: {}C (raw: {}C) | Light: {} | Door: {} | Risk: {} {}".format(
                processed["timestamp"],
                filtered_temp, temp,
                light,
                "OPEN" if door else "CLOSED",
                risk,
                risk_symbol.get(risk, "")
            ))

            # Publish to MQTT
            if use_mqtt and mqtt_client:
                mqtt_client.publish(MQTT_TOPIC, json.dumps(processed))

        except KeyboardInterrupt:
            print("\nShutting down...")
            break
        except Exception as e:
            print("[ERROR] {}".format(e))
            time.sleep(1)

    # Cleanup
    ser.close()
    if use_mqtt and mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    print("Analytics node stopped.")

if __name__ == "__main__":
    main()