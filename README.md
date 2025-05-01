# Smart Home Monitoring System

Dieses Projekt überwacht und visualisiert Gas- und Stromverbrauchsdaten und erstellt Berichte.

## Funktionsweise

1. **ESP32-Kamera** nimmt Bilder vom Gaszähler auf und sendet diese mit Sensordaten an den Server
2. **Stromzähler-ESP** erfasst Stromverbrauchsdaten und sendet diese an den Server
3. **Server** (server.py) empfängt und speichert alle Daten
4. **Bildauswertung** (image_evaluator.py) extrahiert Zählerwerte aus den Bildern
5. **Visualisierungstools** erstellen Grafiken und Berichte zum Energieverbrauch

## Einrichtung für öffentliche Nutzung

### 1. Umgebungsvariablen konfigurieren

1. Kopiere die `.env.example` Datei und benenne sie in `.env` um:
   ```bash
   cp .env.example .env
   ```

2. Bearbeite die `.env` Datei und füge deine persönlichen Konfigurationsdaten ein:
   ```
   # Ersetze diese Werte mit deinen eigenen Daten
   TELEGRAM_BOT_TOKEN="DEIN_BOT_TOKEN_HIER_EINFUEGEN"
   TELEGRAM_CHAT_ID="DEINE_GRUPPEN_CHAT_ID_HIER_EINFUEGEN"
   ELECTRICITY_ESP_IP="192.168.178.XXX"
   ```

### 2. ESP32-Konfigurationsdateien einrichten

#### Gaszähler-ESP32 (mit Kamera)
1. Kopiere die Beispiel-Konfigurationsdatei und erstelle deine eigene:
   ```bash
   cp gas-esp/src/environment.h.example gas-esp/src/environment.h
   ```
2. Bearbeite `gas-esp/src/environment.h` und passe die WLAN-Zugangsdaten und Server-URL an:
   ```cpp
   #define WIFI_SSID "DEIN_WLAN_SSID"
   #define WIFI_PASSWORD "DEIN_WLAN_PASSWORT"
   #define SERVER_URL "http://DEINE_SERVER_IP:5000/api/camera"
   ```

#### Stromzähler-ESP32
1. Kopiere die Beispiel-Konfigurationsdatei und erstelle deine eigene:
   ```bash
   cp electricity-esp/src/config.h.example electricity-esp/src/config.h
   ```
2. Bearbeite `electricity-esp/src/config.h` und passe die WLAN-Zugangsdaten und Server-URL an:
   ```cpp
   const char* ssid = "DEIN_WLAN_SSID";
   const char* password = "DEIN_WLAN_PASSWORT";
   const char* serverUrl = "http://DEINE_SERVER_IP:5000/upload";
   ```

### 3. Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### 4. Tesseract OCR installieren (für Bildauswertung)

#### Windows
1. Download von https://github.com/UB-Mannheim/tesseract/wiki
2. Installation ausführen
3. Pfad in `image_evaluator.py` prüfen: `pytesseract.pytesseract.tesseract_cmd = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'`

#### macOS
```
brew install tesseract
```

#### Linux (Ubuntu/Debian)
```
sudo apt update
sudo apt install tesseract-ocr
```

## Wichtige Dateien

- `server.py`: Hauptserver zum Empfang aller Daten
- `image_evaluator.py`: Bildauswertung mit OCR für den Gaszähler
- `electricity-esp/stromzaehler_logger.py`: Logger für den Stromzähler
- `combined_visualizer.py`: Kombinierte Visualisierung von Gas- und Stromverbrauch
- `sende_bericht.py`: Sendet Berichte via Telegram

## Verwendung

### Server starten

```bash
python server.py
```

### Visualisierung starten

```bash
python combined_visualizer.py
```

### Bericht senden

```bash
python sende_bericht.py
```

## Umgebungsvariablen

Die folgende Tabelle zeigt alle verfügbaren Konfigurationsparameter in der `.env`-Datei:

| Variable | Beschreibung | Standardwert |
|----------|--------------|--------------|
| TELEGRAM_BOT_TOKEN | Telegram-Bot-Token | - |
| TELEGRAM_CHAT_ID | Telegram-Chat-ID für Berichte | - |
| TELEGRAM_DATEINAME | Dateiname für Telegram-Berichte | Wochenbericht_Energie_KW_JAHR_WOCHE.png |
| ELECTRICITY_ESP_IP | IP-Adresse des Strom-ESP | 192.168.178.157 |
| ELECTRICITY_POLL_INTERVAL_SECONDS | Abfrageintervall in Sekunden | 0.5 |
| ELECTRICITY_ROTATIONS_PER_KWH | Umdrehungen pro kWh | 75 |
| ELECTRICITY_COST_PER_KWH_EURO | Stromkosten pro kWh in Euro | 0.4017 |
| SERVER_PORT | Server-Port | 5000 |
| PORT_NUMBER | Port für Visualisierungen | 5001 |
| ESP_WIFI_SSID | WLAN-SSID für die ESP32-Geräte | - |
| ESP_WIFI_PASSWORD | WLAN-Passwort für die ESP32-Geräte | - |
| ESP_GAS_SERVER_URL | Server-URL für den Gaszähler | - |
| ESP_ELECTRICITY_SERVER_URL | Server-URL für den Stromzähler | - |

## Hinweis zur Sicherheit

Alle sensiblen Daten werden in separaten Konfigurationsdateien gespeichert, die nicht im Repository enthalten sind:

1. `.env` - Hauptkonfiguration für den Server und Python-Skripte
2. `gas-esp/src/environment.h` - Konfiguration für den Gaszähler-ESP32
3. `electricity-esp/src/config.h` - Konfiguration für den Stromzähler-ESP32

Diese Dateien sind in der `.gitignore` aufgeführt und werden nicht ins Repository hochgeladen. Verwenden Sie die `.example`-Versionen als Vorlagen.

## Veröffentlichung auf GitHub

Bei der Veröffentlichung auf GitHub wird durch die `.gitignore` sichergestellt, dass keine sensiblen Daten hochgeladen werden. Folgende Dateien werden ignoriert:

- `.env` - Enthält API-Keys, Tokens und andere sensible Informationen
- `gas-esp/src/environment.h` - Enthält WLAN-Zugangsdaten und Server-URLs
- `electricity-esp/src/config.h` - Enthält WLAN-Zugangsdaten und Server-URLs

Vergewissern Sie sich vor dem ersten Push, dass Sie alle sensiblen Daten aus dem Code entfernt und in die entsprechenden Konfigurationsdateien ausgelagert haben.

## Mitwirkung

1. Forke das Repository
2. Erstelle einen Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Committe deine Änderungen (`git commit -m 'Add some AmazingFeature'`)
4. Pushe zum Branch (`git push origin feature/AmazingFeature`)
5. Öffne einen Pull Request 