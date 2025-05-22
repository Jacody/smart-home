from flask import Flask, request, jsonify
import os
import csv
from datetime import datetime
import argparse
import sys
import subprocess
import time
import threading
from dotenv import load_dotenv

# Lade Umgebungsvariablen aus .env-Datei
load_dotenv()

# Importiere image_evaluator direkt, da wir jetzt im selben Verzeichnis sind
try:
    from image_evaluator import evaluate_image
except ImportError:
    print("Warnung: image_evaluator konnte nicht importiert werden. Stelle sicher, dass image_evaluator.py im selben Verzeichnis liegt.")
    # Definiere eine Dummy-Funktion für den Fall, dass das Modul nicht importiert werden kann
    def evaluate_image(image_path, csv_path):
        print(f"Hinweis: Bildauswertung nicht verfügbar. Bild {image_path} wurde nicht ausgewertet.")
        return None

# Importiere den Electricity Evaluator für die Stromverbrauchsberechnung
try:
    import electricity_evaluator
except ImportError:
    print("Warnung: electricity_evaluator konnte nicht importiert werden. Stelle sicher, dass electricity_evaluator.py im selben Verzeichnis liegt.")

app = Flask(__name__)

# Basisverzeichnis bestimmen
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Ordner für gespeicherte Bilder erstellen
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join(BASE_DIR, "camera_images"))
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# CSV-Datei für Sensor-Daten der Kamera
SENSOR_CSV = os.getenv("SENSOR_CSV", os.path.join(os.path.dirname(__file__), "data_gas.csv"))

