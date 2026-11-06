
/*
  GLUCOSENSE - ESP32 INTEGRATED FIRMWARE

  OLED:
    Page 0: Initialization
    Page 1: Live Sensor Readings
    Page 2: Sensor Connection Status

  Button:
    GPIO18 -> GND (INPUT_PULLUP)
    First press  : Initialization -> Readings
    Second press : Readings -> Status
    Next presses : Readings <-> Status

  Hardware:
    ESP32 DevKit V1
    AS7343      : 0x59
    MAX30102    : I2C
    MLX90614    : 0x5A
    ADS1115     : 0x48
    SSD1306     : 0x3C

  I2C:
    SDA = GPIO21
    SCL = GPIO22

  LEDs:
    850nm = GPIO25
    940nm = GPIO26

  Research prototype only.
  Not clinically validated.
*/

// =====================================================
// LIBRARIES
// =====================================================

#include <WiFi.h>
#include <WiFiClient.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <time.h>
#include <ArduinoJson.h>
#include <WebServer.h>

#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_AS7343.h>
#include <MAX30105.h>
#include <Adafruit_MLX90614.h>
#include <Adafruit_ADS1X15.h>


// =====================================================
// CONFIGURATION - CHANGE THESE VALUES
// =====================================================

const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

const char* API_BASE = "http://10.46.89.210:8000";

const char* DEVICE_API_KEY = "YOUR_DEVICE_API_KEY";

const char* DEVICE_ID = "glucosense-01";


// =====================================================
// PINS AND ADDRESSES
// =====================================================

#define I2C_SDA 21
#define I2C_SCL 22

#define BUTTON_PIN 18

#define LED_850_PIN 25
#define LED_940_PIN 26

#define OLED_ADDR 0x3C
#define AS7343_ADDR 0x59
#define ADS1115_ADDR 0x48

// Avoid library macro conflict
#define MLX_I2C_ADDRESS 0x5A


// =====================================================
// TIMING
// =====================================================

#define SENSOR_INTERVAL_MS 500
#define DISPLAY_INTERVAL_MS 100

#define LED_CAPTURE_INTERVAL_MS 1500

#define SEND_INTERVAL_MS 5000
#define BACKEND_INTERVAL_MS 5000
#define WIFI_RETRY_INTERVAL_MS 10000

#define BUTTON_DEBOUNCE_MS 25


// =====================================================
// HARDWARE OBJECTS
// =====================================================

Adafruit_SSD1306 display(128, 64, &Wire, -1);

WebServer server(80);

Adafruit_AS7343 as7343;

MAX30105 max30102;

Adafruit_MLX90614 mlx90614;

Adafruit_ADS1115 ads1115;


// =====================================================
// SENSOR STATUS
// =====================================================

bool oledReady = false;

bool asReady = false;
bool maxReady = false;
bool mlxReady = false;
bool adsReady = false;

volatile bool backendConnected = false;


// =====================================================
// SENSOR DATA
// =====================================================

float channels[12] = {0};

float nirValue = 0;
float visValue = 0;

float led850Proxy = -1;
float led940Proxy = -1;

float objectTempC = NAN;
float ambientTempC = NAN;

float adcVolts[4] = {NAN, NAN, NAN, NAN};

int16_t adcRaw[4] = {0, 0, 0, 0};

uint32_t maxRed = 0;
uint32_t maxIR = 0;


// =====================================================
// OLED PAGE CONTROL
// =====================================================

uint8_t displayPage = 0;

bool lastButtonReading = HIGH;
bool stableButtonState = HIGH;

uint32_t lastDebounceTime = 0;


// =====================================================
// TIMERS
// =====================================================

uint32_t lastSensorRead = 0;
uint32_t lastDisplay = 0;
uint32_t lastLedCapture = 0;

uint32_t lastHttpStatus = 0;

String wifiIp = "--";
bool wifiInfoPrinted = false;


// =====================================================
// HELPER FUNCTIONS
// =====================================================

float safeFloat(float value) {

  if (!isfinite(value)) {
    return 0.0f;
  }

  return value;
}


