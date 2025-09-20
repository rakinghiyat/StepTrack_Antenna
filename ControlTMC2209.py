import serial
import pywinusb.hid as hid
import threading
import time
from datetime import datetime

arduino = serial.Serial('COM5', 115200)
time.sleep(2)

knob_delta = 0
lock = threading.Lock()
accumulated_delta = 0

last_knob_info = None
last_manual_info = None  # <<< tambahan untuk manual input

def read_knob(callback):
    def handler(data):
        rotation = data[2]
        if rotation > 127:
            rotation -= 256
        if rotation != 0:
            callback(rotation)
    return handler

def knob_callback(delta):
    global knob_delta
    with lock:
        knob_delta += delta

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

            # scaling nonlinear
            scale = 1 if abs_d <= 3 else 2

            accumulated_delta += sign * abs_d * scale
            move_steps = int(accumulated_delta)

            if move_steps != 0:
                cmd = f"K{move_steps}\n"   # <<< knob command
                arduino.write(cmd.encode())
                accumulated_delta -= move_steps

                last_knob_info = (d, scale, move_steps)

def manual_input():
    global last_manual_info
    while True:
        try:
            val = input("Masukkan perintah (contoh: 200 / -200 / D90 / S1600 / C): ")
            if val.strip() == "":
                continue
            if val[0].upper() in ["S", "D", "C"]:
                cmd = val.upper() + "\n"
            else:
                cmd = f"S{val}\n"
            arduino.write(cmd.encode())
            print(f"[PYTHON] Manual dikirim: {cmd.strip()}")
            last_manual_info = cmd.strip()  # <<< simpan info untuk log feedback
        except Exception as e:
            print("Error input:", e)

# Setup PowerMate
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

                    if last_knob_info:
                        d, scale, move_steps = last_knob_info
                        print(f"Knob {d} | Scale {scale} | Move {move_steps} | Raw {rawAngle} | Bearing {angleDeg:.2f} | Time {timestamp}")
                        last_knob_info = None

                    elif last_manual_info:
                        print(f"[PYTHON] Manual {last_manual_info} | Raw {rawAngle} | Bearing {angleDeg:.2f} | Time {timestamp}")
                        last_manual_info = None

                except:
                    pass
            time.sleep(0.01)
    except KeyboardInterrupt:
        device.close()
