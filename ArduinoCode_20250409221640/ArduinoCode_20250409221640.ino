#include <Wire.h>
#include <AS5600.h>
#include <A4988.h>
#include <math.h> // untuk round()

const int Step = 9;
const int Dir = 8;
const int Sleep = 10;
const int MS1 = 13;
const int MS2 = 12;
const int MS3 = 11;

const int spr = 200;
const int Microsteps = 4;
const int RPM = 120;

AS5600 encoder;
A4988 stepper(spr, Dir, Step, MS1, MS2, MS3);

unsigned long lastSend = 0;
int lastRaw = -1;

void setup() {
  Serial.begin(115200);
  Wire.begin();
  encoder.begin();  // Mulai komunikasi dengan AS5600
  pinMode(Sleep, OUTPUT);
  digitalWrite(Sleep, HIGH);
  stepper.begin(RPM, Microsteps);
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'R') {
      stepper.move(1);  // gerakkan motor satu langkah
      sendRawValue();   // kirimkan nilai raw setelah motor bergerak
    }
    else if (c == 'L') {
      stepper.move(-1);  // gerakkan motor satu langkah berlawanan arah
      sendRawValue();    // kirimkan nilai raw setelah motor bergerak
    }
    else if (c == 'C') {
      // reset jika diperlukan
    }
  }

  // Cek raw angle setiap 50ms (mempercepat pembacaan)
  if (millis() - lastSend > 50) {
    sendRawValue();
    lastSend = millis();
  }
}

int lastRawAngle = -1;  // Variabel untuk menyimpan nilai RAW sebelumnya

void sendRawValue() {
  // Baca angle sensor
  int rawAngle = encoder.readAngle();  // 0–4095
  float angleDeg = (rawAngle * 360.0) / 4096.0;

  // Hanya kirim jika ada perubahan pada rawAngle
  if (rawAngle != lastRawAngle) {
    // Kirim hanya nilai raw dan sudut (tanpa print di serial monitor)
    Serial.print("Raw Angle: ");
    Serial.print(rawAngle);  // Kirim nilai RAW
    Serial.print(" | Angle (°): ");
    Serial.println(angleDeg, 2);  // Kirim nilai Angle dalam derajat
    lastRawAngle = rawAngle;  // Update nilai rawAngle yang terakhir
  }
}
