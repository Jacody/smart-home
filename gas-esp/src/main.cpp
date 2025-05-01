#include "esp_camera.h"
#include <WiFi.h>
#include "driver/ledc.h"
#include <HTTPClient.h>
#include <DHT.h>
#include "esp_sleep.h"
#include "esp_timer.h" // Wird nur noch für Debugging gebraucht, nicht für Scheduling
#include "driver/rtc_io.h" // Für rtc_gpio_hold_dis

// Wähle das Kameramodell
#define CAMERA_MODEL_AI_THINKER
#include "camera_pins.h"

// === Konfiguration ===
// WiFi-Zugangsdaten werden über die environment.h geladen
#include "environment.h" // Definiert WIFI_SSID und WIFI_PASSWORD und SERVER_URL
// Prüfen ob die Umgebungsvariablen gesetzt sind
#ifndef WIFI_SSID
#define WIFI_SSID "WIFI_SSID_HIER_EINTRAGEN"
#endif
#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD "WIFI_PASSWORD_HIER_EINTRAGEN"
#endif
#ifndef SERVER_URL
#define SERVER_URL "http://SERVER_IP_HIER_EINTRAGEN:5000/api/camera"
#endif

// Server-Informationen aus environment.h geladen
const char* serverUrl = SERVER_URL;

// Deep Sleep Konfiguration
#define uS_TO_S_FACTOR 1000000ULL      // Umrechnungsfaktor Mikrosekunden -> Sekunden
#define PHOTO_INTERVAL_S 3600          // Intervall für Fotos in Sekunden (1 Stunde)
#define KEEP_ALIVE_INTERVAL_S 90       // Intervall zum Wachhalten der Powerbank (Sekunden) <= 120s !

// Berechne, wie viele Keep-Alive-Intervalle ungefähr in ein Foto-Intervall passen
// Wir runden auf (durch Addition von Intervall-1 vor Division), um sicherzustellen, dass wir nicht zu früh auslösen.
const int wakeupsNeededForPhoto = (PHOTO_INTERVAL_S + KEEP_ALIVE_INTERVAL_S - 1) / KEEP_ALIVE_INTERVAL_S;

// DHT11 Sensor Pin und Typ
#define DHTPIN 13
#define DHTTYPE DHT11

// Konstanten für LED-Steuerung (Flash)
#define LEDC_CHANNEL_FLASH 5 // Kanal für den Blitz
#define LED_GPIO_NUM 4       // Blitz-LED Pin (oft GPIO 4 bei ESP32-CAM AI Thinker)

// === Globale Variablen / RTC Speicher ===
RTC_DATA_ATTR int bootCount = 0;                   // Zählt alle Boots/Wakeups
RTC_DATA_ATTR int wakeupsSinceLastPhoto = 0; // Zähler für Aufwachzyklen seit letztem Foto

// DHT Sensor Objekt erstellen
DHT dht(DHTPIN, DHTTYPE);

// === LED Steuerung (Flash) ===
void setupLedFlash(int pin) {
    if (pin >= 0) {
        // Verhindere, dass der Pin während Deep Sleep gehalten wird (falls er vorher genutzt wurde)
        rtc_gpio_hold_dis((gpio_num_t)pin);

        ledcSetup(LEDC_CHANNEL_FLASH, 5000, 8); // channel, freq, resolution
        ledcAttachPin(pin, LEDC_CHANNEL_FLASH);
        ledcWrite(LEDC_CHANNEL_FLASH, 0); // LED aus
        Serial.printf("LED-Flash konfiguriert (Pin: %d, Kanal: %d)\n", pin, LEDC_CHANNEL_FLASH);
    } else {
        Serial.println("Kein LED_GPIO_NUM definiert oder ungültig.");
    }
}

void toggle_led(bool en) {
#if defined(LED_GPIO_NUM) && LED_GPIO_NUM >= 0
    int duty = en ? 200 : 0; // Helligkeit für Blitz (0-255)
    ledcWrite(LEDC_CHANNEL_FLASH, duty);
    // Serial.printf("LED Intensität: %d\n", duty); // Optional: Weniger Output
#endif
}