void allLedsOff() {

  digitalWrite(LED_850_PIN, LOW);
  digitalWrite(LED_940_PIN, LOW);
}


// =====================================================
// OLED INITIALIZATION SCREEN
// =====================================================

void showInitialization(const char* message) {

  if (!oledReady) return;

  display.clearDisplay();

  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  display.setCursor(0, 0);

  display.println("GLUCOSENSE");
  display.println("---------------------");

  display.println("SYSTEM INITIALIZING");

  display.println();

  display.println(message);

  display.println();

  display.println("Please wait...");

  display.display();
}


// =====================================================
// WIFI - NON BLOCKING
// =====================================================

void connectWiFi() {

  WiFi.mode(WIFI_STA);

  WiFi.setSleep(false);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.println("WiFi connection started");
}


// =====================================================
// OLED INITIALIZATION
// =====================================================

void initDisplay() {

  oledReady = display.begin(
    SSD1306_SWITCHCAPVCC,
    OLED_ADDR
  );

  if (!oledReady) {

    Serial.println("OLED ERROR");

    return;
  }

  display.clearDisplay();

  display.setTextColor(SSD1306_WHITE);

  display.setTextSize(1);

  showInitialization("Starting ESP32...");

  Serial.println("OLED initialized");
}


// =====================================================
// SENSOR INITIALIZATION
// =====================================================

void initSensors() {

  showInitialization("Initializing AS7343...");

  asReady = as7343.begin(
    AS7343_ADDR,
    &Wire
  );

  Serial.printf(
    "AS7343: %s\n",
    asReady ? "OK" : "ERROR"
  );


  showInitialization("Initializing MAX30102...");

  maxReady = max30102.begin(
    Wire,
    I2C_SPEED_STANDARD
  );

  if (maxReady) {

    max30102.setup();

    max30102.setPulseAmplitudeRed(0x1F);

    max30102.setPulseAmplitudeIR(0x1F);

    max30102.setPulseAmplitudeGreen(0);
  }

  Serial.printf(
    "MAX30102: %s\n",
    maxReady ? "OK" : "ERROR"
  );


  showInitialization("Initializing MLX90614...");

  mlxReady = mlx90614.begin(
    MLX_I2C_ADDRESS,
    &Wire
  );

  Serial.printf(
    "MLX90614: %s\n",
    mlxReady ? "OK" : "ERROR"
  );


  showInitialization("Initializing ADS1115...");

  adsReady = ads1115.begin(
    ADS1115_ADDR,
    &Wire
  );

  if (adsReady) {

    ads1115.setGain(GAIN_ONE);
  }

  Serial.printf(
    "ADS1115: %s\n",
    adsReady ? "OK" : "ERROR"
  );
}


// =====================================================
// AS7343 SENSOR READING
// =====================================================

bool readAS7343() {

  if (!asReady) return false;

  uint16_t values[12] = {0};

  if (!as7343.readAllChannels(values)) {

    return false;
  }

  for (int i = 0; i < 12; i++) {

    channels[i] = values[i];
  }

  // Relative VIS indicator
  visValue = 0;

  for (int i = 0; i < 8; i++) {

    visValue += channels[i];
  }

  visValue /= 8.0f;

  // Verify channel mapping with the AS7343 library.
  nirValue = channels[9];

  return true;
}


// =====================================================
// LED OPTICAL CAPTURE
// =====================================================

bool captureLedProxy(
  int pin,
  float &proxy
) {

  if (!asReady) return false;

  allLedsOff();

  delay(10);

  digitalWrite(pin, HIGH);

  delay(35);

  bool ok = readAS7343();

  allLedsOff();

  if (!ok) return false;

  float total = 0;

  for (int i = 0; i < 6; i++) {

    total += channels[i];
  }

  proxy = total / 6.0f;

  return true;
}


// =====================================================
// READ MAX30102
// =====================================================

void readMAX30102() {

  if (!maxReady) return;

  max30102.check();

  maxRed = max30102.getRed();

  maxIR = max30102.getIR();
}


// =====================================================
// READ MLX90614
// =====================================================

