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

# buffer untuk menyimpan info knob sebelum feedback datang
last_knob_info = None

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
            if abs_d <= 3:
                scale = 1
            else:
                scale = 2

            accumulated_delta += sign * abs_d * scale
            move_steps = int(accumulated_delta)

            if move_steps != 0:
                cmd = f"D{move_steps}\n"
                arduino.write(cmd.encode())
                accumulated_delta -= move_steps

                # simpan sementara info knob
                last_knob_info = (d, scale, move_steps)

# Setup PowerMate
filter = hid.HidDeviceFilter(vendor_id=0x077d)
devices = filter.get_devices()
if devices:
    device = devices[0]
    device.open()
    device.set_raw_data_handler(read_knob(knob_callback))
    print("PowerMate siap digunakan (Closed-loop knob).")

    threading.Thread(target=send_knob_loop, daemon=True).start()

    try:
        while True:
            line = arduino.readline().decode('utf-8').strip()
            if "," in line:
                try:
                    rawAngle, angleDeg = line.split(",")
                    rawAngle = int(rawAngle)
                    angleDeg = float(angleDeg)

                    if last_knob_info:
                        d, scale, move_steps = last_knob_info

                        # buat timestamp format HH:MM:SS.mmm
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                        print(f"Knob {d} | Scale {scale} | Move {move_steps} | Raw {rawAngle} | Bearing {angleDeg:.2f} | Time  {timestamp}")
                        last_knob_info = None  # reset setelah dicetak
                except:
                    pass
            time.sleep(0.01)
    except KeyboardInterrupt:
        device.close()
