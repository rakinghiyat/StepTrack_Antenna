#include <Arduino.h>
#include "A4988.h"

const int Step = 9;
const int Dir = 8;
const int Sleep = 10;
const int MS1 = 13;
const int MS2 = 12;
const int MS3 = 11;

const int spr = 200;
const int Microsteps = 4;
const int RPM = 120;

A4988 stepper(spr, Dir, Step, MS1, MS2, MS3);

void setup() {
  Serial.begin(115200);  // WAJIB supaya bisa menerima dari Python
  pinMode(Sleep, OUTPUT);
  digitalWrite(Sleep, HIGH);
  stepper.begin(RPM, Microsteps);
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'R') stepper.move(1);
    else if (c == 'L') stepper.move(-1);
    else if (c == 'C') {
      // Reset bearing sekarang dilakukan di sisi Python
      // Tidak ada tindakan tambahan di Arduino
    }
  }
}