void readMLX90614() {

  if (!mlxReady) return;

  objectTempC = mlx90614.readObjectTempC();

  ambientTempC = mlx90614.readAmbientTempC();
}


// =====================================================
// READ ADS1115
// =====================================================

void readADS1115() {

  if (!adsReady) return;

  for (int i = 0; i < 4; i++) {

    adcRaw[i] = ads1115.readADC_SingleEnded(i);

    adcVolts[i] = ads1115.computeVolts(
      adcRaw[i]
    );
  }
}


// =====================================================
// READ ALL SENSORS
// =====================================================

void readAllSensors() {

  readAS7343();

  readMAX30102();

  readMLX90614();

  readADS1115();

  allLedsOff();

  Serial.printf(
    "NIR: %.0f | VIS: %.0f | RED: %lu | IR: %lu | TEMP: %.2f\n",
    nirValue,
    visValue,
    (unsigned long)maxRed,
    (unsigned long)maxIR,
    safeFloat(objectTempC)
  );

  lastSensorRead = millis();
}


// =====================================================
// PERIODIC LED CAPTURE
// =====================================================

void updateLEDMeasurements() {

  if (!asReady) return;

  if (
    millis() - lastLedCapture <
    LED_CAPTURE_INTERVAL_MS
  ) {
    return;
  }

  lastLedCapture = millis();

  captureLedProxy(
    LED_850_PIN,
    led850Proxy
  );

  captureLedProxy(
    LED_940_PIN,
    led940Proxy
  );

  allLedsOff();
}
// =====================================================
// ESP32 LOCAL API - LIVE SENSOR DATA
// =====================================================

void handleData() {

  StaticJsonDocument<2048> doc;

  doc["status"] = "ok";
  doc["device_id"] = DEVICE_ID;

  // Sensor connection status
  doc["as7343Ready"] = asReady;
  doc["max30102Ready"] = maxReady;
  doc["mlx90614Ready"] = mlxReady;
  doc["ads1115Ready"] = adsReady;
  doc["oledReady"] = oledReady;

  // AS7343 readings
  doc["nir"] = nirValue;
  doc["vis"] = visValue;

  // MAX30102 readings
  doc["red"] = maxRed;
  doc["ir"] = maxIR;

  // Temperature
  doc["objectTempC"] = safeFloat(objectTempC);
  doc["ambientTempC"] = safeFloat(ambientTempC);

  // ADS1115 readings
  JsonArray raw = doc.createNestedArray("adcRaw");
  JsonArray volts = doc.createNestedArray("adcVolts");

  for (int i = 0; i < 4; i++) {
    raw.add(adcRaw[i]);
    volts.add(safeFloat(adcVolts[i]));
  }

  // AS7343 channels
  JsonArray ch = doc.createNestedArray("channels");

  for (int i = 0; i < 12; i++) {
    ch.add(channels[i]);
  }

  // LED readings
  doc["led850Proxy"] = safeFloat(led850Proxy);
  doc["led940Proxy"] = safeFloat(led940Proxy);

  // Network status
  doc["wifiConnected"] = WiFi.status() == WL_CONNECTED;
  doc["wifiIP"] = WiFi.localIP().toString();
  doc["backendConnected"] = backendConnected;

  // CORS for React/Vite frontend
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Cache-Control", "no-store");

  String response;
  serializeJson(doc, response);

  server.send(200, "application/json", response);
}

// =====================================================
// BACKEND HEALTH CHECK
// =====================================================

void checkBackend() {

  if (WiFi.status() != WL_CONNECTED) {

    backendConnected = false;

    return;
  }

  WiFiClient client;

  HTTPClient http;

  String url = String(API_BASE) + "/health";

  if (!http.begin(client, url)) {

    backendConnected = false;

    return;
  }

  http.setTimeout(1500);

  int code = http.GET();

  backendConnected = false;

  if (code == 200) {

    String response = http.getString();

    StaticJsonDocument<1024> doc;

    DeserializationError error =
      deserializeJson(doc, response);

    if (
      !error &&
      doc["database_connected"] == true
    ) {

      backendConnected = true;
    }
  }

  Serial.printf(
    "Backend: %s | HTTP: %d\n",
    backendConnected ? "CONNECTED" : "DISCONNECTED",
    code
  );

  http.end();
}


