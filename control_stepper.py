import time
import threading
from pywinusb import hid
import serial

# Koneksi ke Arduino (pastikan COM port sesuai)
arduino = serial.Serial('COM5', 115200)
print("Terhubung ke Arduino...", flush=True)

# Variabel kontrol utama
knob_dir = 0
last_knob_event = time.time()
knob_delay = 0.01
TIMEOUT = 0.2

# Posisi bearing dan stepper
bearing_deg = 0
step_pos = 0
step_per_click = 1.8 / 4  # 0.45 derajat per step (microstepping x4)
lock = threading.Lock()
stop_event = threading.Event()

# Encoder tracking
last_raw = None
last_deg = None

def normalize_bearing(b):
    b = b % 360
    return b if b >= 0 else b + 360

# Membaca data dari Arduino (encoder)
def read_from_arduino():
    global bearing_deg, last_raw, last_deg
    while not stop_event.is_set():
        try:
            line = arduino.readline().decode('utf-8').strip()
            if line.startswith("Raw Angle:"):
                parts = line.split(" | ")
                raw_val = int(parts[0].split(":")[1].strip())
                angle = float(parts[1].split(":")[1].strip())

                if raw_val != last_raw or angle != last_deg:
                    last_raw = raw_val
                    last_deg = angle
                    print(f"[ENC] Bearing: {bearing_deg:.2f}° | RAW: {raw_val}, Angle: {angle:.2f}°", flush=True)
        except Exception as e:
            print(f"[ERROR] Serial read: {e}")

# Kontrol stepper via knob input
def stepper_loop():
    global knob_dir, knob_delay, step_pos, bearing_deg
    while not stop_event.is_set():
        now = time.time()
        with lock:
            if now - last_knob_event > TIMEOUT:
                knob_dir = 0
            dir = knob_dir
            delay = knob_delay

        if dir == 1:
            arduino.write(b'R')
            with lock:
                step_pos += 1
                bearing_deg = normalize_bearing(step_pos * step_per_click)
        elif dir == -1:
            arduino.write(b'L')
            with lock:
                step_pos -= 1
                bearing_deg = normalize_bearing(step_pos * step_per_click)

        if dir != 0:
            print(f"[KNOB] Bearing: {bearing_deg:.2f}°", flush=True)

        time.sleep(delay)

# Input manual dari pengguna
def manual_input_loop():
    global step_pos, bearing_deg
    while not stop_event.is_set():
        try:
            target = input("Masukkan target bearing (0–359): ")
            if stop_event.is_set():
                break
            target = int(target)
            if not (0 <= target < 360):
                print("Input harus antara 0–359.")
                continue

            with lock:
                current = normalize_bearing(step_pos * step_per_click)
                delta = (target - current + 540) % 360 - 180
                steps = int(round(delta / step_per_click))
                direction = 'R' if steps > 0 else 'L'

                for _ in range(abs(steps)):
                    arduino.write(direction.encode())
                    step_pos += 1 if direction == 'R' else -1
                    bearing_deg = normalize_bearing(step_pos * step_per_click)
                    time.sleep(0.005)

                print(f"[MANUAL] Posisi akhir: {bearing_deg:.2f}°")

        except ValueError:
            print("Input tidak valid.")
        except EOFError:
            stop_event.set()

# Handler knob input
last_event = time.time()

def knob_handler(data):
    global knob_dir, last_knob_event, knob_delay, last_event, step_pos, bearing_deg

    delta = data[2]
    button = data[1]
    now = time.time()
    interval = now - last_event
    last_event = now

    if interval > 0:
        speed = 1.0 / interval
        knob_delay = max(0.0005, min(0.02, 0.05 / speed))

    with lock:
        if delta == 1:
            knob_dir = 1
        elif delta == 255:
            knob_dir = -1
        last_knob_event = now

    if button == 1:
        arduino.write(b'C')
        with lock:
            knob_dir = 0
            bearing_deg = 0
            step_pos = 0
            print("[KNOB] Reset ke 0°", flush=True)
            last_knob_event = time.time()

# Mulai HID PowerMate
devices = hid.HidDeviceFilter().get_devices()
powermate = next((dev for dev in devices if "Griffin PowerMate" in dev.product_name), None)

if not powermate:
    print("PowerMate tidak ditemukan.")
else:
    print("PowerMate ditemukan. Memulai layanan...", flush=True)
    powermate.open()
    powermate.set_raw_data_handler(knob_handler)

    t1 = threading.Thread(target=stepper_loop, daemon=True)
    t2 = threading.Thread(target=manual_input_loop, daemon=True)
    t3 = threading.Thread(target=read_from_arduino, daemon=True)
    t1.start()
    t2.start()
    t3.start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[INFO] Program dihentikan.")
        stop_event.set()
        time.sleep(0.5)
    finally:
        powermate.close()
        arduino.close()
