# StepTrack_Antenna 🚀📡

A compact and innovative auto-tracking antenna system using a stepper motor, Arduino, and the Griffin PowerMate USB knob. Designed to control antenna bearing in real-time, this system is ideal for telemetry, ADS-B tracking, and IoT experiments.

---

## 🎯 Key Features

- 🔁 Precise stepper motor control based on bearing input
- 🎛️ Intuitive interface using Griffin PowerMate as a "direction wheel"
- 🧠 Real-time bearing calculation handled by Arduino
- 🔌 Serial communication between Python and Arduino
- 🛰️ Ready for integration with external ADS-B / VRS bearing sources

---

## 🛠️ System Architecture

Griffin PowerMate → Python → Serial → Arduino → Stepper Motor (via A4988) ↑ Serial Bearing Feedback

---

## 📦 Hardware & Tools

- Arduino Mega / Uno
- A4988 Stepper Motor Driver
- 200 SPR Stepper Motor
- Griffin PowerMate USB knob
- Python (with `pywinusb`, `pyserial`)
- 12V Power Supply
- Optional: Virtual Radar Server / ADS-B data feed

---

## 🚀 How It Works

1. **Rotate the Griffin PowerMate** — Python detects knob input and sends `R` (right) or `L` (left) via serial.
2. **Arduino receives command** — moves the stepper accordingly and updates internal bearing.
3. **Bearing is printed over serial** — ready for GUI or external program to visualize tracking.

---

## ✅ Project Goals / Roadmap

- [x] Real-time stepper control via Griffin knob
- [x] Local bearing tracking via Arduino
- [ ] Integration with external bearing (VRS / JSON)
- [ ] Real-time GUI dashboard
- [ ] Auto-reset to home bearing
- [ ] Toggle between Manual and Auto modes

---

## 🤝 Contributing

Pull requests are welcome! Feel free to fork and contribute — whether it's bug fixes, enhancements, or documentation.

---

## 📄 License

MIT License – Free to use, modify, and build upon for personal and educational purposes.

---

## 💡 Inspiration

This system was built out of necessity when conventional auto-tracking modules failed. It's a lightweight, low-cost, DIY solution that turns simple hardware into a smart, controllable tracker.

---

## 🔗 References

- **PowerMate Windows Interface Library**  
  This project uses [`powermate-win10`](https://github.com/alex-ong/powermate-win10) by [@alex-ong](https://github.com/alex-ong) as a base for reading Griffin PowerMate input in Python.  
  It's a lightweight and reliable solution for Windows systems and was crucial for enabling real-time knob input.