// =====================================================
// BUTTON CONTROL - FAST DEBOUNCE
// =====================================================

void handleButton() {

  bool reading = digitalRead(BUTTON_PIN);

  if (reading != lastButtonReading) {

    lastDebounceTime = millis();
  }

  if (
    millis() - lastDebounceTime >=
    BUTTON_DEBOUNCE_MS
  ) {

    if (reading != stableButtonState) {

      stableButtonState = reading;

      if (stableButtonState == LOW) {

        if (displayPage == 0) {

          displayPage = 1;
        }

        else if (displayPage == 1) {

          displayPage = 2;
        }

        else {

          displayPage = 1;
        }

        Serial.printf(
          "OLED PAGE: %u\n",
          displayPage
        );

        // Immediately refresh after button press.
        lastDisplay = 0;
      }
    }
  }

  lastButtonReading = reading;
}


// =====================================================
// OLED PAGE 1 - LIVE READINGS
// =====================================================

void drawLiveReadings() {

  display.clearDisplay();

  display.setTextSize(1);

  display.setTextColor(SSD1306_WHITE);

  display.setCursor(0, 0);

  display.println("LIVE SENSOR READINGS");

  display.printf(
    "NIR:%.0f VIS:%.0f\n",
    nirValue,
    visValue
  );

  display.printf(
    "RED: %lu\n",
    (unsigned long)maxRed
  );

  display.printf(
    "IR: %lu\n",
    (unsigned long)maxIR
  );

  display.printf(
    "OBJ:%.1f AMB:%.1f C\n",
    safeFloat(objectTempC),
    safeFloat(ambientTempC)
  );

  display.printf(
    "ADC0:%.2f ADC1:%.2f\n",
    safeFloat(adcVolts[0]),
    safeFloat(adcVolts[1])
  );

  display.printf(
    "ADC2:%.2f ADC3:%.2f\n",
    safeFloat(adcVolts[2]),
    safeFloat(adcVolts[3])
  );

  display.printf(
    "850:%s 940:%s\n",
    led850Proxy >= 0 ? "READY" : "ERROR",
    led940Proxy >= 0 ? "READY" : "ERROR"
  );

  display.display();
}


// =====================================================
// OLED PAGE 2 - SENSOR STATUS
// =====================================================

void drawSensorStatus() {

  display.clearDisplay();

  display.setTextSize(1);

  display.setTextColor(SSD1306_WHITE);

  display.setCursor(0, 0);

  display.println("SENSOR STATUS");

  display.printf(
    "AS7343: %s\n",
    asReady ? "CONNECTED" : "ERROR"
  );

  display.printf(
    "MAX30102: %s\n",
    maxReady ? "CONNECTED" : "ERROR"
  );

  display.printf(
    "MLX90614: %s\n",
    mlxReady ? "CONNECTED" : "ERROR"
  );

  display.printf(
    "ADS1115: %s OLED:%s\n",
    adsReady ? "OK" : "ERROR",
    oledReady ? "OK" : "ERROR"
  );

  display.printf(
    "WIFI: %s\n",
    WiFi.status() == WL_CONNECTED
      ? "CONNECTED"
      : "DISCONNECTED"
  );

  display.printf(
    "BACKEND: %s\n",
    backendConnected
      ? "CONNECTED"
      : "DISCONNECTED"
  );

  display.display();
}


// =====================================================
// OLED PAGE 0 - INITIALIZATION
// =====================================================

void drawInitialization() {

  display.clearDisplay();

  display.setTextSize(1);

  display.setTextColor(SSD1306_WHITE);

  display.setCursor(0, 0);

  display.println("GLUCOSENSE");

  display.println("---------------------");

  display.println("SYSTEM INITIALIZED");

  display.printf(
    "AS7343: %s\n",
    asReady ? "OK" : "ERROR"
  );

  display.printf(
    "MAX30102: %s\n",
    maxReady ? "OK" : "ERROR"
  );

  display.printf(
    "MLX90614: %s\n",
    mlxReady ? "OK" : "ERROR"
  );

  display.printf(
    "ADS1115: %s\n",
    adsReady ? "OK" : "ERROR"
  );

  display.println("Press button to start");

  display.display();
}


