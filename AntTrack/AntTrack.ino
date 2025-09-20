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

  stepper.run();
}

// --------------------
void processCommand(String cmd) {
  cmd.trim();

  if (cmd.startsWith("K")) {
    // Knob (relative steps → sama logic dengan stable)
    long deg = cmd.substring(1).toInt();
    long steps = deg * stepsPerDegree;

    targetSteps += steps;
    stepper.moveTo(targetSteps);
    sendFeedback();
  }
  else if (cmd.startsWith("S")) {
    // Manual relative steps
    long steps = cmd.substring(1).toInt();
    targetSteps += steps;
    stepper.moveTo(targetSteps);
    sendFeedback();
  }
  else if (cmd.startsWith("D")) {
    // Manual absolute degrees
    long targetDeg = cmd.substring(1).toInt();

    int rawAngle = encoder.rawAngle(); // 0–4095
    float currentDeg = (rawAngle * 360.0) / 4096.0;

    float deltaDeg = targetDeg - currentDeg;
    while (deltaDeg > 180) deltaDeg -= 360;
    while (deltaDeg < -180) deltaDeg += 360;

    long deltaSteps = deltaDeg * stepsPerDegree;
    targetSteps += deltaSteps;
    stepper.moveTo(targetSteps);

    sendFeedback();
  }
  else if (cmd == "C") {
    // Reset posisi
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
