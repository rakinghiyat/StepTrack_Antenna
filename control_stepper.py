import time
import threading
import json
import os
from pywinusb import hid
import serial

# Konfigurasi serial Arduino
arduino = serial.Serial('COM5', 115200)
print("Terhubung ke Arduino...")

# File kalibrasi
CALIBRATION_FILE = "calibration.json"

# Variabel global
knob_direction = 0
last_knob_event = time.time()
knob_speed_delay = 0.01
TIMEOUT = 0.2

bearing = 0
steps_per_click = 1.8 / 4  # 0.45° per step
lock = threading.Lock()
stop_event = threading.Event()

last_raw_value = None
last_angle_deg = None

calibration_data = {}

def normalize_bearing(b):
    b = b % 360
    return b if b >= 0 else b + 360

def save_calibration_data(last_bearing, last_raw):
    slope = 4096 / 360.0
    bearing_raw_map = {str(deg): int(round(deg * slope)) for deg in range(0, 360)}
    data = {
        "last_bearing": last_bearing,
        "last_raw": last_raw,
        "bearing_raw_map": bearing_raw_map
    }
    with open(CALIBRATION_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    print("File kalibrasi disimpan.")

def load_calibration_data():
    with open(CALIBRATION_FILE, 'r') as f:
        return json.load(f)

def initial_calibration():
    global bearing, calibration_data

    try:
        print("Menunggu data dari Arduino untuk kalibrasi awal...")
        while True:
            line = arduino.readline().decode('utf-8').strip()
            if line.startswith("Raw Angle:"):
                current_raw = int(line.split(" | ")[0].split(":")[1].strip())
                break

        if not os.path.exists(CALIBRATION_FILE):
            print("File kalibrasi tidak ditemukan. Membuat file baru...")
            # Gunakan raw sekarang dan anggap bearing saat ini adalah 0°
            last_bearing = 0
            last_raw = current_raw
            save_calibration_data(last_bearing, last_raw)
            calibration_data = load_calibration_data()
        else:
            print("Membaca file kalibrasi...")
            calibration_data = load_calibration_data()

        target_raw = calibration_data["last_raw"]
        delta_raw = target_raw - current_raw

        # AS5600 12-bit: 4096 = 360°
        degrees_per_raw = 360.0 / 4096
        raw_per_step = steps_per_click / degrees_per_raw
        steps_needed = int(round(delta_raw / raw_per_step))

        direction = 'R' if steps_needed > 0 else 'L'
        for _ in range(abs(steps_needed)):
            arduino.write(direction.encode())
            time.sleep(0.005)

        # Setelah motor sudah selesai bergerak
        bearing = calibration_data["last_bearing"]
        print(f"Kalibrasi awal selesai. Disinkronkan ke RAW: {target_raw}, bearing dilanjutkan dari: {bearing:.2f}°")


    except Exception as e:
        print(f"Kesalahan saat kalibrasi awal: {e}")

def read_from_arduino():
    global last_raw_value, last_angle_deg
    while not stop_event.is_set():
        try:
            line = arduino.readline().decode('utf-8').strip()
            if line.startswith("Raw Angle:"):
                parts = line.split(" | ")
                raw_value = int(parts[0].split(":")[1].strip())
                angle_deg = float(parts[1].split(":")[1].strip())
                if raw_value != last_raw_value or angle_deg != last_angle_deg:
                    last_raw_value = raw_value
                    last_angle_deg = angle_deg
                    print(f"Bearing AS5600: {bearing:.2f}° -> RAW angle diterima: {raw_value}")
        except Exception as e:
            print(f"Error membaca serial: {e}")

def stepper_driver_loop():
    global knob_direction, knob_speed_delay, bearing
    while not stop_event.is_set():
        now = time.time()
        with lock:
            if now - last_knob_event > TIMEOUT:
                knob_direction = 0
            dir = knob_direction
            delay = knob_speed_delay

        if dir == 1:
            arduino.write(b'R')
            with lock:
                bearing += steps_per_click
                bearing = normalize_bearing(bearing)
        elif dir == -1:
            arduino.write(b'L')
            with lock:
                bearing -= steps_per_click
                bearing = normalize_bearing(bearing)

        if dir != 0:
            print(f"Bearing AS5600: {bearing:.2f}°")
        time.sleep(delay)

def manual_input_loop():
    global bearing
    while not stop_event.is_set():
        try:
            target = input("Masukkan target bearing (0–359): ")
            if stop_event.is_set():
                break
            target = int(target)
            if not (0 <= target < 360):
                print("Masukkan antara 0–359.")
                continue

            # Menghitung perbedaan dan menggerakkan motor
            delta = (target - bearing + 540) % 360 - 180
            steps_needed = int(round(delta / steps_per_click))
            direction = 'R' if steps_needed > 0 else 'L'

            for _ in range(abs(steps_needed)):
                arduino.write(direction.encode())
                bearing += steps_per_click if direction == 'R' else -steps_per_click
                bearing = normalize_bearing(bearing)
                time.sleep(0.005)

            print(f"Posisi kini: {bearing:.2f}°")

        except ValueError:
            print("Input tidak valid. Harap masukkan angka 0–359.")
        except EOFError:
            stop_event.set()

last_event_time = time.time()

def knob_handler(data):
    global knob_direction, last_knob_event, knob_speed_delay, last_event_time, bearing
    delta = data[2]
    button = data[1]
    now = time.time()
    time_diff = now - last_event_time
    last_event_time = now

    if time_diff > 0:
        speed = 1.0 / time_diff
        knob_speed_delay = max(0.0005, min(0.02, 0.05 / speed))

    with lock:
        if delta == 1:
            knob_direction = 1
        elif delta == 255:
            knob_direction = -1
        last_knob_event = now

    if button == 1:
        arduino.write(b'C')
        with lock:
            knob_direction = 0
            bearing = 0
            print("Bearing di-reset ke 0°")
            last_knob_event = time.time()

# Setup PowerMate HID
all_devices = hid.HidDeviceFilter().get_devices()
powermate = next((dev for dev in all_devices if "Griffin PowerMate" in dev.product_name), None)

# Main program
if not powermate:
    print("PowerMate tidak ditemukan.")
else:
    print("PowerMate ditemukan, memulai listener...")
    powermate.open()
    powermate.set_raw_data_handler(knob_handler)

    initial_calibration()

    # Start semua thread
    threading.Thread(target=stepper_driver_loop, daemon=True).start()
    threading.Thread(target=manual_input_loop, daemon=True).start()
    threading.Thread(target=read_from_arduino, daemon=True).start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nProgram dihentikan.")
        stop_event.set()
        time.sleep(0.5)
    finally:
        if last_raw_value is not None:
            save_calibration_data(bearing, last_raw_value)
            print(f"Data terakhir disimpan ke file kalibrasi: Bearing {bearing:.2f}°, Raw {last_raw_value}")
        powermate.close()
        arduino.close()