// === Sensor Auslesen ===
void readDHT(float &temperature, float &humidity) {
    temperature = dht.readTemperature();
    humidity = dht.readHumidity();

    if (isnan(temperature) || isnan(humidity)) {
        Serial.println("Fehler beim Auslesen des DHT11 Sensors!");
        temperature = -99.9; // Fehlerwert
        humidity = -99.9;    // Fehlerwert
        return;
    }

    Serial.print("Temperatur: ");
    Serial.print(temperature);
    Serial.print(" °C | Luftfeuchtigkeit: ");
    Serial.print(humidity);
    Serial.println(" %");
}

// === Bild an Server senden ===
bool sendImageToServer(camera_fb_t *fb, float temperature, float humidity) {
    if (!fb) {
        Serial.println("Fehler: Kein Bild zum Senden");
        return false;
    }
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("Fehler: Kein WiFi zum Senden");
        return false;
    }

    HTTPClient http;
    bool success = false;

    Serial.println("Sende Bild, Temperatur und Luftfeuchtigkeit an Server...");
    Serial.print("URL: ");
    Serial.println(serverUrl);

    http.begin(serverUrl);
    http.addHeader("Content-Type", "image/jpeg");
    // Nur gültige Werte senden
    if (temperature > -99.0) http.addHeader("X-Temperature", String(temperature, 1));
    if (humidity > -99.0) http.addHeader("X-Humidity", String(humidity, 1));

    // Sende das Bild als POST-Request
    int httpResponseCode = http.POST(fb->buf, fb->len);

    if (httpResponseCode > 0) {
        String response = http.getString();
        Serial.println("HTTP Response Code: " + String(httpResponseCode));
        Serial.println("Server-Antwort: " + response);
        if (httpResponseCode == 200) { // Oder den erwarteten Erfolgscode prüfen
           success = true;
        }
    } else {
        Serial.print("Fehler beim Senden. HTTP-Fehlercode: ");
        Serial.println(httpResponseCode);
        // Versuche, mehr Details zu bekommen
        // String response = http.getString(); // Kann bei Fehlern leer sein
        // Serial.println("Server-Antwort (bei Fehler): " + response);
        Serial.print("ESP-IDF HTTP Error: ");
        Serial.println(http.errorToString(httpResponseCode).c_str());
    }

    http.end();
    return success;
}

// === Bildaufnahme mit Blitz ===
bool captureAndSendImage() {
    // LED einschalten
    Serial.println("Schalte LED ein...");
    toggle_led(true);
    delay(1000); // Kurz warten bis LED hell ist / Belichtung anpasst

    // Bild aufnehmen
    Serial.println("Nehme Bild auf...");
    camera_fb_t* fb = esp_camera_fb_get();

    // LED ausschalten
    // Serial.println("Schalte LED aus..."); // Optional: Weniger Output
    toggle_led(false);

    bool success = false;
    if (fb) {
        Serial.printf("Bild aufgenommen: %dx%d Pixel, Groesse: %u Bytes\n", fb->width, fb->height, fb->len);

        // Temperatur und Luftfeuchtigkeit lesen
        float temperature = 0.0;
        float humidity = 0.0;
        readDHT(temperature, humidity);

        // Bild an Server senden
        success = sendImageToServer(fb, temperature, humidity);

        // Speicher freigeben
        esp_camera_fb_return(fb);
        Serial.println("Kamerabuffer freigegeben.");
    } else {
        Serial.println("Fehler bei der Bildaufnahme!");
        success = false;
    }
    return success;
}

