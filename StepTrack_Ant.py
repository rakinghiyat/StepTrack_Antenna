import socket
import threading
import tkinter as tk
import math
import time

HOST = "127.0.0.1"
PORT = 5000

# --- UI ---
root = tk.Tk()
root.title("StepTrack Antenna Monitor")
root.geometry("900x400")

# Canvas untuk kompas
canvas = tk.Canvas(root, width=300, height=300, bg="white")
canvas.pack(side="left", padx=10, pady=10)

center_x, center_y, radius = 150, 150, 120
canvas.create_oval(center_x-radius, center_y-radius, center_x+radius, center_y+radius, outline="black")

needle = canvas.create_line(center_x, center_y, center_x, center_y-radius, width=3, fill="red")

# Log area
log_text = tk.Text(root, width=60, height=25)
log_text.pack(side="right", padx=10, pady=10)

bearing_value = tk.StringVar(value="Bearing: 0.00°")
label = tk.Label(root, textvariable=bearing_value, font=("Arial", 14))
label.pack(side="bottom", pady=10)

# --- Input command D / S ---
entry_frame = tk.Frame(root)
entry_frame.pack(side="bottom", pady=5)

tk.Label(entry_frame, text="Command D/S:").pack(side="left")
command_entry = tk.Entry(entry_frame, width=10)
command_entry.pack(side="left", padx=5)

def send_command():
    cmd = command_entry.get().strip()
    if cmd:
        try:
            client_socket.sendall((cmd + "\n").encode())
            log_text.insert(tk.END, f"[UI] Sent command: {cmd}\n")
            log_text.see(tk.END)
            command_entry.delete(0, tk.END)
        except Exception as e:
            log_text.insert(tk.END, f"[UI-ERROR] {e}\n")
            log_text.see(tk.END)

send_btn = tk.Button(entry_frame, text="Send", command=send_command)
send_btn.pack(side="left", padx=5)

# --- Update jarum ---
current_bearing = 0.0
target_bearing = 0.0
bearing_lock = threading.Lock()

def update_needle_interpolated():
    global current_bearing, target_bearing
    with bearing_lock:
        delta = target_bearing - current_bearing
        # wrap-around handling
        if delta > 180:
            delta -= 360
        elif delta < -180:
            delta += 360

        # interpolasi halus
        step = delta * 0.2  # 0.2 = smoothing factor
        if abs(step) < 0.01:
            step = delta
        current_bearing += step

        # wrap current_bearing ke 0-360
        if current_bearing >= 360:
            current_bearing -= 360
        elif current_bearing < 0:
            current_bearing += 360

        angle_rad = math.radians(current_bearing - 90)
        x = center_x + radius * math.cos(angle_rad)
        y = center_y + radius * math.sin(angle_rad)
        canvas.coords(needle, center_x, center_y, x, y)
        bearing_value.set(f"Bearing: {current_bearing:.2f}°")

    root.after(20, update_needle_interpolated)  # update setiap 20ms

root.after(20, update_needle_interpolated)

# --- Socket client ---
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

def socket_thread():
    global target_bearing, client_socket
    try:
        client_socket.connect((HOST, PORT))
        log_text.insert(tk.END, f"[UI] Connected to {HOST}:{PORT}\n")
        log_text.see(tk.END)

        while True:
            data = client_socket.recv(1024).decode("utf-8").strip()
            if not data:
                continue

            log_text.insert(tk.END, data + "\n")
            log_text.see(tk.END)

            # parsing bearing dari data Arduino
            try:
                parts = data.split("|")
                for part in parts:
                    if "Bearing" in part:
                        b_str = part.split()[1]
                        b = float(b_str)
                        with bearing_lock:
                            target_bearing = b
            except:
                pass

    except Exception as e:
        log_text.insert(tk.END, f"[UI-SOCKET-ERROR] {e}\n")
        log_text.see(tk.END)

threading.Thread(target=socket_thread, daemon=True).start()
root.mainloop()