// =====================================================
// OLED DISPLAY CONTROL
// =====================================================

void drawDisplay() {

  if (!oledReady) return;

  if (displayPage == 0) {

    drawInitialization();
  }

  else if (displayPage == 1) {

    drawLiveReadings();
  }

  else if (displayPage == 2) {

    drawSensorStatus();
  }
}


// =====================================================
// BACKEND DATA UPLOAD
// =====================================================

bool postReading() {

  if (WiFi.status() != WL_CONNECTED) {

    return false;
  }

  WiFiClient client;

  HTTPClient http;

  String url = String(API_BASE) + "/api/readings";

  if (!http.begin(client, url)) {

    return false;
  }

  http.setTimeout(1500);

  http.addHeader(
    "Content-Type",
    "application/json"
  );

  http.addHeader(
    "X-Device-Key",
    DEVICE_API_KEY
  );

  StaticJsonDocument<2048> doc;

  doc["device_id"] = DEVICE_ID;

  doc["led_850_raw"] =
    led850Proxy >= 0 ? led850Proxy : 0;

  doc["led_940_raw"] =
    led940Proxy >= 0 ? led940Proxy : 0;

  doc["signal_quality"] = "unassessed";

  doc["reference_glucose_mg_dl"] = nullptr;

  doc["pulse_bpm"] = nullptr;

  doc["red"] = maxRed;

  doc["ir"] = maxIR;

  doc["object_temp_c"] =
    isfinite(objectTempC) ? objectTempC : 0;

  doc["ambient_temp_c"] =
    isfinite(ambientTempC) ? ambientTempC : 0;


  JsonArray ch = doc.createNestedArray("channels");

  for (int i = 0; i < 12; i++) {

    ch.add(channels[i]);
  }


  JsonArray raw = doc.createNestedArray("adc_raw");

  JsonArray volts = doc.createNestedArray("adc_volts");

  for (int i = 0; i < 4; i++) {

    raw.add(adcRaw[i]);

    volts.add(
      isfinite(adcVolts[i])
        ? adcVolts[i]
        : 0
    );
  }


  JsonObject metadata = doc.createNestedObject("metadata");

  metadata["firmware"] = "GlucoSense-ESP32-1.2";

  metadata["as7343_ready"] = asReady;

  metadata["max30102_ready"] = maxReady;

  metadata["mlx90614_ready"] = mlxReady;

  metadata["ads1115_ready"] = adsReady;

  metadata["warning"] =
    "Experimental prototype only; not clinically validated";

  metadata["optical_proxy_note"] =
    "LED-on aggregate channel averages; not calibrated irradiance";


  struct tm timeinfo;

  if (getLocalTime(&timeinfo, 50)) {

    char timestamp[25];

    strftime(
      timestamp,
      sizeof(timestamp),
      "%Y-%m-%dT%H:%M:%SZ",
      &timeinfo
    );

    doc["timestamp"] = timestamp;
  }


  String body;

  serializeJson(doc, body);

  int code = http.POST(body);

  lastHttpStatus = code;

  Serial.printf(
    "POST /api/readings: HTTP %d\n",
    code
  );

  if (code > 0) {

    Serial.println(http.getString());
  }

  else {

    Serial.println(
      http.errorToString(code)
    );
  }

  http.end();

  return code >= 200 && code < 300;
}


// =====================================================
// BACKGROUND NETWORK TASK
// =====================================================

