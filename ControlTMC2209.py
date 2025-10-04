import socket
import threading
import tkinter as tk
import math
import time
import serial
import pywinusb.hid as hid

# --- Koneksi Arduino ---
arduino = serial.Serial('COM5', 115200)
time.sleep(2)

# --- Variabel global ---
current_bearing = 0.0
target_bearing = 0.0
pending_bearing = None
bearing_lock = threading.Lock()
step_to_degree = 0.1  # asumsi konversi step ke derajat
knob_delta = 0
accumulated_delta = 0
lock = threading.Lock()

# --- Socket server (opsional, jika UI via socket) ---
HOST = '127.0.0.1'
PORT = 5000
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen(1)
client_socket = None

def accept_client():
    global client_socket
    while True:
        client_socket, addr = server_socket.accept()
        print(f"[SOCKET] Client connected from {addr}")

threading.Thread(target=accept_client, daemon=True).start()

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
            except:
                client_socket = None
        else:
            time.sleep(0.1)

threading.Thread(target=ui_command_thread, daemon=True).start()

# --- Setup Tkinter UI ---
root = tk.Tk()
root.title("StepTrack Antenna Monitor")
root.geometry("1050x400")

canvas = tk.Canvas(root, width=300, height=300, bg="white")
canvas.pack(side="left", padx=10, pady=10)
center_x, center_y, radius = 150, 150, 120
canvas.create_oval(center_x-radius, center_y-radius, center_x+radius, center_y+radius, outline="black")
needle = canvas.create_line(center_x, center_y, center_x, center_y-radius, width=3, fill="red")

log_text = tk.Text(root, width=60, height=25)
log_text.pack(side="right", padx=10, pady=10)

bearing_value = tk.StringVar(value="Bearing: 0.00°")
tk.Label(root, textvariable=bearing_value, font=("Arial", 14)).pack(side="bottom", pady=10)

# --- Entry Command D/S/C ---
entry_frame = tk.Frame(root)
entry_frame.pack(side="bottom", pady=5)
tk.Label(entry_frame, text="Command D/S/C:").pack(side="left")
command_entry = tk.Entry(entry_frame, width=10)
command_entry.pack(side="left", padx=5)

def send_command():
    global pending_bearing
    cmd = command_entry.get().strip().upper()
    if not cmd:
        return
    try:
        if cmd[0] == "D":
            deg = int(cmd[1:])
            if 0 <= deg <= 360:
                pending_bearing = deg
                arduino.write((cmd + "\n").encode())
        elif cmd[0] == "S":
            steps = int(cmd[1:])
            with bearing_lock:
                pending_bearing = (current_bearing + steps * step_to_degree) % 360
            arduino.write((cmd + "\n").encode())
        elif cmd[0] == "C":
            arduino.write(b"C\n")
        log_text.insert(tk.END, f"[UI] Sent command: {cmd}\n")
        log_text.see(tk.END)
        command_entry.delete(0, tk.END)
    except Exception as e:
        log_text.insert(tk.END, f"[UI-ERROR] {e}\n")
        log_text.see(tk.END)

tk.Button(entry_frame, text="Send", command=send_command).pack(side="left", padx=5)

# --- Update jarum interpolasi ---
def update_needle_interpolated():
    global current_bearing, target_bearing, pending_bearing
    with bearing_lock:
        if pending_bearing is not None:
            ui_target = pending_bearing
        else:
            ui_target = target_bearing

        delta = ui_target - current_bearing
        if delta > 180:
            delta -= 360
        elif delta < -180:
            delta += 360

        step = delta * 0.2
        if abs(step) < 0.01:
            step = delta
        current_bearing += step
        if current_bearing >= 360:
            current_bearing -= 360
        elif current_bearing < 0:
            current_bearing += 360

        angle_rad = math.radians(current_bearing - 90)
        x = center_x + radius * math.cos(angle_rad)
        y = center_y + radius * math.sin(angle_rad)
        canvas.coords(needle, center_x, center_y, x, y)
        bearing_value.set(f"Bearing: {current_bearing:.2f}°")

    root.after(20, update_needle_interpolated)

root.after(20, update_needle_interpolated)

# --- Handler PowerMate ---
def read_knob(callback):
    def handler(data):
        rotation = data[2]
        press = data[1]
        if rotation > 127:
            rotation -= 256
        if rotation != 0:
            callback(rotation)
        if press != 0:
            arduino.write(b"C\n")
    return handler

def knob_callback(delta):
    global knob_delta
    with lock:
        knob_delta += delta

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

# --- Thread membaca Arduino ---
def read_arduino():
    global target_bearing, pending_bearing
    while True:
        line = arduino.readline().decode('utf-8').strip()
        if not line:
            continue
        log_text.insert(tk.END, line + "\n")
        log_text.see(tk.END)
        parts = line.split(",")
        if len(parts) >= 3:
            try:
                bearing = float(parts[2])
                with bearing_lock:
                    target_bearing = bearing
                    pending_bearing = None  # sinkronisasi jarum
            except:
                pass

# --- Setup PowerMate ---
filter = hid.HidDeviceFilter(vendor_id=0x077d)
devices = filter.get_devices()
if devices:
    device = devices[0]
    device.open()
    device.set_raw_data_handler(read_knob(knob_callback))
    threading.Thread(target=send_knob_loop, daemon=True).start()
    threading.Thread(target=read_arduino, daemon=True).start()
    print("[PYTHON] StepTrack Antenna READY !")
else:
    print("PowerMate device tidak ditemukan.")

root.mainloop()
