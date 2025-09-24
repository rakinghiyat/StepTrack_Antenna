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

// Toleransi (deg) hanya untuk perintah D dan S
const float toleranceDeg = 1.0;

long targetSteps = 0;

// --- Deteksi sensor vs command ---
int lastRawAngle = 0;
int lastCommandRaw = 0;
bool motorActive = false;
bool motorPrevActive = false;
bool motorCommandActive = false; // motor bergerak karena perintah
bool pendingKFeedback = false;    // flag untuk K: tunggu sampai selesai
unsigned long lastSensorCheck = 0;
unsigned long lastStopFeedback = 0;
const unsigned long gracePeriodMs = 50;  // waktu tunggu setelah motor berhenti

void setup() {
  Serial.begin(115200);
  Wire.begin();
  encoder.begin();

  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, LOW);

  stepper.setMaxSpeed(5000);
  stepper.setAcceleration(8000);

  lastRawAngle = encoder.rawAngle();
  lastCommandRaw = lastRawAngle;

  Serial.println("[ARDUINO] Ready (Knob + Manual Relative + Manual Absolute)");
}

void loop() {
  // Baca command dari Python
  while (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    processCommand(cmd);
  }

  // Update status motor
  motorPrevActive = motorActive;
  motorActive = (stepper.distanceToGo() != 0);
  stepper.run();

  // Kirim feedback terakhir setelah motor berhenti (grace period)
  if (!motorActive && motorPrevActive) {
    lastStopFeedback = millis();
  }
  if (!motorActive && (millis() - lastStopFeedback < gracePeriodMs)) {
    // Hanya cetak K jika pendingKFeedback true
    if (pendingKFeedback) {
      sendFeedback();
      pendingKFeedback = false;
      lastCommandRaw = encoder.rawAngle(); // update raw terakhir setelah berhenti
    }
    lastStopFeedback = 0;
  }

  // Deteksi gerakan liar (no cmd) hanya jika motor diam
  checkSensor();
}

// --------------------
void processCommand(String cmd) {
  cmd.trim();

  if (cmd.startsWith("K")) {
    long deg = cmd.substring(1).toInt();
    long steps = deg * stepsPerDegree;
    targetSteps += steps;
    stepper.moveTo(targetSteps);
    motorCommandActive = true;
    pendingKFeedback = true; // tunggu sampai selesai baru cetak feedback
    // jangan langsung kirim feedback
  }
  else if (cmd.startsWith("S") || cmd.startsWith("D")) {
    long deltaSteps = 0;
    float deltaDeg = 0;

    if (cmd.startsWith("S")) {
      deltaSteps = cmd.substring(1).toInt();
      deltaDeg = deltaSteps / stepsPerDegree;
    } else if (cmd.startsWith("D")) {
      long targetDeg = cmd.substring(1).toInt();
      int rawAngle = encoder.rawAngle();
      float currentDeg = (rawAngle * 360.0) / 4096.0;
      deltaDeg = targetDeg - currentDeg;
      while (deltaDeg > 180) deltaDeg -= 360;
      while (deltaDeg < -180) deltaDeg += 360;
      deltaSteps = deltaDeg * stepsPerDegree;
    }

    if (fabs(deltaDeg) < toleranceDeg) {
      sendFeedback();
      lastCommandRaw = encoder.rawAngle();
      return;
    }

    targetSteps += deltaSteps;
    stepper.moveTo(targetSteps);
    stepper.runToPosition();
    sendFeedback();
    lastCommandRaw = encoder.rawAngle();
  }
  else if (cmd == "C") {
    int rawAngle = encoder.rawAngle();
    float currentDeg = (rawAngle * 360.0) / 4096.0;

    float deltaDeg = -currentDeg;
    while (deltaDeg > 180) deltaDeg -= 360;
    while (deltaDeg < -180) deltaDeg += 360;

    long deltaSteps = deltaDeg * stepsPerDegree;
    targetSteps += deltaSteps;
    stepper.moveTo(targetSteps);
    stepper.runToPosition();

    stepper.setCurrentPosition(0);
    targetSteps = 0;
    sendFeedback();
    lastCommandRaw = encoder.rawAngle();
  }
}

// --------------------
void sendFeedback() {
  int rawAngle = encoder.rawAngle();
  float angleDeg = (rawAngle * 360.0) / 4096.0;

  Serial.print(rawAngle);
  Serial.print(",");
  Serial.println(angleDeg, 2);
}

// --------------------
void checkSensor() {
  unsigned long now = millis();
  if (now - lastSensorCheck < 50) return; // cek tiap 50ms
  lastSensorCheck = now;

  int raw = encoder.rawAngle();
  int deltaRaw = abs(raw - lastRawAngle);

  // Threshold noise stepper kecil
  if (deltaRaw > 2) {
    // hanya catat sensor jika motor diam
    int deltaCommand = abs(raw - lastCommandRaw);
    if (!motorActive && deltaCommand > 2) {
      float angleDeg = (raw * 360.0) / 4096.0;
      Serial.print("[SENSOR],");
      Serial.print(raw);
      Serial.print(",");
      Serial.println(angleDeg, 2);
    }
  }

  lastRawAngle = raw;
}
