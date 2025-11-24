import socket
import threading
import tkinter as tk
import math
import time
import serial
import pywinusb.hid as hid
import json
import os

# --- State file ---
STATE_FILE = "state.json"
saved_state = {
    "last_bearing": 0.0,
    "last_revolutions": 0.0,
    "last_raw_angle": 0.0
}

# --- Koneksi Arduino ---
arduino = serial.Serial('COM5', 115200)
time.sleep(2)

# --- Konfigurasi arah gerak antenna ---
# True = CW (searah jarum jam)
# False = CCW (berlawanan jarum jam)
antenna_direction_cw = False

# --- Variabel global ---
absolute_bearing_red = 0.0
absolute_bearing_blue = 0.0
absolute_target_red = None
absolute_target_blue = None
s_direction_red = 0
s_direction_blue = 0
waiting_feedback_red = False
waiting_feedback_blue = False
projected_bearing = 0.0   # dihitung dari knob
actual_bearing = 0.0      # feedback dari Arduino
display_bearing = 0.0     # yang ditampilkan di needle

bearing_lock = threading.Lock()
knob_delta = 0
accumulated_delta = 0
lock = threading.Lock()

# --- Variabel revolusi ---
last_raw_angle = None
revolution_count = 0.0

# --- Konfigurasi gear ---
motor_teeth = 36
antenna_teeth = 68
gear_ratio = motor_teeth / antenna_teeth
steps_per_rev = 3200  # satu putaran penuh motor

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

# --- Helper: sesuaikan feedback (0-360) ke nilai absolut terdekat dari reference ---
def adjust_feedback_to_reference(feedback_deg, reference_abs):
    if reference_abs is None:
        return feedback_deg
    k = round((reference_abs - feedback_deg) / 360.0)
    return feedback_deg + 360.0 * k

# --- State load/save ---
def load_state():
    global saved_state
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w") as f:
            json.dump(saved_state, f, indent=4)
        print("[STATE] state.json dibuat (default zeros)")
        return saved_state
    try:
        with open(STATE_FILE, "r") as f:
            saved_state = json.load(f)
        # ensure floats
        saved_state["last_bearing"] = float(saved_state.get("last_bearing", 0.0))
        saved_state["last_revolutions"] = float(saved_state.get("last_revolutions", 0.0))
        saved_state["last_raw_angle"] = float(saved_state.get("last_raw_angle", 0.0))
        print("[STATE] state.json dibaca:", saved_state)
    except Exception as e:
        print("[STATE] ERROR membaca state.json, memakai default:", e)
        saved_state = {
            "last_bearing": 0.0,
            "last_revolutions": 0.0,
            "last_raw_angle": 0.0
        }
    return saved_state


def save_state():
    try:
        data = {
            "last_bearing": float(absolute_bearing_red % 360),
            "last_revolutions": float(revolution_count),
            "last_raw_angle": float(last_raw_angle if last_raw_angle is not None else 0.0)
        }
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, indent=4)
        print("[STATE] state saved:", data)
    except Exception as e:
        print("[STATE] ERROR save:", e)

# --- Setup Tkinter UI ---
root = tk.Tk()
root.title("StepTrack Antenna Monitor")
root.geometry("1200x500")

canvas = tk.Canvas(root, width=600, height=400, bg="white")
canvas.pack(side="left", padx=10, pady=10)

# --- Lingkaran motor ---
motor_cx, motor_cy, motor_r = 150, 200, 100
canvas.create_oval(motor_cx-motor_r, motor_cy-motor_r,
                   motor_cx+motor_r, motor_cy+motor_r, outline="black")
needle_red = canvas.create_line(motor_cx, motor_cy, motor_cx, motor_cy-motor_r,
                                width=3, fill="red")
needle_blue = canvas.create_line(motor_cx, motor_cy, motor_cx, motor_cy-motor_r,
                                 width=3, fill="blue")

# Teeth motor
for i in range(motor_teeth):
    ang = 2*math.pi * i / motor_teeth
    x1 = motor_cx + (motor_r-5)*math.cos(ang)
    y1 = motor_cy + (motor_r-5)*math.sin(ang)
    x2 = motor_cx + (motor_r+5)*math.cos(ang)
    y2 = motor_cy + (motor_r+5)*math.sin(ang)
    canvas.create_line(x1, y1, x2, y2, fill="gray")

