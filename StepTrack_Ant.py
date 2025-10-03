import socket
import threading
import tkinter as tk
import math

HOST = "127.0.0.1"
PORT = 5000

# --- UI ---
root = tk.Tk()
root.title("StepTrack Antenna Monitor")
root.geometry("800x400")

# Canvas untuk kompas
canvas = tk.Canvas(root, width=300, height=300, bg="white")
canvas.pack(side="left", padx=10, pady=10)

# Lingkaran kompas
center_x, center_y, radius = 150, 150, 120
canvas.create_oval(center_x-radius, center_y-radius, center_x+radius, center_y+radius, outline="black")

# Jarum awal
needle = canvas.create_line(center_x, center_y,
                            center_x, center_y-radius,
                            width=3, fill="red")

# Log area
log_text = tk.Text(root, width=60, height=25)
log_text.pack(side="right", padx=10, pady=10)

bearing_value = tk.StringVar(value="Bearing: 0.00°")
label = tk.Label(root, textvariable=bearing_value, font=("Arial", 14))
label.pack(side="bottom", pady=10)


# --- Update jarum ---
def update_needle(bearing):
    angle_rad = math.radians(bearing - 90)  # -90 agar 0° ke atas
    x = center_x + radius * math.cos(angle_rad)
    y = center_y + radius * math.sin(angle_rad)
    canvas.coords(needle, center_x, center_y, x, y)
    bearing_value.set(f"Bearing: {bearing:.2f}°")


# --- Terima data socket ---
def socket_thread():
    global bearing_value
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        while True:
            try:
                data = s.recv(1024).decode("utf-8").strip()
                if not data:
                    continue

                # tampilkan di log
                log_text.insert(tk.END, data + "\n")
                log_text.see(tk.END)

                # cari bearing
                parts = data.split("|")
                for part in parts:
                    if "Bearing" in part:
                        try:
                            bearing = float(part.split()[1])
                            root.after(0, update_needle, bearing)
                        except:
                            pass
            except Exception as e:
                log_text.insert(tk.END, f"[ERROR] {e}\n")
                log_text.see(tk.END)
                break


threading.Thread(target=socket_thread, daemon=True).start()
root.mainloop()
