#define THERM_PIN   A1
#define LIGHT_PIN   A0
#define BUZZER_PIN  8
#define LED_PIN     9

#define TEMP_DANGER  25
#define LIGHT_DOOR   100
#define READ_INTERVAL 2000

unsigned long lastReadTime = 0;

float readTemp() {
  int raw = analogRead(THERM_PIN);
  if (raw >= 1023 || raw <= 0) return -999;
  float voltage = raw * 5.0 / 1023.0;
  float resistance = 35000.0 * voltage / (5.0 - voltage);
  float tK = 1.0 / (1.0/298.15 + (1.0/3950.0) * log(resistance/10000.0));
  return tK - 273.15;
}

void setup() {
  Serial.begin(9600);
  pinMode(A1, INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(LED_PIN, LOW);
  tone(BUZZER_PIN, 1000, 200);
  digitalWrite(LED_PIN, HIGH);
  delay(200);
  digitalWrite(LED_PIN, LOW);
  delay(1000);
}

void loop() {
  unsigned long now = millis();
  if (now - lastReadTime < READ_INTERVAL) return;
  lastReadTime = now;

  float temp = readTemp();
  int lightVal = analogRead(LIGHT_PIN);
  bool doorOpen = (lightVal > LIGHT_DOOR);
  bool tempDanger = (temp > TEMP_DANGER);

  if (tempDanger) {
    tone(BUZZER_PIN, 1000);
    digitalWrite(LED_PIN, HIGH);
  } else if (doorOpen) {
    tone(BUZZER_PIN, 2000);
    digitalWrite(LED_PIN, HIGH);
  } else {
    noTone(BUZZER_PIN);
    digitalWrite(LED_PIN, LOW);
  }

  Serial.print("{\"temp\":");
  Serial.print(temp, 1);
  Serial.print(",\"light\":");
  Serial.print(lightVal);
  Serial.print(",\"door\":");
  Serial.print(doorOpen ? 1 : 0);
  Serial.println("}");
}