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

Griffin PowerMate → Python → Serial → Arduino → Stepper Motor (via A4988 or TMC2209) ↑ Serial Bearing Feedback

---

## 📦 Hardware & Tools

- Arduino Mega / Uno (for motor & sensor control)
- A4988 / TMC2209 Stepper Motor Driver  
  (TMC2209 = silent & UART features, A4988 = simple & cheap)
- 200 SPR stepper motor (1.8°/step),  
  up to 3200 microsteps/rev at 1/16 microstepping
- Griffin PowerMate USB knob (manual input)
- Python (with `pywinusb`, `pyserial`; future GUI with `tkinter`/`PyQt5`)
- 12V Power Supply (≥2A recommended, depends on motor)
- Optional: Virtual Radar Server / ADS-B data feed
- Optional: RF RSSI module (for signal-based tracking)

---

## 🚀 How It Works

1. Rotate the Griffin PowerMate — Python detects knob rotation and sends commands (`K`, `S`, `D`, or `C`) to Arduino.
2. Arduino interprets the command:
   - `K`: knob input → relative movement (non-blocking, real-time)
   - `S`: manual relative steps (blocking, until reached)
   - `D`: manual absolute degree target (blocking, until reached)
   - `C`: reset current bearing to 0°
3. Arduino drives the stepper motor accordingly, using encoder feedback for precise control.
4. Arduino prints feedback (`rawAngle, angleDeg`) over serial, which can be logged or visualized.

---

## ✅ Project Goals / Roadmap

### Core Features
- [x] Real-time stepper control via Griffin knob
- [x] Local bearing tracking via Arduino
- [x] Auto-reset to home bearing
- [ ] Real-time GUI dashboard
- [ ] Mode selection between Manual and Auto modes

### Advanced Features
- [ ] Integration with external bearing (VRS/JSON)
- [ ] Automatic tracking using RSSI signal input
- [ ] Multi-source input fusion (ADS-B + RSSI + manual)

### Reliability & Usability
- [x] Enhanced logging with timestamps
- [ ] Error detection & auto-correction (missed steps, encoder drift)
- [ ] Cross-platform GUI support

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