// === Deep Sleep Funktion ===
void goToDeepSleep(uint64_t sleepDuration_s) {
    Serial.printf("Vorbereitung für Deep Sleep für %llu Sekunden...\n", sleepDuration_s);

    // WLAN-Verbindung trennen und Modul deaktivieren
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
    btStop(); // Bluetooth auch stoppen (falls aktiviert gewesen wäre)

    // GPIOs in einen stromsparenden Zustand versetzen (optional, aber gut)
    // Beispiel: Halten des LED-Pins verhindern (bereits in setupLedFlash)
    // Man könnte hier weitere ungenutzte Pins konfigurieren, falls nötig

    Serial.println("WiFi & BT deaktiviert.");

    // Deep Sleep Timer konfigurieren
    esp_sleep_enable_timer_wakeup(sleepDuration_s * uS_TO_S_FACTOR);
    Serial.printf("ESP32 wird in %llu Sekunden aufwachen.\n", sleepDuration_s);

    // Serielle Ausgaben abschließen lassen
    Serial.flush();
    delay(100); // Kurze Pause um sicherzustellen, dass alles gesendet wurde

    // In den Deep Sleep gehen
    Serial.println("Gehe jetzt in Deep Sleep...");
    esp_deep_sleep_start();
    // Code wird hier nicht weiter ausgeführt
}

// === Powerbank Wachhalte-Aktion ===
void performKeepAliveAction() {
    Serial.println("Führe Keep-Alive Aktion aus...");
    // Aktion, die kurz Strom zieht. Beispiel: LED kurz hell aufleuchten lassen.
#if defined(LED_GPIO_NUM) && LED_GPIO_NUM >= 0
    ledcWrite(LEDC_CHANNEL_FLASH, 255); // Max Helligkeit
    delay(500);                        // Für 500ms anlassen
    ledcWrite(LEDC_CHANNEL_FLASH, 0);  // Wieder aus
    // Serial.println("Keep-Alive LED Blitz ausgeführt."); // Optional: Weniger Output
#else
    // Alternative, falls keine LED konfiguriert: WiFi kurz an/aus (zieht mehr Strom)
    Serial.println("Keep-Alive: Schalte WiFi kurz ein/aus...");
    WiFi.mode(WIFI_STA); // Aktiviert WiFi Radio
    delay(200);
    WiFi.mode(WIFI_OFF); // Deaktiviert es wieder
    // esp_wifi_stop(); // WiFi.mode(WIFI_OFF) sollte reichen
    Serial.println("Keep-Alive WiFi Puls ausgeführt.");
#endif
    delay(100); // Kurze Pause nach der Aktion
}

// === Wakeup Grund anzeigen ===
void printWakeupReason() {
    esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
    bootCount++; // Zähler erhöhen bei jedem Start

    Serial.println("\n=================================");
    Serial.printf("Boot Zähler (Gesamt): %d\n", bootCount);

    switch(wakeup_reason) {
        case ESP_SLEEP_WAKEUP_TIMER:
            Serial.println("Aufgewacht durch Timer.");
            break;
        // Füge hier bei Bedarf andere Wakeup-Gründe hinzu
        default:
             // Beim allerersten Start ist der Grund oft PWR_RESET oder RTC_SW_SYS_RESET
            Serial.printf("Aufgewacht durch Grund: %d\n", wakeup_reason);
            if (bootCount == 1) {
                Serial.println("Erster Start nach Power-On oder Flash.");
                // Beim ersten Start den Zähler für Fotos initialisieren,
                // damit er nicht zufällig direkt auslöst.
                wakeupsSinceLastPhoto = 0;
            }
            break;
    }
    Serial.println("=================================");
}

