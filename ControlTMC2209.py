import serial
import pywinusb.hid as hid
import threading
import time
from datetime import datetime

# --- Koneksi Arduino ---
arduino = serial.Serial('COM5', 115200)
time.sleep(2)

# --- Variabel global ---
knob_delta = 0
accumulated_delta = 0
lock = threading.Lock()

# --- Handler PowerMate ---
def read_knob(callback):
    def handler(data):
        rotation = data[2]
        press = data[1]

        if rotation > 127:
            rotation -= 256
        if rotation != 0:
            callback(rotation)

        if press != 0:  # tombol ditekan
            arduino.write(b"C\n")
    return handler

def knob_callback(delta):
    global knob_delta
    with lock:
        knob_delta += delta

# --- Thread loop kirim data knob ---
def send_knob_loop():
    global knob_delta, accumulated_delta
    interval = 0.05
    while True:
        time.sleep(interval)
        with lock:
            d = knob_delta
            knob_delta = 0

        if d != 0:
            sign = 1 if d > 0 else -1
            scale = 1 if abs(d) <= 3 else 2
            accumulated_delta += sign * abs(d) * scale
            move_steps = int(accumulated_delta)

            if move_steps != 0:
                cmd = f"K{move_steps}\n"
                arduino.write(cmd.encode())
                accumulated_delta -= move_steps

# --- Thread input manual ---
def manual_input():
    while True:
        try:
            val = input().strip()
            if val == "":
                continue

            # Cek command D
            if val[0].upper() == "D":
                try:
                    deg = int(val[1:])
                    if 0 <= deg <= 360:
                        cmd = val.upper() + "\n"
                        arduino.write(cmd.encode())
                    else:
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        print(f"[D-SKIP] | Value {deg} out of range 0-360 | Time {timestamp}")
                        continue
                except ValueError:
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    print(f"[D-SKIP] | Invalid value | Time {timestamp}")
                    continue
            elif val[0].upper() in ["S","C"]:
                cmd = val.upper() + "\n"
                arduino.write(cmd.encode())
            else:
                cmd = f"S{val}\n"
                arduino.write(cmd.encode())

        except Exception as e:
            print("Error input:", e)

# --- Setup PowerMate ---
filter = hid.HidDeviceFilter(vendor_id=0x077d)
devices = filter.get_devices()
if devices:
    device = devices[0]
    device.open()
    device.set_raw_data_handler(read_knob(knob_callback))
    print("[PYTHON] StepTrack Antenna READY !")

    threading.Thread(target=send_knob_loop, daemon=True).start()
    threading.Thread(target=manual_input, daemon=True).start()

    try:
        while True:
            line = arduino.readline().decode('utf-8').strip()
            if not line:
                continue

            parts = line.split(",")
            label = parts[0].strip()
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # HH:MM:SS.mmm

            if label.startswith("[K]") and len(parts) == 3:
                raw = int(parts[1])
                bearing = float(parts[2])
                print(f"[K] | Raw {raw} | Bearing {bearing:.2f} | Time {timestamp}")

            elif (label.startswith("[S]") or label.startswith("[S-SKIP]")) and len(parts) == 3:
                raw = int(parts[1])
                bearing = float(parts[2])
                print(f"[S] | Raw {raw} | Bearing {bearing:.2f} | Time {timestamp}")

            elif (label.startswith("[D]") or label.startswith("[D-SKIP]")) and len(parts) == 3:
                raw = int(parts[1])
                bearing = float(parts[2])
                print(f"[D] | Raw {raw} | Bearing {bearing:.2f} | Time {timestamp}")

            elif label.startswith("[C]") and len(parts) == 3:
                raw = int(parts[1])
                bearing = float(parts[2])
                print(f"[C] | RESET | Raw {raw} | Bearing {bearing:.2f} | Time {timestamp}")

            elif label.startswith("[SENSOR]") and len(parts) == 3:
                raw = int(parts[1])
                bearing = float(parts[2])
                print(f"[SENSOR] | Raw {raw} | Bearing {bearing:.2f} | Time {timestamp}")

            else:
                print (line)

            time.sleep(0.005)

    except KeyboardInterrupt:
        device.close()
        print("\nProgram dihentikan.")
else:
    print("PowerMate device tidak ditemukan.")