canvas.create_text(motor_cx, motor_cy+motor_r+15, text="Motor Pulley (76 teeth)")

# --- Lingkaran antenna ---
ant_cx, ant_cy, ant_r = 450, 200, 145
canvas.create_oval(ant_cx-ant_r, ant_cy-ant_r,
                   ant_cx+ant_r, ant_cy+ant_r, outline="black")
needle_ant_red = canvas.create_line(ant_cx, ant_cy, ant_cx, ant_cy-ant_r,
                                    width=3, fill="red")
needle_ant_blue = canvas.create_line(ant_cx, ant_cy, ant_cx, ant_cy-ant_r,
                                     width=3, fill="blue")

# Teeth antenna
for i in range(antenna_teeth):
    ang = 2*math.pi * i / antenna_teeth
    x1 = ant_cx + (ant_r-5)*math.cos(ang)
    y1 = ant_cy + (ant_r-5)*math.sin(ang)
    x2 = ant_cx + (ant_r+5)*math.cos(ang)
    y2 = ant_cy + (ant_r+5)*math.sin(ang)
    canvas.create_line(x1, y1, x2, y2, fill="gray")

canvas.create_text(ant_cx, ant_cy+ant_r+15, text="Antenna Pulley (228 teeth)")

# --- Log dan Bearing ---
log_text = tk.Text(root, width=40, height=25)
log_text.pack(side="right", padx=10, pady=10)

bearing_value_red = tk.StringVar(value="Red Bearing: 0.00°")
bearing_value_blue = tk.StringVar(value="Blue Bearing: 0.00°")
bearing_value_ant_red = tk.StringVar(value="Antenna Red: 0.00°")
bearing_value_ant_blue = tk.StringVar(value="Antenna Blue: 0.00°")
revolution_value = tk.StringVar(value="Revolutions: 0.00")

tk.Label(root, textvariable=bearing_value_red, font=("Arial", 12)).pack(side="bottom", pady=2)
tk.Label(root, textvariable=bearing_value_blue, font=("Arial", 12)).pack(side="bottom", pady=2)
tk.Label(root, textvariable=bearing_value_ant_red, font=("Arial", 12)).pack(side="bottom", pady=2)
tk.Label(root, textvariable=bearing_value_ant_blue, font=("Arial", 12)).pack(side="bottom", pady=2)
tk.Label(root, textvariable=revolution_value, font=("Arial", 12, "bold")).pack(side="bottom", pady=5)

# --- Entry Command D/S/C ---
entry_frame = tk.Frame(root)
entry_frame.pack(side="bottom", pady=5)
tk.Label(entry_frame, text="Command D/S/C:").pack(side="left")
command_entry = tk.Entry(entry_frame, width=10)
command_entry.pack(side="left", padx=5)

