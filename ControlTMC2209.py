import serial
import pywinusb.hid as hid
import threading
import time
from datetime import datetime
import socket

# --- Koneksi Arduino ---
arduino = serial.Serial('COM5', 115200)
time.sleep(2)

# --- Variabel global ---
knob_delta = 0
accumulated_delta = 0
lock = threading.Lock()
client_socket = None

# --- Setup socket server ---
HOST = '127.0.0.1'
PORT = 5000
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen(1)
print(f"[SOCKET] Listening on {HOST}:{PORT}...")

# --- Terima koneksi client UI ---
def accept_client():
    global client_socket
    while True:
        client_socket, addr = server_socket.accept()
        print(f"[SOCKET] Client connected from {addr}")

threading.Thread(target=accept_client, daemon=True).start()

# --- Thread menerima command dari UI ---
def ui_command_thread():
    global client_socket
    while True:
        if client_socket:
            try:
                data = client_socket.recv(1024).decode("utf-8").strip()
                if data:
                    cmds = data.split("\n")
                    for cmd in cmds:
                        cmd = cmd.strip()
                        if cmd:
                            arduino.write((cmd + "\n").encode())
                            print(f"[UI] {cmd}")
            except Exception as e:
                print(f"[SOCKET ERROR] {e}")
                client_socket = None
        else:
            time.sleep(0.1)

threading.Thread(target=ui_command_thread, daemon=True).start()

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

# --- Thread input manual console ---
def manual_input():
    while True:
        try:
            val = input().strip()
            if val == "":
                continue

            if val[0].upper() == "D":
                try:
                    deg = int(val[1:])
                    if 0 <= deg <= 360:
                        cmd = val.upper() + "\n"
                        arduino.write(cmd.encode())
                    else:
                        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        print(f"[D-SKIP] Value {deg} out of range 0-360 | Time {ts}")
                        send_socket(f"[D-SKIP] Value {deg} out of range 0-360 | Time {ts}")
                        continue
                except ValueError:
                    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    print(f"[D-SKIP] Invalid value | Time {ts}")
                    send_socket(f"[D-SKIP] Invalid value | Time {ts}")
                    continue
            elif val[0].upper() in ["S","C"]:
                cmd = val.upper() + "\n"
                arduino.write(cmd.encode())
            else:
                cmd = f"S{val}\n"
                arduino.write(cmd.encode())

        except Exception as e:
            print("Error input:", e)

# --- Fungsi kirim ke socket UI ---
def send_socket(msg):
    global client_socket
    try:
        if client_socket:
            client_socket.sendall((msg + "\n").encode())
    except Exception as e:
        client_socket = None

# --- Setup PowerMate ---
filter = hid.HidDeviceFilter(vendor_id=0x077d)
devices = filter.get_devices()
if devices:
    device = devices[0]
    device.open()
    device.set_raw_data_handler(read_knob(knob_callback))
    print("[PYTHON] StepTrack Antenna READY !")

    # Start thread
    threading.Thread(target=send_knob_loop, daemon=True).start()
    threading.Thread(target=manual_input, daemon=True).start()

    try:
        while True:
            line = arduino.readline().decode('utf-8').strip()
            if not line:
                continue

            parts = line.split(",")
            label = parts[0].strip()
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]

            output = ""
            if label.startswith("[K]") and len(parts) == 3:
                raw = int(parts[1])
                bearing = float(parts[2])
                output = f"[K] | Raw {raw} | Bearing {bearing:.2f} | Time {ts}"

            elif label.startswith("[S]") or label.startswith("[S-SKIP]") and len(parts) == 3:
                raw = int(parts[1])
                bearing = float(parts[2])
                output = f"[S] | Raw {raw} | Bearing {bearing:.2f} | Time {ts}"

            elif label.startswith("[D]") or label.startswith("[D-SKIP]") and len(parts) == 3:
                raw = int(parts[1])
                bearing = float(parts[2])
                output = f"[D] | Raw {raw} | Bearing {bearing:.2f} | Time {ts}"

            elif label.startswith("[C]") and len(parts) == 3:
                raw = int(parts[1])
                bearing = float(parts[2])
                output = f"[C] | RESET | Raw {raw} | Bearing {bearing:.2f} | Time {ts}"

            elif label.startswith("[SENSOR]") and len(parts) == 3:
                raw = int(parts[1])
                bearing = float(parts[2])
                output = f"[SENSOR] | Raw {raw} | Bearing {bearing:.2f} | Time {ts}"

            else:
                output = line

            print(output)
            send_socket(output)
            time.sleep(0.005)

    except KeyboardInterrupt:
        device.close()
        print("\nProgram dihentikan.")
else:
    print("PowerMate device tidak ditemukan.")
