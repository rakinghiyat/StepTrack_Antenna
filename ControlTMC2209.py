import serial
import pywinusb.hid as hid
import threading
import time
from datetime import datetime

# --- Koneksi Arduino ---
arduino = serial.Serial('COM5', 115200)
time.sleep(2)

# --- Variabel Global ---
knob_delta = 0
accumulated_delta = 0
lock = threading.Lock()

last_knob_info = None
last_manual_info = None

# --- Handler untuk data dari knob (rotasi & tekan) ---
def read_knob(callback):
    def handler(data):
        global last_manual_info
        rotation = data[2]
        press = data[1]  # tombol knob ditekan

        # Handle rotasi
        if rotation > 127:
            rotation -= 256
        if rotation != 0:
            callback(rotation)

        # Handle tombol ditekan → reset ke 0 derajat
        if press != 0:
            arduino.write(b"C\n")
            last_manual_info = "C"

    return handler

# --- Callback rotasi knob ---
def knob_callback(delta):
    global knob_delta
    with lock:
        knob_delta += delta

# --- Thread loop kirim data knob ---
def send_knob_loop():
    global knob_delta, accumulated_delta, last_knob_info
    interval = 0.05  # 50 ms
    while True:
        time.sleep(interval)
        with lock:
            d = knob_delta
            knob_delta = 0

        if d != 0:
            abs_d = abs(d)
            sign = 1 if d > 0 else -1
            scale = 1 if abs_d <= 3 else 2
            accumulated_delta += sign * abs_d * scale
            move_steps = int(accumulated_delta)

            if move_steps != 0:
                cmd = f"K{move_steps}\n"
                arduino.write(cmd.encode())
                accumulated_delta -= move_steps
                last_knob_info = (d, scale, move_steps)

# --- Thread input manual dari user ---
def manual_input():
    global last_manual_info
    print("Masukkan perintah (contoh: 200 / -200 / D90 / S1600 / C):")
    while True:
        try:
            val = input().strip()
            if val == "":
                continue

            # Perintah manual D/S/C
            if val[0].upper() in ["S", "D", "C"]:
                if val[0].upper() == "D":
                    try:
                        target_deg = int(val[1:])
                        if target_deg < 0 or target_deg > 360:
                            print(f"[ERROR] Input D harus 0–360 (Anda memasukkan {target_deg})")
                            continue
                    except ValueError:
                        print("[ERROR] Format D salah, gunakan D0–D360")
                        continue
                cmd = val.upper() + "\n"
            else:
                # Default → relatif S
                cmd = f"S{val}\n"

            arduino.write(cmd.encode())
            last_manual_info = cmd.strip()

        except Exception as e:
            print("Error input:", e)

# --- Setup PowerMate ---
filter = hid.HidDeviceFilter(vendor_id=0x077d)
devices = filter.get_devices()
if devices:
    device = devices[0]
    device.open()
    device.set_raw_data_handler(read_knob(knob_callback))
    print("PowerMate siap digunakan (Closed-loop).")

    threading.Thread(target=send_knob_loop, daemon=True).start()
    threading.Thread(target=manual_input, daemon=True).start()

    try:
        while True:
            line = arduino.readline().decode('utf-8').strip()
            if "," in line:
                try:
                    rawAngle, angleDeg = line.split(",")
                    rawAngle = int(rawAngle)
                    angleDeg = float(angleDeg)
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                    # Log knob
                    if last_knob_info:
                        d, scale, move_steps = last_knob_info
                        print(f"Knob {d} | Scale {scale} | Move {move_steps} | Raw {rawAngle} | Bearing {angleDeg:.2f} | Time {timestamp}")
                        last_knob_info = None

                    # Log manual
                    elif last_manual_info:
                        cmd_type = last_manual_info[0].upper()
                        value = last_manual_info[1:] if len(last_manual_info) > 1 else ""
                        print(f"[Manual] {last_manual_info} | Scale 0 | Move {value} | Raw {rawAngle} | Bearing {angleDeg:.2f} | Time {timestamp}")
                        last_manual_info = None

                except Exception as e:
                    print("Error parsing line:", e)

            time.sleep(0.01)

    except KeyboardInterrupt:
        device.close()
        print("\nProgram dihentikan.")