def send_command():
    global absolute_target_red, absolute_target_blue
    global s_direction_red, s_direction_blue
    global waiting_feedback_red, waiting_feedback_blue

    cmd = command_entry.get().strip().upper()
    if not cmd:
        return
    try:
        if cmd[0] == "D":
            deg = int(cmd[1:])
            if 0 <= deg <= 360:
                with bearing_lock:
                    absolute_target_red = adjust_feedback_to_reference(deg, absolute_bearing_red)
                    absolute_target_blue = adjust_feedback_to_reference(deg, absolute_bearing_blue)
                    s_direction_red = 0
                    s_direction_blue = 0
                    waiting_feedback_red = False
                    waiting_feedback_blue = False
                arduino.write((cmd + "\n").encode())

        elif cmd[0] == "S":
            steps = int(cmd[1:])
            with bearing_lock:
                target_deg = (steps / steps_per_rev) * 360.0
                absolute_target_red = absolute_bearing_red + target_deg
                absolute_target_blue = absolute_bearing_blue + target_deg
                s_direction_red = 1 if steps > 0 else -1
                s_direction_blue = 1 if steps > 0 else -1
                waiting_feedback_red = True
                waiting_feedback_blue = True
            arduino.write((cmd + "\n").encode())

        elif cmd[0] == "C":
            with bearing_lock:
                waiting_feedback_red = True
                waiting_feedback_blue = True
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
    global absolute_bearing_red, absolute_bearing_blue
    global s_direction_red, s_direction_blue
    global waiting_feedback_red, waiting_feedback_blue
    max_step_per_frame = 20

    with bearing_lock:
        # --- RED ---
        if absolute_target_red is not None:
            remaining = absolute_target_red - absolute_bearing_red
            step_mag = min(max_step_per_frame, abs(remaining))
            step_red = s_direction_red * step_mag if s_direction_red != 0 else remaining * 0.2
            if abs(step_red) < 0.01:
                step_red = remaining
            if (remaining < 0 and step_red > 0) or (remaining > 0 and step_red < 0):
                step_red = -step_red
            absolute_bearing_red += step_red
            if abs(absolute_bearing_red - absolute_target_red) < 0.5:
                absolute_bearing_red = absolute_target_red
                s_direction_red = 0

        # --- BLUE ---
        if absolute_target_blue is not None:
            remaining_b = absolute_target_blue - absolute_bearing_blue
            step_mag_b = min(max_step_per_frame, abs(remaining_b))
            step_blue = s_direction_blue * step_mag_b if s_direction_blue != 0 else remaining_b * 0.2
            if abs(step_blue) < 0.01:
                step_blue = remaining_b
            if (remaining_b < 0 and step_blue > 0) or (remaining_b > 0 and step_blue < 0):
                step_blue = -step_blue
            absolute_bearing_blue += step_blue
            if abs(absolute_bearing_blue - absolute_target_blue) < 0.5:
                absolute_bearing_blue = absolute_target_blue
                s_direction_blue = 0

        # --- Render motor dan antenna ---
        bearing_red_mod = absolute_bearing_red % 360
        angle_red_rad = math.radians(bearing_red_mod - 90)
        x_red = motor_cx + motor_r * math.cos(angle_red_rad)
        y_red = motor_cy + motor_r * math.sin(angle_red_rad)
        canvas.coords(needle_red, motor_cx, motor_cy, x_red, y_red)
        bearing_value_red.set(f"Red Bearing: {bearing_red_mod:.2f}°")

        bearing_blue_mod = absolute_bearing_blue % 360
        angle_blue_rad = math.radians(bearing_blue_mod - 90)
        x_blue = motor_cx + motor_r * math.cos(angle_blue_rad)
        y_blue = motor_cy + motor_r * math.sin(angle_blue_rad)
        canvas.coords(needle_blue, motor_cx, motor_cy, x_blue, y_blue)
        bearing_value_blue.set(f"Blue Bearing: {bearing_blue_mod:.2f}°")

        # apply direction multiplier for antenna rendering
        direction = 1 if antenna_direction_cw else -1

        ant_red = (absolute_bearing_red * gear_ratio * direction) % 360
        ang_ant_red = math.radians(ant_red - 90)
        ax_red = ant_cx + ant_r * math.cos(ang_ant_red)
        ay_red = ant_cy + ant_r * math.sin(ang_ant_red)
        canvas.coords(needle_ant_red, ant_cx, ant_cy, ax_red, ay_red)
        bearing_value_ant_red.set(f"Antenna Red: {ant_red:.2f}°")

        ant_blue = (absolute_bearing_blue * gear_ratio * direction) % 360
        ang_ant_blue = math.radians(ant_blue - 90)
        ax_blue = ant_cx + ant_r * math.cos(ang_ant_blue)
        ay_blue = ant_cy + ant_r * math.sin(ang_ant_blue)
        canvas.coords(needle_ant_blue, ant_cx, ant_cy, ax_blue, ay_blue)
        bearing_value_ant_blue.set(f"Antenna Blue: {ant_blue:.2f}°")

        revolution_value.set(f"Revolutions: {revolution_count:.2f}")

    root.after(20, update_needles)

root.after(20, update_needles)

