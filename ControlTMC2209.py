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
absolute_bearing_red = 0.0
absolute_bearing_blue = 0.0
absolute_target_red = None
absolute_target_blue = None
s_direction_red = 0
s_direction_blue = 0
waiting_feedback_red = False
waiting_feedback_blue = False

bearing_lock = threading.Lock()
knob_delta = 0
accumulated_delta = 0
lock = threading.Lock()

# --- Steps per revolution ---
steps_per_rev = 3200  # satu putaran penuh jarum

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
    # pilih k sedemikian sehingga feedback_deg + 360*k dekat dengan reference_abs
    if reference_abs is None:
        return feedback_deg
    k = round((reference_abs - feedback_deg) / 360.0)
    return feedback_deg + 360.0 * k

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
                    # buat target absolut dekat posisi saat ini (hindari jump)
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
                # target absolut relatif ke posisi saat ini (bisa >360 atau <0)
                absolute_target_red = absolute_bearing_red + target_deg
                absolute_target_blue = absolute_bearing_blue + target_deg
                s_direction_red = 1 if steps > 0 else -1
                s_direction_blue = 1 if steps > 0 else -1
                # setelah jarum mencapai target UI, kita akan menunggu feedback dari Arduino untuk validasi
                waiting_feedback_red = True
                waiting_feedback_blue = True
            arduino.write((cmd + "\n").encode())

        elif cmd[0] == "C":
            # biarkan Arduino yang mengirim feedback C; kita bisa juga menandai menunggu feedback
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
    max_step_per_frame = 20  # derajat per frame (atur ini sesuai kebutuhan)

    with bearing_lock:
        # RED
        if absolute_target_red is not None:
            if s_direction_red != 0:
                # bergerak sesuai polaritas hingga mencapai absolute_target_red
                remaining = absolute_target_red - absolute_bearing_red
                step_mag = min(max_step_per_frame, abs(remaining))
                step_red = s_direction_red * step_mag
                # jika arah tanda berbeda karena sign mismatch, gunakan sign dari remaining
                if (remaining < 0 and s_direction_red > 0) or (remaining > 0 and s_direction_red < 0):
                    # arah target relatif ternyata berlawanan (misalnya karena wrap) -> perbaiki direction
                    s_direction_red = 1 if remaining > 0 else -1
                    step_red = s_direction_red * step_mag
                absolute_bearing_red += step_red

                # jika sudah sangat dekat -> snap & berhenti, tapi tetap menunggu feedback
                if abs(absolute_bearing_red - absolute_target_red) < 0.5:
                    absolute_bearing_red = absolute_target_red
                    s_direction_red = 0
                    # waiting_feedback_red sudah True (set saat kirim S), tunggu feedback Arduino
            else:
                # mode D/K/C (non-S) — hanya bergerak bila tidak menunggu feedback validasi
                if not waiting_feedback_red:
                    if absolute_target_red is not None:
                        # pastikan target dekat current (target sudah disesuaikan saat feedback/kirim D)
                        remaining = absolute_target_red - absolute_bearing_red
                        # gunakan pendekatan proporsional (halus)
                        step_red = remaining * 0.2
                        if abs(step_red) < 0.01:
                            step_red = remaining
                        absolute_bearing_red += step_red

        # BLUE
        if absolute_target_blue is not None:
            if s_direction_blue != 0:
                remaining_b = absolute_target_blue - absolute_bearing_blue
                step_mag_b = min(max_step_per_frame, abs(remaining_b))
                step_blue = s_direction_blue * step_mag_b
                if (remaining_b < 0 and s_direction_blue > 0) or (remaining_b > 0 and s_direction_blue < 0):
                    s_direction_blue = 1 if remaining_b > 0 else -1
                    step_blue = s_direction_blue * step_mag_b
                absolute_bearing_blue += step_blue
                if abs(absolute_bearing_blue - absolute_target_blue) < 0.5:
                    absolute_bearing_blue = absolute_target_blue
                    s_direction_blue = 0
                    # waiting_feedback_blue True -> tunggu feedback Arduino
            else:
                if not waiting_feedback_blue:
                    if absolute_target_blue is not None:
                        remaining_b = absolute_target_blue - absolute_bearing_blue
                        step_blue = remaining_b * 0.2
                        if abs(step_blue) < 0.01:
                            step_blue = remaining_b
                        absolute_bearing_blue += step_blue

        # Render (pakai modulo agar jarum tampil 0-360)
        bearing_red_mod = absolute_bearing_red % 360
        angle_red_rad = math.radians(bearing_red_mod - 90)
        x_red = center_x + radius * math.cos(angle_red_rad)
        y_red = center_y + radius * math.sin(angle_red_rad)
        canvas.coords(needle_red, center_x, center_y, x_red, y_red)
        bearing_value_red.set(f"Red Bearing: {bearing_red_mod:.2f}°")

        bearing_blue_mod = absolute_bearing_blue % 360
        angle_blue_rad = math.radians(bearing_blue_mod - 90)
        x_blue = center_x + radius * math.cos(angle_blue_rad)
        y_blue = center_y + radius * math.sin(angle_blue_rad)
        canvas.coords(needle_blue, center_x, center_y, x_blue, y_blue)
        bearing_value_blue.set(f"Blue Bearing: {bearing_blue_mod:.2f}°")

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

    while True:
        line = arduino.readline().decode('utf-8').strip()
        if not line:
            continue
        log_text.insert(tk.END, line + "\n")
        log_text.see(tk.END)

        # --- khusus [D-SKIP] ---
        if line.startswith("[D-SKIP]"):
            # abaikan saja, jangan ubah jarum atau bearing
            continue

        parts = line.split(",")
        if len(parts) >= 3:
            label = parts[0].strip("[]")
            try:
                angle = float(parts[2])  # 0..360 from Arduino
            except:
                continue

            with bearing_lock:
                if label == "SENSOR":
                    adjusted = adjust_feedback_to_reference(angle, absolute_bearing_red)
                    absolute_bearing_red = adjusted
                    absolute_target_red = adjusted
                    s_direction_red = 0
                    # blue dibiarkan

                elif label == "S":
                    ref_red = absolute_target_red if absolute_target_red is not None else absolute_bearing_red
                    adj_red = adjust_feedback_to_reference(angle, ref_red)
                    absolute_bearing_red = adj_red
                    absolute_target_red = adj_red
                    s_direction_red = 0
                    waiting_feedback_red = False

                    ref_blue = absolute_target_blue if absolute_target_blue is not None else absolute_bearing_blue
                    adj_blue = adjust_feedback_to_reference(angle, ref_blue)
                    absolute_bearing_blue = adj_blue
                    absolute_target_blue = adj_blue
                    s_direction_blue = 0
                    waiting_feedback_blue = False

                elif label in ("K", "D", "C"):
                    ref_r = absolute_target_red if absolute_target_red is not None else absolute_bearing_red
                    adj_r = adjust_feedback_to_reference(angle, ref_r)
                    absolute_bearing_red = adj_r
                    absolute_target_red = adj_r
                    s_direction_red = 0
                    waiting_feedback_red = False

                    ref_b = absolute_target_blue if absolute_target_blue is not None else absolute_bearing_blue
                    adj_b = adjust_feedback_to_reference(angle, ref_b)
                    absolute_bearing_blue = adj_b
                    absolute_target_blue = adj_b
                    s_direction_blue = 0
                    waiting_feedback_blue = False

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
