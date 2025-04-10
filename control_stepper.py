from pywinusb import hid
import serial
import threading
import sys

# Inisialisasi koneksi serial ke Arduino
arduino = serial.Serial('COM5', 9600)  # Ganti 'COM5' sesuai port kamu
print("Terhubung ke Arduino...")

# Fungsi untuk membaca data serial dari Arduino secara paralel
def baca_serial():
    while True:
        if arduino.in_waiting:
            data = arduino.readline().decode().strip()
            if "Bearing" in data:
                # Bersihkan baris sebelumnya dan cetak bearing terakhir
                sys.stdout.write('\r' + ' ' * 40 + '\r')  # Clear line
                sys.stdout.write(f"{data}")
                sys.stdout.flush()

# Jalankan thread pembacaan serial
serial_thread = threading.Thread(target=baca_serial, daemon=True)
serial_thread.start()

# Fungsi handler untuk knob
def knob_handler(data):
    print(f"Data mentah: {data}")

    button = data[1]
    delta = data[2]

    if delta == 1:
        print("Knob diputar searah jarum jam (+1)")
        arduino.write(b'R')
    elif delta == 255:  # -1 dalam unsigned byte
        print("Knob diputar berlawanan arah jarum jam (-1)")
        arduino.write(b'L')

    if button == 1:
        print("Tombol ditekan")
        # Bisa ditambahkan: arduino.write(b'C')

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
            pass  # Tetap hidup
    except KeyboardInterrupt:
        print("Program dihentikan.")
    finally:
        powermate.close()
        arduino.close()
