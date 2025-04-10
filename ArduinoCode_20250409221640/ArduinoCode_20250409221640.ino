#include <Arduino.h>
#include "A4988.h"

int Step = 9;
int Dire  = 8;
int Sleep = 10;
int MS1 = 13;
int MS2 = 12;
int MS3 = 11;

const int spr = 200;
int RPM = 100;
int Microsteps = 4;

A4988 stepper(spr, Dire, Step, MS1, MS2, MS3);
int current_bearing = 0;

void setup() {
  Serial.begin(9600);
  pinMode(Sleep, OUTPUT);
  digitalWrite(Sleep, HIGH);
  stepper.begin(RPM, Microsteps);
}

void loop() {
  if (Serial.available()) {
    char input = Serial.read();
    if (input == 'R') {
      current_bearing += 1;
      stepper.rotate(1.8);
    }
    else if (input == 'L') {
      current_bearing -= 1;
      stepper.rotate(-1.8);
    }
    else if (input == 'C') {
      current_bearing = 0;
    }

    // Hitung bearing dalam derajat (0 - 359)
    int deg = ((int)(current_bearing * 1.8)) % 360;
    if (deg < 0) deg += 360; // Jaga agar tidak negatif

    Serial.print("Bearing: ");
    Serial.print(deg);
    Serial.println("°");
  }
}