// === Setup Funktion (Hauptlogik) ===
void setup() {
    Serial.begin(115200);
    Serial.setDebugOutput(true);
    // Kleiner Delay nach Serial.begin kann helfen, die erste Ausgabe nicht zu verpassen
    delay(500);
    Serial.println("\n\nESP32-CAM Start...");

    // Wakeup Grund anzeigen (erhöht bootCount)
    printWakeupReason();

    // Zähler für Fotointervall erhöhen (außer beim allerersten Boot, wird in printWakeupReason() behandelt)
    if (bootCount > 1) {
        wakeupsSinceLastPhoto++;
    }

    Serial.printf("Keep-Alive Zyklen seit letztem Foto: %d / %d\n", wakeupsSinceLastPhoto, wakeupsNeededForPhoto);


    // Kamera Konfiguration
    camera_config_t config;
      config.ledc_channel = LEDC_CHANNEL_0; // Beachte: Kann sich von Flash-LED unterscheiden!
      config.ledc_timer = LEDC_TIMER_0;
      config.pin_d0 = Y2_GPIO_NUM;
      config.pin_d1 = Y3_GPIO_NUM;
      config.pin_d2 = Y4_GPIO_NUM;
      config.pin_d3 = Y5_GPIO_NUM;
      config.pin_d4 = Y6_GPIO_NUM;
      config.pin_d5 = Y7_GPIO_NUM;
      config.pin_d6 = Y8_GPIO_NUM;
      config.pin_d7 = Y9_GPIO_NUM;
      config.pin_xclk = XCLK_GPIO_NUM;
      config.pin_pclk = PCLK_GPIO_NUM;
      config.pin_vsync = VSYNC_GPIO_NUM;
      config.pin_href = HREF_GPIO_NUM;
      config.pin_sccb_sda = SIOD_GPIO_NUM;
      config.pin_sccb_scl = SIOC_GPIO_NUM;
      config.pin_pwdn = PWDN_GPIO_NUM;
      config.pin_reset = RESET_GPIO_NUM; // -1 falls nicht verbunden
      config.xclk_freq_hz = 20000000;
      config.frame_size = FRAMESIZE_SVGA;  // Gute Auflösung (800x600)
      config.pixel_format = PIXFORMAT_JPEG;
      config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
      config.fb_location = CAMERA_FB_IN_PSRAM;
      config.jpeg_quality = 12; // 10-12 ist gut
      config.fb_count = 1; // Nur 1 Frame nötig für Foto

      if(psramFound()){
        config.jpeg_quality = 10;
        config.fb_count = 2; // Erlaubt flüssigere Aufnahme, wenn nötig
        config.grab_mode = CAMERA_GRAB_LATEST;
        Serial.println("PSRAM gefunden, nutze höhere Qualitätseinstellungen.");
      } else {
        // Ohne PSRAM ist SVGA oft schon problematisch
        config.frame_size = FRAMESIZE_VGA; // Sicherere Auflösung (640x480)
        config.fb_location = CAMERA_FB_IN_DRAM;
        config.fb_count = 1;
        config.jpeg_quality = 12;
        Serial.println("Kein PSRAM gefunden, nutze DRAM und VGA-Auflösung.");
      }


    // Prüfen, ob genügend Zyklen für ein Foto vergangen sind
    bool timeForPhoto = (wakeupsSinceLastPhoto >= wakeupsNeededForPhoto);

    // Beim allerersten Boot (nach Flash/PowerOn) auch ein Foto machen
    if (bootCount == 1) {
        Serial.println("Erster Boot - Mache initiales Foto.");
        timeForPhoto = true;
    }


    if (timeForPhoto) {
        Serial.println("==> Zeit für ein Foto!");
        // --- FOTO-ROUTINE ---

        // LED-Flash konfigurieren (wird auch für Keep-Alive gebraucht, aber hier sicherstellen)
        #if defined(LED_GPIO_NUM) && LED_GPIO_NUM >= 0
            setupLedFlash(LED_GPIO_NUM);
        #endif

        // DHT Sensor initialisieren
        dht.begin();
        // Kleine Pause nach DHT begin kann helfen
        delay(100);
        Serial.println("DHT11 Sensor initialisiert.");

        Serial.println("Initialisiere Kamera...");
        esp_err_t err = esp_camera_init(&config);
        if (err != ESP_OK) {
            Serial.printf("Kamera-Initialisierung fehlgeschlagen mit Fehler 0x%x\n", err);
            // Mögliche Fehlercodes: ESP_ERR_INVALID_ARG, ESP_ERR_NOT_FOUND, ESP_ERR_NO_MEM, etc.
            Serial.println("Problem bei Kamera-Init. Gehe für Keep-Alive-Intervall schlafen...");
            // Zähler NICHT zurücksetzen, damit er es beim nächsten Mal versucht
            goToDeepSleep(KEEP_ALIVE_INTERVAL_S);
            return; // Sollte nicht erreicht werden
        }
        Serial.println("Kamera initialisiert.");

        // Kameraeinstellungen (optional, nach Init)
        sensor_t * s = esp_camera_sensor_get();
        if (s) {
             s->set_vflip(s, 1);     // Vertikale Spiegelung an (falls nötig)
             s->set_hmirror(s, 1);   // Horizontale Spiegelung an (falls nötig)
             // Weitere Einstellungen nach Bedarf: Helligkeit, Kontrast etc.
             // s->set_brightness(s, 1); // Beispiel
        } else {
             Serial.println("Warnung: Konnte Kamera-Sensor nicht bekommen, um Einstellungen anzuwenden.");
        }


        // Mit WiFi verbinden
        Serial.print("Verbinde mit WiFi: ");
        Serial.println(WIFI_SSID);
        WiFi.mode(WIFI_STA);
        // WiFi.setSleep(false); // Im STA Modus oft standardmäßig an, aber schadet nicht
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

        int wifi_retries = 0;
        const int max_wifi_retries = 20; // Ca. 10 Sekunden Timeout
        while (WiFi.status() != WL_CONNECTED && wifi_retries < max_wifi_retries) {
            delay(500);
            Serial.print(".");
            wifi_retries++;
        }

        bool photoSent = false;
        if (WiFi.status() == WL_CONNECTED) {
            Serial.println("\nWiFi verbunden!");
            Serial.print("IP-Adresse: ");
            Serial.println(WiFi.localIP());

            // Bild aufnehmen und senden
            photoSent = captureAndSendImage(); // Funktion gibt true bei Erfolg zurück

            // WiFi wieder trennen (wird in goToDeepSleep() sowieso gemacht, aber sauberer hier)
            // WiFi.disconnect(true);

        } else {
            Serial.println("\nWiFi-Verbindung fehlgeschlagen!");
            // Hier wurde kein Foto gesendet
        }

        // Kamera deinitialisieren um Strom zu sparen
        esp_camera_deinit();
        Serial.println("Kamera deinitialisiert.");

        // WICHTIG: Zähler zurücksetzen, NACHDEM die Foto-Routine abgeschlossen ist
        // (egal ob erfolgreich gesendet oder nicht, Hauptsache versucht)
        Serial.println("Setze Keep-Alive Zähler zurück.");
        wakeupsSinceLastPhoto = 0;

        // Nach Foto-Routine immer für das kurze Intervall schlafen gehen
        goToDeepSleep(KEEP_ALIVE_INTERVAL_S);

    } else {
        // --- KEEP-ALIVE ROUTINE ---
        // Nur die Keep-Alive Aktion ausführen, keine Kamera/WiFi/DHT nötig

        // LED Konfiguration für Keep-Alive (falls noch nicht geschehen oder nach Fehler)
        #if defined(LED_GPIO_NUM) && LED_GPIO_NUM >= 0
             setupLedFlash(LED_GPIO_NUM); // Sicherstellen, dass LED konfiguriert ist
        #endif

        performKeepAliveAction();

        // Immer für das kurze Intervall schlafen gehen
        goToDeepSleep(KEEP_ALIVE_INTERVAL_S);
    }
}

// === Loop Funktion (wird nicht verwendet) ===
void loop() {
    // Bleibt leer, da die gesamte Logik in setup() nach dem Deep Sleep abläuft
    Serial.println("Unerwartet in loop() gelandet. Gehe schlafen...");
    delay(1000); // Kurze Pause
    goToDeepSleep(KEEP_ALIVE_INTERVAL_S); // Sicherheitsnetz
}