# Verzeichnis für die Umdrehungsdaten erstellen
DATA_DIR = os.path.join(BASE_DIR, 'data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# CSV-Dateien für Umdrehungsdaten
ELECTRICITY_CSV = os.getenv("ELECTRICITY_CSV", os.path.join(os.path.dirname(__file__), "electricity_data.csv"))
ELECTRICITY_METRICS_CSV = os.getenv("ELECTRICITY_METRICS_CSV", os.path.join(DATA_DIR, "stromzaehler_log.csv"))

# CSV-Header erstellen, falls die Datei noch nicht existiert
if not os.path.exists(SENSOR_CSV):
    with open(SENSOR_CSV, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Timestamp', 'Temperature', 'Humidity', 'ImageFile', 'Number'])
# Prüfen, ob die Number-Spalte in der CSV existiert, falls die CSV bereits vorhanden ist
else:
    try:
        with open(SENSOR_CSV, 'r', newline='') as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader, None)
            if header and 'Number' not in header:
                # Füge Number-Spalte hinzu
                header.append('Number')
                rows = list(reader)
                with open(SENSOR_CSV, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(header)
                    for row in rows:
                        # Füge leeren Wert für Number hinzu
                        if len(row) < len(header):
                            row.append('')
                        writer.writerow(row)
    except Exception as e:
        print(f"Warnung: Fehler beim Überprüfen/Aktualisieren des CSV-Headers: {e}")

def bereinige_alte_dateien():
    """Löscht Dateien, die älter als 240 Stunden sind, aus camera_images und cache."""
    verzeichnisse = [UPLOAD_FOLDER, os.path.join(BASE_DIR, 'cache')]
    max_alter_sekunden = 864000  # 240 Stunden (10 Tage)
    aktuelle_zeit = time.time()
    geloescht_gesamt = 0
    
    for verzeichnis in verzeichnisse:
        if not os.path.exists(verzeichnis):
            continue
            
        for dateiname in os.listdir(verzeichnis):
            dateipfad = os.path.join(verzeichnis, dateiname)
            if os.path.isfile(dateipfad):
                datei_aenderungszeit = os.path.getmtime(dateipfad)
                alter = aktuelle_zeit - datei_aenderungszeit
                
                if alter > max_alter_sekunden:
                    try:
                        os.remove(dateipfad)
                        geloescht_gesamt += 1
                    except Exception as e:
                        print(f"Fehler beim Löschen von {dateipfad}: {e}")
    
    if geloescht_gesamt > 0:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Bereinigung: {geloescht_gesamt} alte Dateien gelöscht")
    
    # Planen der nächsten Bereinigung in 1 Stunde
    threading.Timer(3600, bereinige_alte_dateien).start()

def aktualisiere_stromverbrauchsdaten():
    """
    Aktualisiert die Stromverbrauchsdaten, indem die Metriken neu berechnet werden.
    Diese Funktion wird nach dem Empfang neuer Daten aufgerufen.
    """
    try:
        if 'electricity_evaluator' in sys.modules:
            metrics = electricity_evaluator.get_latest_metrics(ELECTRICITY_CSV)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Stromverbrauchsdaten aktualisiert")
            print(f"Anzahl Umdrehungen: {metrics['rotation_count']}, Verbrauch: {metrics['kwh_consumed']:.4f} kWh, Kosten: {metrics['total_cost_euro']:.3f} €")
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Electricity Evaluator ist nicht verfügbar.")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fehler bei der Aktualisierung der Stromverbrauchsdaten: {e}")

@app.route('/upload', methods=['POST'])
def upload():
    # Verzeichnis für die Daten erstellen, falls es nicht existiert
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    # Aktuellen Zeitstempel für den Dateinamen generieren
    timestamp = int(time.time())
    filename = os.path.join(DATA_DIR, f"received_{timestamp}.csv")
    
    # Empfangene Daten speichern
    data = request.data.decode('utf-8')
    
    with open(filename, "w") as f:
        f.write(data)
    
    # CSV-Daten verarbeiten
    csv_lines = data.strip().split('\n')
    
    # Filtere Header-Zeilen heraus für die Zählung der Datenpunkte
    valid_data_points = [line for line in csv_lines if line.strip() and line.strip().isdigit()]
    
    # Log-Ausgabe
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Daten empfangen und in {filename} gespeichert")
    print(f"Anzahl der Datenpunkte: {len(valid_data_points)}")
    
    # Daten auch in electricity_data.csv schreiben und Metriken berechnen
    for line in csv_lines:
        line = line.strip()
        if line and line.isdigit() and not line.startswith('timestamp'):  # Nur numerische Timestamps
            # Timestamp in das electricity_evaluator-Modul einspeiisen
            if 'electricity_evaluator' in sys.modules:
                try:
                    # Füge den Eintrag hinzu und berechne die Metriken
                    results = electricity_evaluator.add_electricity_data_entry(ELECTRICITY_CSV, int(line))
                    print(f"Neuer Stromzähler-Eintrag verarbeitet: {results['time']}")
                except Exception as e:
                    print(f"Fehler bei der Verarbeitung des Stromzähler-Eintrags: {e}")
                    
                    # Fallback: Schreibe die Daten direkt in die CSV, wie zuvor
                    electricity_data_file = ELECTRICITY_CSV
                    if os.path.exists(electricity_data_file):
                        with open(electricity_data_file, 'a') as tf:
                            time_str = datetime.fromtimestamp(int(line)).strftime('%Y-%m-%d %H:%M:%S')
                            tf.write(f"{line},{time_str}\n")
                    else:
                        # Neue Datei erstellen mit Header
                        with open(electricity_data_file, 'w') as tf:
                            tf.write("timestamp,time\n")
                            time_str = datetime.fromtimestamp(int(line)).strftime('%Y-%m-%d %H:%M:%S')
                            tf.write(f"{line},{time_str}\n")
            else:
                # Fallback: Schreibe die Daten direkt in die CSV, wie zuvor
                electricity_data_file = ELECTRICITY_CSV
                if os.path.exists(electricity_data_file):
                    with open(electricity_data_file, 'a') as tf:
                        time_str = datetime.fromtimestamp(int(line)).strftime('%Y-%m-%d %H:%M:%S')
                        tf.write(f"{line},{time_str}\n")
                else:
                    # Neue Datei erstellen mit Header
                    with open(electricity_data_file, 'w') as tf:
                        tf.write("timestamp,time\n")
                        time_str = datetime.fromtimestamp(int(line)).strftime('%Y-%m-%d %H:%M:%S')
                        tf.write(f"{line},{time_str}\n")
    
    # Nach dem Hinzufügen aller Daten die Metriken aktualisieren
    if valid_data_points and 'electricity_evaluator' in sys.modules:
        aktualisiere_stromverbrauchsdaten()
    
    return "OK", 200

@app.route('/api/camera', methods=['POST'])
def receive_image():
    # Überprüfen, ob ein Bild empfangen wurde
    if 'Content-Type' not in request.headers or 'image/jpeg' not in request.headers['Content-Type']:
        return jsonify({'error': 'Kein JPEG-Bild empfangen'}), 400
    
    # Bild aus der Anfrage extrahieren
    img_data = request.data
    
    # Zeitstempel für den Dateinamen
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{UPLOAD_FOLDER}/cam_{timestamp}.jpg"
    
    # Bild speichern
    with open(filename, 'wb') as f:
        f.write(img_data)
    
    # Sensor-Daten aus dem Header extrahieren
    temperature = request.headers.get('X-Temperature', 'N/A')
    humidity = request.headers.get('X-Humidity', 'N/A')
    
    # Aktueller Zeitstempel im Format für die CSV-Datei
    csv_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Speichere zunächst die Sensordaten in CSV ohne OCR-Nummer
    with open(SENSOR_CSV, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            csv_timestamp,
            temperature,
            humidity,
            filename,
            ""  # Leere Spalte für Number, wird später durch Bildauswertung gefüllt
        ])
    
    print(f"Bild empfangen und gespeichert: {filename}")
    print(f"Bildgröße: {len(img_data)} Bytes")
    print(f"Temperatur: {temperature} °C, Luftfeuchtigkeit: {humidity} %")
    
    # Bildauswertung asynchron starten (nur informativ ausgeben)
    print("Starte Bildauswertung...")
    
    try:
        # Versuche die Bildauswertung direkt als Funktion aufzurufen
        abs_image_path = os.path.abspath(filename)
        abs_csv_path = os.path.abspath(SENSOR_CSV)
        
        # Führe die Bildauswertung aus
        number = evaluate_image(abs_image_path, abs_csv_path)
        
        if number:
            print(f"Bildauswertung abgeschlossen. Erkannte Nummer: {number}")
        else:
            print("Bildauswertung ohne erkannte Nummer abgeschlossen.")
            
            # Alternative: Starte die Bildauswertung als Prozess (nur wenn der direkte Import fehlgeschlagen ist)
            if 'evaluate_image' not in globals() or globals()['evaluate_image'].__module__ != 'image_evaluator':
                try:
                    # Führe das Skript in einem separaten Prozess aus
                    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'image_evaluator.py')
                    subprocess.Popen([sys.executable, script_path, '--image', abs_image_path, '--csv', abs_csv_path],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    print(f"Bildauswertung als separater Prozess gestartet.")
                except Exception as e:
                    print(f"Fehler beim Starten der Bildauswertung als Prozess: {e}")
    except Exception as e:
        print(f"Fehler bei der Bildauswertung: {e}")
    
    return jsonify({
        'status': 'success',
        'message': 'Bild und Sensordaten erfolgreich empfangen',
        'filename': filename,
        'temperature': temperature,
        'humidity': humidity
    })

@app.route('/api/electricity/metrics', methods=['GET'])
def get_electricity_metrics():
    """
    API-Endpunkt zum Abrufen der aktuellen Stromverbrauchsmetriken
    """
    try:
        if 'electricity_evaluator' in sys.modules:
            metrics = electricity_evaluator.get_latest_metrics(ELECTRICITY_CSV)
            return jsonify({
                'status': 'success',
                'rotation_count': metrics['rotation_count'],
                'kwh_consumed': round(metrics['kwh_consumed'], 4),
                'total_cost_euro': round(metrics['total_cost_euro'], 3),
                'last_update': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Electricity Evaluator ist nicht verfügbar'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fehler beim Abrufen der Stromverbrauchsmetriken: {str(e)}'
        }), 500

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Startet den Server für die Gaszähler-Auswertung")
    parser.add_argument('--port', type=int, default=int(os.getenv("SERVER_PORT", "5000")),
                        help='Port, auf dem der Server lauschen soll (Standard: 5000)')
    args = parser.parse_args()

    # Starte den Bereinigungs-Timer
    bereinige_alte_dateien()

    # Server starten
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Server wird gestartet auf http://0.0.0.0:{args.port}")
    app.run(host='0.0.0.0', port=args.port, debug=bool(os.getenv("SERVER_DEBUG", "True").lower() == "true")) 