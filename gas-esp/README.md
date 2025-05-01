# ESP32-CAM Projekt (Mit Deep Sleep)

Dieses Projekt ermöglicht es, mit einem ESP32-CAM Modul Bilder aufzunehmen und an einen lokalen Server zu senden. Zusätzlich wird die Temperatur und Luftfeuchtigkeit über einen DHT11-Sensor erfasst und mit den Bildern übertragen. Das System nutzt den Deep Sleep-Modus des ESP32, um alle 2 Minuten eine Aufnahme zu machen und dabei Energie zu sparen.

## Komponenten

1. **ESP32-CAM** - Nimmt Bilder auf und sendet sie per HTTP an den Server
2. **DHT11 Sensor** - Misst Temperatur und Luftfeuchtigkeit (an Pin 13 angeschlossen)
3. **Python Server** - Empfängt Bilder und Sensordaten vom ESP32-CAM und speichert sie

## Deep Sleep Implementierung

Der ESP32-CAM nutzt den Deep Sleep-Modus, um Energie zu sparen:
- Der ESP32 wacht alle 2 Minuten auf
- Nimmt ein Bild auf und sendet es zusammen mit den Sensordaten an den Server
- Trennt dann die WLAN-Verbindung und geht wieder in den Deep Sleep-Modus
- Der Stromverbrauch wird von ~150mA auf ~10µA im Ruhezustand reduziert

## Serielle Überwachung

Die serielle Schnittstelle (115200 baud) liefert ausführliche Informationen zum Betriebszustand:
- Boot-Zähler und Aufwachgrund
- WLAN-Verbindungsstatus
- Sensor- und Kamerastatus
- Übertragungsinformationen
- Deep Sleep-Informationen

## Voraussetzungen

- PlatformIO (für die ESP32-Entwicklung)
- Python 3.6+ mit Flask
- ESP32-CAM Board (AI Thinker)
- USB-TTL Adapter für das Flashen des ESP32 und serielle Überwachung
- DHT11 Temperatur- und Luftfeuchtigkeitssensor (am ESP32-CAM angeschlossen)

## DHT11-Sensor-Anschluss

Der DHT11-Sensor wird an Pin 13 des ESP32-CAM angeschlossen:
- VCC → 3.3V des ESP32
- GND → GND des ESP32
- DATA → GPIO13 des ESP32

Im Projekt wird die Adafruit DHT Bibliothek verwendet, die in der platformio.ini als Abhängigkeit konfiguriert ist.

## Serielle Verbindung herstellen

Für die Überwachung der ESP32-CAM über die serielle Schnittstelle:

1. Verbinden Sie den ESP32-CAM mit einem USB-TTL-Adapter:
   - ESP32 GND → USB-TTL GND
   - ESP32 U0R → USB-TTL TX
   - ESP32 U0T → USB-TTL RX
   - ESP32 VCC → USB-TTL 5V/3.3V (je nach Modell)

2. Öffnen Sie einen seriellen Monitor mit 115200 baud:
   ```
   # Mit PlatformIO
   pio device monitor -b 115200
   
   # Oder mit Screen
   screen /dev/tty.usbserial-XXXX 115200
   ```

## Server starten

```bash
# Standard Port (5000)
python server.py

# Alternativer Port
python server.py --port 5001
```

## ESP32 flashen

1. Verbinde den ESP32 mit dem USB-TTL Adapter:
   - ESP32 GPIO0 → GND (für Flash-Modus)
   - ESP32 GND → USB-TTL GND
   - ESP32 VCC → USB-TTL 5V/3.3V
   - ESP32 U0R → USB-TTL TX
   - ESP32 U0T → USB-TTL RX

2. Flashe den ESP32 mit PlatformIO:
   ```
   pio run -t upload
   ```

3. Nach dem Flashen:
   - Trenne GPIO0 von GND
   - Starte den ESP32 neu

## Konfiguration

Passe folgende Einstellungen in `src/main.cpp` an:
- Deep Sleep-Dauer (standardmäßig 120 Sekunden / 2 Minuten)
- WiFi-Zugangsdaten
- Server-IP-Adresse und Port
- Bei Bedarf den Pin des DHT11-Sensors (standardmäßig Pin 13)

## Daten

- Alle aufgenommenen Bilder werden im Ordner `camera_images` gespeichert
- Temperatur- und Luftfeuchtigkeitsdaten werden in der Datei `data_gas.csv` gespeichert, zusammen mit Zeitstempeln und Referenzen zu den zugehörigen Bildern 