void networkTask(void *parameter) {

  uint32_t lastBackend = 0;

  uint32_t lastUpload = 0;

  uint32_t lastReconnect = 0;

  for (;;) {

    uint32_t now = millis();

    // WiFi reconnect
    if (WiFi.status() != WL_CONNECTED) {

      backendConnected = false;
      wifiInfoPrinted = false;

      if (
        now - lastReconnect >=
        WIFI_RETRY_INTERVAL_MS
      ) {

        lastReconnect = now;

        Serial.println("Retrying WiFi...");

        WiFi.disconnect();

        WiFi.begin(
          WIFI_SSID,
          WIFI_PASSWORD
        );
      }
    }

    else {

      wifiIp = WiFi.localIP().toString();

      // Print ESP32 network details once after Wi-Fi connects.
      if (!wifiInfoPrinted) {
        Serial.println();
        Serial.println("========== GLUCOSENSE NETWORK ==========");
        Serial.print("ESP32 IP Address : ");
        Serial.println(WiFi.localIP());
        Serial.print("Gateway          : ");
        Serial.println(WiFi.gatewayIP());
        Serial.print("Subnet Mask      : ");
        Serial.println(WiFi.subnetMask());
        Serial.print("WiFi RSSI        : ");
        Serial.print(WiFi.RSSI());
        Serial.println(" dBm");
        Serial.print("Backend API      : ");
        Serial.println(API_BASE);
        Serial.println("=========================================");
        wifiInfoPrinted = true;
      }

      // Backend health check
      if (
        now - lastBackend >=
        BACKEND_INTERVAL_MS
      ) {

        lastBackend = now;

        checkBackend();
      }

      // Upload data only when backend DB is connected
      if (
        backendConnected &&
        now - lastUpload >= SEND_INTERVAL_MS
      ) {

        lastUpload = now;

        bool uploaded = postReading();

        Serial.println(
          uploaded
            ? "TELEMETRY UPLOAD OK"
            : "TELEMETRY UPLOAD FAILED"
        );
      }
    }

    vTaskDelay(
      pdMS_TO_TICKS(100)
    );
  }
}


// =====================================================
// SETUP
// =====================================================

void setup() {

  Serial.begin(115200);

  delay(200);

  pinMode(
    BUTTON_PIN,
    INPUT_PULLUP
  );

  pinMode(
    LED_850_PIN,
    OUTPUT
  );

  pinMode(
    LED_940_PIN,
    OUTPUT
  );

  allLedsOff();

  Wire.begin(
    I2C_SDA,
    I2C_SCL
  );

  Wire.setClock(100000);


  // OLED
  initDisplay();


  // WiFi starts without blocking
  showInitialization("Starting WiFi...");

  connectWiFi();


  // Sensors
  initSensors();
  // Start ESP32 HTTP API
server.on("/api/data", HTTP_GET, handleData);

server.begin();

Serial.println("ESP32 HTTP SERVER STARTED");
Serial.println("API: http://10.46.89.4/api/data");


  showInitialization("System initialized");


  Serial.println();

  Serial.println("GLUCOSENSE READY");

  Serial.println("Page 0: Initialization");

  Serial.println("Press 1: Live Readings");

  Serial.println("Press 2: Sensor Status");

  Serial.println("Next presses: Toggle pages");


  displayPage = 0;

  lastSensorRead = millis();

  lastDisplay = 0;

  lastLedCapture = millis();

  // Start independent networking on Core 0
  BaseType_t taskCreated = xTaskCreatePinnedToCore(
    networkTask,
    "NetworkTask",
    8192,
    NULL,
    1,
    NULL,
    0
  );

  if (taskCreated != pdPASS) {

    Serial.println("ERROR: Network task creation failed");
  }
}


// =====================================================
// MAIN LOOP
// =====================================================

void loop() {

  // Handle incoming browser/frontend requests
  server.handleClient();

  // Existing code continues below
  // Button first
  handleButton();


  // Sensor reading
  if (
    millis() - lastSensorRead >=
    SENSOR_INTERVAL_MS
  ) {

    readAllSensors();
  }


  // LED optical captures at separate interval
  updateLEDMeasurements();


  // Button again after sensor work
  handleButton();


  // OLED refresh
  if (
    millis() - lastDisplay >=
    DISPLAY_INTERVAL_MS
  ) {

    lastDisplay = millis();

    drawDisplay();
  }

  delay(1);
}
