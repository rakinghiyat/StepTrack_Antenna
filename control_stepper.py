from pywinusb import hid
import serial

# Inisialisasi koneksi serial ke Arduino
arduino = serial.Serial('COM5', 9600)  # Ganti sesuai port kamu
print("Terhubung ke Arduino...")

current_bearing = 0  # Simpan bearing secara lokal di Python

def update_bearing_display():
    global current_bearing
    deg = current_bearing % 360
    print(f"[Python] Bearing: {deg}°")

def knob_handler(data):
    global current_bearing
    print(f"Data mentah: {data}")

    button = data[1]
    delta = data[2]

    if delta == 1:
        print("Knob diputar searah jarum jam (+1)")
        arduino.write(b'R')
        current_bearing += 1
        update_bearing_display()
    elif delta == 255:
        print("Knob diputar berlawanan arah jarum jam (-1)")
        arduino.write(b'L')
        current_bearing -= 1
        update_bearing_display()

    if button == 1:
        print("Tombol ditekan")
        arduino.write(b'C')
        current_bearing = 0
        update_bearing_display()

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
            pass
    except KeyboardInterrupt:
        print("Program dihentikan.")
    finally:
        powermate.close()
        arduino.close()
