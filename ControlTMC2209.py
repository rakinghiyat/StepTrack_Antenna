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
current_bearing_red = 0.0     # jarum merah
current_bearing_blue = 0.0    # jarum biru
target_bearing_red = 0.0
target_bearing_blue = 0.0
pending_bearing_red = None
pending_bearing_blue = None
bearing_lock = threading.Lock()
step_to_degree = 0.1  # asumsi konversi step ke derajat
knob_delta = 0
accumulated_delta = 0
lock = threading.Lock()

# --- Mode spinning untuk S>1800 ---
spinning_mode = False
spin_direction = 0  # +1 = CW, -1 = CCW

# --- Socket server (opsional) ---
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
root.geometry("900x400")

canvas = tk.Canvas(root, width=300, height=300, bg="white")
canvas.pack(side="left", padx=10, pady=10)
center_x, center_y, radius = 150, 150, 120
canvas.create_oval(center_x-radius, center_y-radius, center_x+radius, center_y+radius, outline="black")
needle_red = canvas.create_line(center_x, center_y, center_x, center_y-radius, width=3, fill="red")
needle_blue = canvas.create_line(center_x, center_y, center_x, center_y-radius, width=3, fill="blue")

log_text = tk.Text(root, width=40, height=25)
log_text.pack(side="right", padx=10, pady=10)

bearing_value_red = tk.StringVar(value="Red Bearing: 0.00°")
bearing_value_blue = tk.StringVar(value="Blue Bearing: 0.00°")
tk.Label(root, textvariable=bearing_value_red, font=("Arial", 14)).pack(side="bottom", pady=5)
tk.Label(root, textvariable=bearing_value_blue, font=("Arial", 14)).pack(side="bottom", pady=5)

# --- Entry Command D/S/C ---
entry_frame = tk.Frame(root)
entry_frame.pack(side="bottom", pady=5)
tk.Label(entry_frame, text="Command D/S/C:").pack(side="left")
command_entry = tk.Entry(entry_frame, width=10)
command_entry.pack(side="left", padx=5)

def send_command():
    global pending_bearing_red, pending_bearing_blue, spinning_mode, spin_direction
    cmd = command_entry.get().strip().upper()
    if not cmd:
        return
    try:
        if cmd[0] == "D":
            deg = int(cmd[1:])
            if 0 <= deg <= 360:
                with bearing_lock:
                    pending_bearing_red = deg
                    pending_bearing_blue = deg
                arduino.write((cmd + "\n").encode())
        elif cmd[0] == "S":
            steps = int(cmd[1:])
            if abs(steps) > 1800:
                # Aktifkan mode spinning
                with bearing_lock:
                    spinning_mode = True
                    spin_direction = 1 if steps > 0 else -1
                    pending_bearing_red = None
                    pending_bearing_blue = None
                arduino.write((cmd + "\n").encode())
            else:
                with bearing_lock:
                    pending_bearing_red = (current_bearing_red + steps * step_to_degree) % 360
                    pending_bearing_blue = (current_bearing_blue + steps * step_to_degree) % 360
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

# --- Update jarum ---
def update_needles():
    global current_bearing_red, current_bearing_blue, spinning_mode, spin_direction
    with bearing_lock:
        if spinning_mode:
            # Animasi spin sesuai polaritas
            spin_speed = 2.0  # derajat per update (atur sesuai kebutuhan)
            current_bearing_red = (current_bearing_red + spin_direction * spin_speed) % 360
            current_bearing_blue = (current_bearing_blue + spin_direction * spin_speed) % 360
        else:
            # Red needle
            if pending_bearing_red is not None:
                delta_red = pending_bearing_red - current_bearing_red
                if delta_red > 180:
                    delta_red -= 360
                elif delta_red < -180:
                    delta_red += 360
                step_red = delta_red * 0.2
                if abs(step_red) < 0.01:
                    step_red = delta_red
                current_bearing_red = (current_bearing_red + step_red) % 360
            # Blue needle
            if pending_bearing_blue is not None:
                delta_blue = pending_bearing_blue - current_bearing_blue
                if delta_blue > 180:
                    delta_blue -= 360
                elif delta_blue < -180:
                    delta_blue += 360
                step_blue = delta_blue * 0.2
                if abs(step_blue) < 0.01:
                    step_blue = delta_blue
                current_bearing_blue = (current_bearing_blue + step_blue) % 360

        # Update canvas
        angle_red_rad = math.radians(current_bearing_red - 90)
        x_red = center_x + radius * math.cos(angle_red_rad)
        y_red = center_y + radius * math.sin(angle_red_rad)
        canvas.coords(needle_red, center_x, center_y, x_red, y_red)
        bearing_value_red.set(f"Red Bearing: {current_bearing_red:.2f}°")

        angle_blue_rad = math.radians(current_bearing_blue - 90)
        x_blue = center_x + radius * math.cos(angle_blue_rad)
        y_blue = center_y + radius * math.sin(angle_blue_rad)
        canvas.coords(needle_blue, center_x, center_y, x_blue, y_blue)
        bearing_value_blue.set(f"Blue Bearing: {current_bearing_blue:.2f}°")

    root.after(20, update_needles)

root.after(20, update_needles)

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
    global target_bearing_red, pending_bearing_red, pending_bearing_blue, spinning_mode
    while True:
        line = arduino.readline().decode('utf-8').strip()
        if not line:
            continue
        log_text.insert(tk.END, line + "\n")
        log_text.see(tk.END)
        parts = line.split(",")
        if len(parts) >= 3:
            label = parts[0].strip("[]")
            try:
                angle = float(parts[2])
                with bearing_lock:
                    if label == "SENSOR":
                        pending_bearing_red = angle  # merah ikut sensor
                    elif label in ("K", "D", "S"):
                        pending_bearing_red = angle  # merah ikut command
                        pending_bearing_blue = angle # biru ikut command
                    # Matikan spinning begitu ada feedback
                    spinning_mode = False
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
