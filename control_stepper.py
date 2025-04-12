from pywinusb import hid
import serial
import time

# Inisialisasi koneksi serial ke Arduino
arduino = serial.Serial('COM5', 9600)  # Ganti COM sesuai dengan Arduino kamu
print("Terhubung ke Arduino...")

# Variabel untuk menyimpan status
rotation_counter = 0
last_sent_bearing = -1
last_move_time = time.time()
debounce_time = 0.3  # dalam detik: waktu jeda dianggap selesai berputar

# Fungsi menghitung bearing dari counter
def calculate_bearing(steps, steps_per_rev=200, microsteps=4):
    total_steps = steps_per_rev * microsteps
    bearing = (steps % total_steps) * (360 / total_steps)
    return round(bearing) % 360

# Handler untuk knob
def knob_handler(data):
    global rotation_counter, last_sent_bearing, last_move_time

    print(f"Data mentah: {data}")
    delta = data[2]
    button = data[1]

    # Interpretasi delta
    if delta == 1:
        rotation_counter += 1
        last_move_time = time.time()
    elif delta == 255:  # -1 dalam unsigned byte
        rotation_counter -= 1
        last_move_time = time.time()

    # Tombol (opsional)
    if button == 1:
        print("Tombol ditekan")

# Deteksi PowerMate
all_devices = hid.HidDeviceFilter().get_devices()
powermate = None
for device in all_devices:
    if "Griffin PowerMate" in device.product_name:
        powermate = device
        break

if not powermate:
    print("PowerMate tidak ditemukan.")
else:
    print("PowerMate ditemukan, memulai listener...")
    powermate.open()
    powermate.set_raw_data_handler(knob_handler)

    try:
        while True:
            time.sleep(0.05)  # Cegah CPU 100%
            elapsed = time.time() - last_move_time

            # Kirim bearing hanya saat sudah tidak ada gerakan
            if elapsed > debounce_time:
                bearing = calculate_bearing(rotation_counter)
                if bearing != last_sent_bearing:
                    print(f"[Bearing akhir dikirim: {bearing}°]")
                    arduino.write((str(bearing) + '\n').encode())
                    last_sent_bearing = bearing

    except KeyboardInterrupt:
        print("Program dihentikan.")
    finally:
        powermate.close()
        arduino.close()
