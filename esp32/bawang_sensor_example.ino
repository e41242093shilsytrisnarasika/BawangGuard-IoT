/*
  Contoh sketch ESP32 → BawangGuard IoT
  Ganti WIFI_SSID, WIFI_PASS, dan SERVER_URL sesuai jaringan Anda.
  Endpoint: POST /api/sensors/ingest
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

const char* WIFI_SSID = "NAMA_WIFI";
const char* WIFI_PASS = "PASSWORD_WIFI";
const char* SERVER_URL = "http://192.168.1.10:8000/api/sensors/ingest";

void setup() {
  Serial.begin(115200);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
}

void loop() {
  // Ganti dengan pembacaan sensor nyata (ADC kelembapan, DHT22, pH probe)
  float soilMoisture = 60.0;
  float soilTemp = 28.0;
  float soilPh = 6.0;
  float airTemp = 29.0;
  float airHumidity = 70.0;

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(SERVER_URL);
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<256> doc;
    doc["node_id"] = "NODE-01";
    doc["soil_moisture"] = soilMoisture;
    doc["soil_temp"] = soilTemp;
    doc["soil_ph"] = soilPh;
    doc["air_temp"] = airTemp;
    doc["air_humidity"] = airHumidity;
    doc["drainage_score"] = 0.8;
    doc["method"] = "fuzzy";

    String body;
    serializeJson(doc, body);
    int code = http.POST(body);
    Serial.printf("HTTP %d\n", code);
    http.end();
  }
  delay(60000); // kirim tiap 60 detik
}
