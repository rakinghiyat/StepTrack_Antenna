#include <AccelStepper.h>
#include <Wire.h>
#include <AS5600.h>
#include <HMC5883L.h>   // Library HMC5883L

// --- Pin TMC2209 ---
#define DIR_PIN     8
#define STEP_PIN    9
#define EN_PIN      10

AccelStepper stepper(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);
AS5600 encoder;
HMC5883L compass;      // Objek kompas

// Stepper config
const int stepsPerRev = 200;
const int microstep   = 16;
const float stepsPerDegree = (stepsPerRev * microstep) / 360.0;

// Toleransi (deg)
const float toleranceDeg = 1.0;

long targetSteps = 0;

// --- Deteksi motor & sensor ---
int lastRawAngle = 0;
int lastCommandRaw = 0;
bool motorActive = false;
bool motorPrevActive = false;
bool waitingKDone = false;
unsigned long lastSensorCheck = 0;

void setup() {
  Serial.begin(115200);
  Wire.begin();

  // --- AS5600 ---
  encoder.begin();

  // --- HMC5883L ---
  if (!compass.begin()) {
    Serial.println("[ERROR] HMC5883L tidak terdeteksi!");
  } else {
    compass.setRange(HMC5883L_RANGE_1_3GA);         // Range default
    compass.setMeasurementMode(HMC5883L_CONTINOUS);
    compass.setDataRate(HMC5883L_DATARATE_30HZ);    // 30Hz refresh
    compass.setSamples(HMC5883L_SAMPLES_8);         // sampling rata-rata
    Serial.println("[HMC5883L] OK");
  }

  // --- Stepper ---
  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, LOW);
  stepper.setMaxSpeed(15000);      // knob cepat
  stepper.setAcceleration(30000);  // knob cepat

  lastRawAngle = encoder.rawAngle();
  lastCommandRaw = lastRawAngle;

  Serial.println("[ARDUINO] READY !");
}

void loop() {
  while (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    processCommand(cmd);
  }

  motorPrevActive = motorActive;
  motorActive = (stepper.distanceToGo() != 0);
  stepper.run();

  if (!motorActive && motorPrevActive && waitingKDone) {
    sendFeedback("K");
    waitingKDone = false;
    lastCommandRaw = encoder.rawAngle();
  }

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
    sendFeedback("K");
    waitingKDone = true;
  }
  else if (cmd.startsWith("S")) {
    long deltaSteps = cmd.substring(1).toInt();
    float deltaDeg = deltaSteps / stepsPerDegree;

    if (fabs(deltaDeg) < toleranceDeg) {
      sendFeedback("S-SKIP");
      lastCommandRaw = encoder.rawAngle();
      return;
    }

    targetSteps += deltaSteps;
    stepper.moveTo(targetSteps);
    stepper.runToPosition();
    sendFeedback("S");
    lastCommandRaw = encoder.rawAngle();
  }
  else if (cmd.startsWith("D")) {
    long targetDeg = cmd.substring(1).toInt();

    if (targetDeg < 0 || targetDeg > 360) {
      sendFeedback("D-SKIP");
      lastCommandRaw = encoder.rawAngle();
      return;
    }

    int rawAngle = encoder.rawAngle();
    float currentDeg = (rawAngle * 360.0) / 4096.0;
    float deltaDeg = targetDeg - currentDeg;
    while (deltaDeg > 180) deltaDeg -= 360;
    while (deltaDeg < -180) deltaDeg += 360;

    if (fabs(deltaDeg) < toleranceDeg) {
      sendFeedback("D-SKIP");
      lastCommandRaw = encoder.rawAngle();
      return;
    }

    long deltaSteps = deltaDeg * stepsPerDegree;
    targetSteps += deltaSteps;
    stepper.moveTo(targetSteps);
    stepper.runToPosition();
    sendFeedback("D");
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
    sendFeedback("C");
    lastCommandRaw = encoder.rawAngle();
  }
  else if (cmd == "Q") {
    sendFeedback("Q");
    lastCommandRaw = encoder.rawAngle();
  }
}

// --------------------
void sendFeedback(const char* label) {
  int rawAngle = encoder.rawAngle();
  float angleDeg = (rawAngle * 360.0) / 4096.0;

  // --- Data HMC5883L ---
  Vector norm = compass.readNormalize();
  float heading = atan2(norm.YAxis, norm.XAxis) * 180.0 / PI;
  if (heading < 0) heading += 360.0;   // Normalisasi ke 0–360

  Serial.print("[");
  Serial.print(label);
  Serial.print("],");
  Serial.print(rawAngle);
  Serial.print(",");
  Serial.print(angleDeg, 2);
  Serial.print(",");
  Serial.println(heading, 2);
}


// --------------------
void checkSensor() {
  unsigned long now = millis();
  if (now - lastSensorCheck < 50) return;
  lastSensorCheck = now;

  int raw = encoder.rawAngle();
  int deltaRaw = abs(raw - lastRawAngle);

  float deltaDeg = ((raw - lastCommandRaw) * 360.0 / 4096.0);
  while (deltaDeg > 180) deltaDeg -= 360;
  while (deltaDeg < -180) deltaDeg += 360;
  deltaDeg = fabs(deltaDeg);

  if (deltaRaw > 2 && deltaDeg > toleranceDeg) {
    if (!motorActive) {
      float angleDeg = (raw * 360.0) / 4096.0;

      Vector norm = compass.readNormalize();
      float heading = atan2(norm.YAxis, norm.XAxis) * 180.0 / PI;
      if (heading < 0) heading += 360.0;

      Serial.print("[SENSOR],AS5600,");
      Serial.print(raw);
      Serial.print(",");
      Serial.print(angleDeg, 2);
      Serial.print(",HMC5883L,");
      Serial.println(heading, 2);
    }
  }

  lastRawAngle = raw;
}