# --- Handler PowerMate ---
def read_knob(callback):
    def handler(data):
        rotation = data[2]
        press = data[1]
        if rotation > 127: rotation -= 256
        if rotation != 0: callback(rotation)
        if press != 0: arduino.write(b"C\n")
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
    global absolute_target_red, absolute_target_blue
    global absolute_bearing_red, absolute_bearing_blue
    global s_direction_red, s_direction_blue
    global waiting_feedback_red, waiting_feedback_blue
    global last_raw_angle, revolution_count

    while True:
        line = arduino.readline().decode('utf-8').strip()
        if not line:
            continue
        log_text.insert(tk.END, line + "\n")
        log_text.see(tk.END)

        parts = line.split(",")
        if len(parts) < 3:
            continue

        label = parts[0].strip("[]")
        try:
            raw_angle = float(parts[1])
            angle_deg = float(parts[2])
        except:
            continue

        # --- Hitung revolusi antenna berdasarkan raw AS5600 (motor) ---
        # raw AS5600 memiliki rentang 0–4095 = satu putaran motor
        if last_raw_angle is not None:
            diff = raw_angle - last_raw_angle

            # deteksi wrap (melompati 0)
            if diff > 2048:
                diff -= 4096
            elif diff < -2048:
                diff += 4096

            # konversi raw → putaran motor
            motor_rev_delta = diff / 4096.0

            # konversi putaran motor → putaran antenna (36/68)
            antenna_rev_delta = -motor_rev_delta * gear_ratio

            revolution_count += antenna_rev_delta

        last_raw_angle = raw_angle

        if label == "D-SKIP":
            label = "D"

        with bearing_lock:
            if label == "SENSOR":
                adjusted = adjust_feedback_to_reference(angle_deg, absolute_bearing_red)
                absolute_bearing_red = adjusted
                absolute_target_red = adjusted
                s_direction_red = 0
                waiting_feedback_red = False
            elif label in ("K", "D", "S", "Q"):
                ref_r = absolute_target_red if absolute_target_red is not None else absolute_bearing_red
                adj_r = adjust_feedback_to_reference(angle_deg, ref_r)
                absolute_target_red = adj_r
                s_direction_red = 1 if adj_r > absolute_bearing_red else -1
                waiting_feedback_red = True

                ref_b = absolute_target_blue if absolute_target_blue is not None else absolute_bearing_blue
                adj_b = adjust_feedback_to_reference(angle_deg, ref_b)
                absolute_target_blue = adj_b
                s_direction_blue = 1 if adj_b > absolute_bearing_blue else -1
                waiting_feedback_blue = True
            elif label == "C":
                ref_r = absolute_target_red if absolute_target_red is not None else absolute_bearing_red
                adj_r = adjust_feedback_to_reference(angle_deg, ref_r)
                absolute_target_red = adj_r
                s_direction_red = 1 if adj_r > absolute_bearing_red else -1
                waiting_feedback_red = True

                adj_b = adjust_feedback_to_reference(angle_deg, absolute_bearing_blue)
                absolute_target_blue = adj_b
                s_direction_blue = 1 if adj_b > absolute_bearing_blue else -1
                waiting_feedback_blue = True

# --- Background request posisi awal ---
def request_initial_position():
    global last_raw_angle, revolution_count, absolute_bearing_red, absolute_target_red
    time.sleep(0.5)

    # load state
    state = load_state()

    # restore internal variables from state
    try:
        last_raw_angle = float(state.get("last_raw_angle", 0.0))
        revolution_count = float(state.get("last_revolutions", 0.0))
        absolute_bearing_red = float(state.get("last_bearing", 0.0))
        absolute_target_red = absolute_bearing_red
    except Exception:
        pass

    # kirim perintah D untuk memposisikan motor ke last_bearing
    try:
        deg = int(round(absolute_bearing_red)) % 360
        cmd = f"D{deg}\n"
        arduino.write(cmd.encode())
        print(f"[STATE] Restoring last bearing -> D{deg}")
    except Exception as e:
        print("[STATE] ERROR saat restore posisi:", e)

threading.Thread(target=request_initial_position, daemon=True).start()

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

# --- Save state on close ---
def on_closing():
    save_state()
    try:
        # close device if open
        if 'device' in globals() and device is not None:
            try:
                device.close()
            except:
                pass
    finally:
        root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)

root.mainloop()
