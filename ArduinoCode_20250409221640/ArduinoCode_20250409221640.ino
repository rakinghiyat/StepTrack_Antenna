#include <Wire.h>
#include <AS5600.h>
#include <A4988.h>
#include <math.h> // untuk round()

// Konfigurasi pin A4988
const int Step = 9;
const int Dir = 8;
const int Sleep = 10;
const int MS1 = 13;
const int MS2 = 12;
const int MS3 = 11;

const int spr = 200;          // Step per revolution
const int Microsteps = 4;     // Mikrostepping
const int RPM = 120;          // Kecepatan motor
const int stepDelay = 20;     // Delay antar langkah motor (ms)

AS5600 encoder;
A4988 stepper(spr, Dir, Step, MS1, MS2, MS3);

unsigned long lastSend = 0;
int lastRaw = -1;

void setup() {
  Serial.begin(115200);
  Wire.begin();
  encoder.begin();  // Inisialisasi komunikasi dengan AS5600

  pinMode(Sleep, OUTPUT);
  digitalWrite(Sleep, HIGH); // Aktifkan driver motor

  stepper.begin(RPM, Microsteps); // Inisialisasi motor
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    switch (c) {
      case 'R':
        stepper.move(1);  // Satu langkah searah jarum jam
        delay(stepDelay);
        sendRawValue();
        break;

      case 'L':
        stepper.move(-1); // Satu langkah berlawanan arah jarum jam
        delay(stepDelay);
        sendRawValue();
        break;

      case 'C':
        // Untuk reset atau fungsi lain di masa depan
        break;
    }
  }

  // Kirim pembacaan sudut setiap 100ms hanya jika berubah
  if (millis() - lastSend > 100) {
    sendRawValue();
    lastSend = millis();
  }
}

void sendRawValue() {
  int rawAngle = encoder.readAngle();  // Rentang 0–4095
  if (rawAngle != lastRaw) {
    lastRaw = rawAngle;
    float angleDeg = (rawAngle * 360.0) / 4096.0;

    Serial.print("Raw Angle: ");
    Serial.print(rawAngle);
    Serial.print(" | Angle (°): ");
    Serial.println(angleDeg, 2);
  }
}
