#include <Arduino.h>
#include "A4988.h"

int Step = 9;
int Dire = 8;
int Sleep = 10;
int MS1 = 13;
int MS2 = 12;
int MS3 = 11;

const int spr = 200;  // Full steps per revolution
int RPM = 100;
int Microsteps = 4;

A4988 stepper(spr, Dire, Step, MS1, MS2, MS3);

float currentBearing = 0.0; // Posisi terakhir dalam derajat

void setup() {
  Serial.begin(9600);
  pinMode(Sleep, OUTPUT);
  digitalWrite(Sleep, HIGH); // Aktifkan driver

  stepper.begin(RPM, Microsteps);
  Serial.println("Siap menerima bearing dari Python (0–359)...");
}

void loop() {
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    float targetBearing = input.toFloat();

    // Validasi input
    if (targetBearing < 0.0 || targetBearing >= 360.0) {
      Serial.println("Input tidak valid. Masukkan angka 0–359.");
      return;
    }

    float delta = targetBearing - currentBearing;

    // Normalisasi ke -180 hingga +180 derajat
    if (delta > 180.0) delta -= 360.0;
    if (delta < -180.0) delta += 360.0;

    int totalMicrosteps = spr * Microsteps;
    int stepsToMove = round(abs(delta) / 360.0 * totalMicrosteps);
    int direction = delta > 0 ? 1 : -1;

    stepper.move(stepsToMove * direction);
    currentBearing = targetBearing;

    Serial.print("Pindah ke: ");
    Serial.println(currentBearing);
  }
}
