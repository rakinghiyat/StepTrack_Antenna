from pywinusb import hid
import serial
import threading
import time

# --- Konfigurasi Serial dan Variabel ---
arduino = serial.Serial('COM3', 115200)
print("Terhubung ke Arduino...")

knob_direction = 0
last_knob_event = time.time()
knob_speed_delay = 0.01
lock = threading.Lock()
TIMEOUT = 0.2

# --- Variabel bearing ---
bearing = 0
step_count = 0
steps_per_click = 1.8 / 4  # 1.8° per step, microstep = 4 → 0.45°

def normalize_bearing(b):
    b = b % 360
    return b if b >= 0 else b + 360

# --- Fungsi driver untuk kontrol motor berdasarkan knob ---
def stepper_driver_loop():
    global knob_direction, knob_speed_delay, step_count, bearing
    while True:
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
        elif dir == -1:
            arduino.write(b'L')
            with lock:
                step_count -= 1
                bearing = normalize_bearing(step_count * steps_per_click)

        if dir != 0:
            print(f"Bearing: {bearing:.2f}°")

        time.sleep(delay)

# --- Fungsi input manual dari terminal ---
def manual_input_loop():
    global step_count, bearing
    while True:
        try:
            target = int(input("Masukkan target bearing (0–359): "))
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
                    time.sleep(0.005)

                bearing = normalize_bearing(step_count * steps_per_click)
                print(f"Posisi kini: {bearing:.2f}°")
        except ValueError:
            print("Input tidak valid. Harap masukkan angka 0–359.")

# --- Fungsi handler dari knob PowerMate ---
last_event_time = time.time()

def knob_handler(data):
    global knob_direction, last_knob_event, knob_speed_delay, last_event_time

    delta = data[2]
    button = data[1]
    now = time.time()
    time_diff = now - last_event_time
    last_event_time = now

    if time_diff > 0:
        speed = 1.0 / time_diff
        min_delay = 0.0005
        max_delay = 0.02
        sensitivity = 0.05
        knob_speed_delay = max(min_delay, min(max_delay, sensitivity / speed))

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
            print("Bearing di-reset ke 0°")
            last_knob_event = time.time()

# --- Deteksi PowerMate ---
all_devices = hid.HidDeviceFilter().get_devices()
powermate = None
for device in all_devices:
    if "Griffin PowerMate" in device.product_name:
        powermate = device
        break

# --- Jalankan program utama ---
if not powermate:
    print("PowerMate tidak ditemukan.")
else:
    print("PowerMate ditemukan, memulai listener...")
    powermate.open()
    powermate.set_raw_data_handler(knob_handler)

    # Thread: knob kontrol ke motor
    threading.Thread(target=stepper_driver_loop, daemon=True).start()
    
    # Thread: input manual dari terminal
    threading.Thread(target=manual_input_loop, daemon=True).start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Program dihentikan.")
    finally:
        powermate.close()
        arduino.close()
