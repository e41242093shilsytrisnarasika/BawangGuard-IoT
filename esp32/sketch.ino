#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>

// ================= KONFIGURASI =================
const char* WIFI_SSID = "Valhala007";
const char* WIFI_PASS="";

// Gunakan URL Cloudflare Tunnel.
// Contoh:
// https://contoh-acak.trycloudflare.com/api/sensors/ingest
const char* API_URL =
 "https://URL-TUNNEL-ANDA.trycloudflare.com/api/sensors/ingest";

// ================= PIN =================
#define DHTPIN 4
#define DHTTYPE DHT22
#define SOIL_PIN 34

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C

// Kalibrasi sensor tanah
const int AIR_VALUE = 3200;
const int WATER_VALUE = 1400;

// ================= OBJECT =================
DHT dht(DHTPIN, DHTTYPE);
Adafruit_SSD1306 display(
  SCREEN_WIDTH,
  SCREEN_HEIGHT,
  &Wire,
  OLED_RESET
);

unsigned long lastSend = 0;
const unsigned long SEND_INTERVAL = 10000;

// ================= WIFI =================
void connectWiFi() {
  Serial.print("Menghubungkan WiFi");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  int attempt = 0;

  while (WiFi.status() != WL_CONNECTED && attempt < 30) {
    delay(500);
    Serial.print(".");
    attempt++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.println("WiFi connected");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println();
    Serial.println("WiFi gagal terhubung");
  }
}

// ================= OLED =================
void showDisplay(
  float suhu,
  float kelembaban,
  int soilRaw,
  int soilPercent,
  bool apiBerhasil
) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);

  display.println("BawangGuard");
  display.print("WiFi: ");
  display.println(
    WiFi.status() == WL_CONNECTED ? "Connected" : "Offline"
  );

  display.print("Temp: ");
  display.print(suhu, 1);
  display.println(" C");

  display.print("Hum : ");
  display.print(kelembaban, 1);
  display.println(" %");

  display.print("Soil: ");
  display.print(soilPercent);
  display.println(" %");

  display.print("API : ");
  display.println(apiBerhasil ? "OK" : "WAIT");

  display.display();
}

// ================= KIRIM API =================
bool sendToBackend(
  float suhu,
  float kelembaban,
  int soilPercent
) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[API] WiFi belum terhubung");
    return false;
  }

  HTTPClient http;

  Serial.println("[API] Menghubungkan ke backend...");
  http.begin(API_URL);
  http.addHeader("Content-Type", "application/json");

  String payload = "{";
  payload += "\"node_id\":\"VELXIO-01\",";
  payload += "\"soil_moisture\":" + String(soilPercent) + ",";
  payload += "\"soil_temp\":" + String(suhu, 2) + ",";
  payload += "\"soil_ph\":6.2,";
  payload += "\"air_temp\":" + String(suhu, 2) + ",";
  payload += "\"air_humidity\":" + String(kelembaban, 2) + ",";
  payload += "\"rainfall_mm\":0.0,";
  payload += "\"drainage_score\":0.8,";
  payload += "\"method\":\"fuzzy\"";
  payload += "}";

  Serial.println("[API] Payload:");
  Serial.println(payload);

  int httpCode = http.POST(payload);

  Serial.print("[API] HTTP status: ");
  Serial.println(httpCode);

  if (httpCode > 0) {
    String response = http.getString();
    Serial.println("[API] Response:");
    Serial.println(response);
    http.end();
    return httpCode >= 200 && httpCode < 300;
  }

  Serial.print("[API] Error: ");
  Serial.println(http.errorToString(httpCode));

  http.end();
  return false;
}

// ================= SETUP =================
void setup() {
  Serial.begin(115200);
  delay(1000);

  dht.begin();

  if (!display.begin(
        SSD1306_SWITCHCAPVCC,
        SCREEN_ADDRESS
      )) {
    Serial.println("OLED gagal dimulai");
  } else {
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.println("BawangGuard");
    display.println("Starting...");
    display.display();
  }

  connectWiFi();
}

// ================= LOOP =================
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi terputus. Reconnect...");
    connectWiFi();
  }

  float suhu = dht.readTemperature();
  float kelembaban = dht.readHumidity();

  if (isnan(suhu)) {
    suhu = 25.0;
  }

  if (isnan(kelembaban)) {
    kelembaban = 50.0;
  }

  int soilRaw = analogRead(SOIL_PIN);

  int soilPercent = map(
    soilRaw,
    AIR_VALUE,
    WATER_VALUE,
    0,
    100
  );

  soilPercent = constrain(soilPercent, 0, 100);

  Serial.println("========================");
  Serial.print("WiFi Status : ");
  Serial.println(
    WiFi.status() == WL_CONNECTED
      ? "Connected"
      : "Disconnected"
  );

  Serial.print("Suhu        : ");
  Serial.print(suhu, 2);
  Serial.println(" C");

  Serial.print("Kelembaban  : ");
  Serial.print(kelembaban, 2);
  Serial.println(" %");

  Serial.print("Soil Raw    : ");
  Serial.println(soilRaw);

  Serial.print("Soil Moisture: ");
  Serial.print(soilPercent);
  Serial.println(" %");

  bool apiBerhasil = false;

  if (millis() - lastSend >= SEND_INTERVAL) {
    apiBerhasil = sendToBackend(
      suhu,
      kelembaban,
      soilPercent
    );

    lastSend = millis();
  }

  showDisplay(
    suhu,
    kelembaban,
    soilRaw,
    soilPercent,
    apiBerhasil
  );

  delay(1000);
}
