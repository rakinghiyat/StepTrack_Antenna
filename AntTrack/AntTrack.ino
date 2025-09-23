#include <AccelStepper.h>
#include <Wire.h>
#include <AS5600.h>

// --- Pin TMC2209 ---
#define DIR_PIN     8
#define STEP_PIN    9
#define EN_PIN      10

AccelStepper stepper(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);
AS5600 encoder;

// Stepper config
const int stepsPerRev = 200;
const int microstep   = 16;
const float stepsPerDegree = (stepsPerRev * microstep) / 360.0;

// --------------------
// Toleransi (dalam derajat) hanya untuk perintah D dan S
const float toleranceDeg = 1.0;  

long targetSteps = 0;  // posisi target (absolute)

void setup() {
  Serial.begin(115200);
  Wire.begin();
  encoder.begin();

  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, LOW); // enable driver

  stepper.setMaxSpeed(5000);
  stepper.setAcceleration(8000);

  Serial.println("[ARDUINO] Ready (Knob + Manual Relative + Manual Absolute)");
}

void loop() {
  // Baca command dari Python
  while (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    processCommand(cmd);
  }

  // Knob movement tetap realtime
  stepper.run();
}

// --------------------
void processCommand(String cmd) {
  cmd.trim();

  if (cmd.startsWith("K")) {
    // Knob (relative steps, realtime)
    long deg = cmd.substring(1).toInt();
    long steps = deg * stepsPerDegree;

    targetSteps += steps;
    stepper.moveTo(targetSteps);

    // Kirim log posisi terakhir, tapi motor tetap berjalan
    sendFeedback();
  }
  else if (cmd.startsWith("S") || cmd.startsWith("D")) {
    // Manual input → tunggu sampai motor sampai target
    long deltaSteps = 0;
    float deltaDeg = 0;

    if (cmd.startsWith("S")) {
      deltaSteps = cmd.substring(1).toInt();
      deltaDeg = deltaSteps / stepsPerDegree;
    }
    else if (cmd.startsWith("D")) {
      long targetDeg = cmd.substring(1).toInt();
      int rawAngle = encoder.rawAngle(); // 0–4095
      float currentDeg = (rawAngle * 360.0) / 4096.0;
      deltaDeg = targetDeg - currentDeg;
      while (deltaDeg > 180) deltaDeg -= 360;
      while (deltaDeg < -180) deltaDeg += 360;
      deltaSteps = deltaDeg * stepsPerDegree;
    }

    // Terapkan toleransi
    if (fabs(deltaDeg) < toleranceDeg) {
      // Tidak usah gerak, tapi tetap kirim feedback
      sendFeedback();
      return;
    }

    targetSteps += deltaSteps;
    stepper.moveTo(targetSteps);

    // Tunggu sampai motor sampai
    stepper.runToPosition();

    // Kirim log posisi akhir (bearing akurat)
    sendFeedback();
  }
  else if (cmd == "C") {
    // Ambil posisi sekarang
    int rawAngle = encoder.rawAngle(); // 0–4095
    float currentDeg = (rawAngle * 360.0) / 4096.0;

    // Hitung delta untuk ke 0°
    float deltaDeg = -currentDeg;
    while (deltaDeg > 180) deltaDeg -= 360;
    while (deltaDeg < -180) deltaDeg += 360;

    long deltaSteps = deltaDeg * stepsPerDegree;

    targetSteps += deltaSteps;
    stepper.moveTo(targetSteps);

    // Jalanin sampai benar-benar sampai 0°
    stepper.runToPosition();

    // Setelah sampai → set current posisi sebagai 0
    stepper.setCurrentPosition(0);
    targetSteps = 0;

    sendFeedback();
  }
}

// --------------------
void sendFeedback() {
  int rawAngle = encoder.rawAngle(); // 0–4095
  float angleDeg = (rawAngle * 360.0) / 4096.0;

  Serial.print(rawAngle);
  Serial.print(",");
  Serial.println(angleDeg, 2);
}
