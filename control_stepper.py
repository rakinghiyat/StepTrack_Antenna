import json
import os
import time
import threading
from pywinusb import hid
import serial

# Konfigurasi serial Arduino
arduino = serial.Serial('COM5', 115200)
print("Terhubung ke Arduino...")

# File untuk menyimpan data bearing
JSON_FILE = 'bearing.json'
ENCODER_JSON = 'raw_to_bearing.json'

# Variabel kontrol
knob_direction = 0
last_knob_event = time.time()
knob_speed_delay = 0.01
TIMEOUT = 0.2

# Bearing dan step
bearing = 0
step_count = 0
steps_per_click = 1.8 / 4  # 0.45 derajat per step dengan microstep 4
lock = threading.Lock()
stop_event = threading.Event()

# Map raw AS5600 ke bearing
raw_to_bearing = {}

def normalize_bearing(b):
    b = b % 360
    return b if b >= 0 else b + 360

def save_bearing_to_file(bearing, step_count):
    with open(JSON_FILE, 'w') as f:
        json.dump({'bearing': bearing, 'step_count': step_count}, f)
    print(f"Bearing disimpan: {bearing:.2f}°")

def load_bearing_from_file():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, 'r') as f:
            try:
                data = json.load(f)
                return float(data.get('bearing', 0)), int(data.get('step_count', 0))
            except:
                pass
    return 0.0, 0

def load_raw_map():
    global raw_to_bearing
    if os.path.exists(ENCODER_JSON):
        with open(ENCODER_JSON, 'r') as f:
            try:
                raw_to_bearing = json.load(f)
            except:
                raw_to_bearing = {}
    else:
        raw_to_bearing = {}

def save_raw_map():
    with open(ENCODER_JSON, 'w') as f:
        json.dump(raw_to_bearing, f, indent=2)
        print("Peta RAW-Bearing disimpan.")

# Load data bearing sebelumnya
initial_bearing, step_count = load_bearing_from_file()
bearing = normalize_bearing(initial_bearing)
print(f"Memuat bearing terakhir: {bearing:.2f}°")

# Load data raw map
load_raw_map()

# Kirim step count awal ke Arduino
arduino.write(f"S{step_count}\n".encode())

# Fungsi membaca raw data dari Arduino
def read_from_arduino():
    global bearing
    while not stop_event.is_set():
        try:
            line = arduino.readline().decode('utf-8').strip()
            if line.startswith("RAW:"):
                raw_value = int(line.split(":")[1].strip())
                with lock:
                    if str(raw_value) not in raw_to_bearing:
                        raw_to_bearing[str(raw_value)] = round(bearing, 2)
                        print(f"[SAVE] RAW: {raw_value} -> Bearing: {bearing:.2f}°")
                        save_raw_map()
                    else:
                        print(f"[SKIP] RAW {raw_value} sudah ada.")
        except Exception as e:
            print(f"Error membaca serial: {e}")

# Fungsi utama untuk mengontrol motor berdasarkan knob
def stepper_driver_loop():
    global knob_direction, knob_speed_delay, step_count, bearing
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
                step_count += 1
                bearing = normalize_bearing(step_count * steps_per_click)
                save_bearing_to_file(bearing, step_count)
        elif dir == -1:
            arduino.write(b'L')
            with lock:
                step_count -= 1
                bearing = normalize_bearing(step_count * steps_per_click)
                save_bearing_to_file(bearing, step_count)

        if dir != 0:
            print(f"Bearing: {bearing:.2f}°")

        time.sleep(delay)

# Fungsi input manual bearing
def manual_input_loop():
    global step_count, bearing
    while not stop_event.is_set():
        try:
            target = input("Masukkan target bearing (0–359): ")
            if stop_event.is_set():
                break
            target = int(target)
            if not (0 <= target < 360):
                print("Masukkan antara 0–359.")
                continue

            with lock:
                current_bearing = normalize_bearing(step_count * steps_per_click)
                delta = (target - current_bearing + 540) % 360 - 180
                steps_needed = int(round(delta / steps_per_click))
                direction = 'R' if steps_needed > 0 else 'L'

                for _ in range(abs(steps_needed)):
                    arduino.write(direction.encode())
                    step_count += 1 if direction == 'R' else -1
                    bearing = normalize_bearing(step_count * steps_per_click)
                    save_bearing_to_file(bearing, step_count)
                    time.sleep(0.005)

                print(f"Posisi kini: {bearing:.2f}°")

        except ValueError:
            print("Input tidak valid. Harap masukkan angka 0–359.")
        except EOFError:
            stop_event.set()

# Fungsi untuk handle input dari knob PowerMate
last_event_time = time.time()

def knob_handler(data):
    global knob_direction, last_knob_event, knob_speed_delay, last_event_time, step_count, bearing

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
            step_count = 0
            save_bearing_to_file(bearing, step_count)
            print("Bearing di-reset ke 0°")
            last_knob_event = time.time()

# Setup PowerMate HID
all_devices = hid.HidDeviceFilter().get_devices()
powermate = next((dev for dev in all_devices if "Griffin PowerMate" in dev.product_name), None)

# Main loop
if not powermate:
    print("PowerMate tidak ditemukan.")
else:
    print("PowerMate ditemukan, memulai listener...")
    powermate.open()
    powermate.set_raw_data_handler(knob_handler)

    # Start semua thread
    t1 = threading.Thread(target=stepper_driver_loop, daemon=True)
    t2 = threading.Thread(target=manual_input_loop, daemon=True)
    t3 = threading.Thread(target=read_from_arduino, daemon=True)
    t1.start()
    t2.start()
    t3.start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nProgram dihentikan.")
        stop_event.set()
        time.sleep(0.5)
    finally:
        powermate.close()
        arduino.close()
