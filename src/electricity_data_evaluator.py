import csv
from datetime import datetime
from collections import defaultdict
import os

# Pfade zu den Dateien
current_dir = os.path.dirname(__file__)
input_file = os.path.join(current_dir, 'electricity_data.csv')
output_file = os.path.join(current_dir, 'hourly_counts.csv')

# Daten einlesen und nach Stunden gruppieren
timestamp_counts = defaultdict(int)

with open(input_file, 'r') as file:
    reader = csv.reader(file)
    for row in reader:
        if len(row) == 2:  # Prüfen, ob die Zeile zwei Spalten hat
            _, timestamp_str = row
            try:
                # Zeitstempel parsen
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                # Stunde extrahieren und für die Ausgabe formatieren
                hour_key = timestamp.strftime('%Y-%m-%d %H:00')
                # Zählung für diese Stunde erhöhen
                timestamp_counts[hour_key] += 1
            except ValueError:
                # Ungültiges Datumsformat überspringen
                continue

# Ergebnisse in eine neue CSV-Datei schreiben
with open(output_file, 'w', newline='') as output_file:
    writer = csv.writer(output_file)
    writer.writerow(['Stunde', 'Anzahl', 'Verbrauch', 'Kosten'])
    
    # Stunden sortieren und Daten schreiben
    for hour in sorted(timestamp_counts.keys()):
        count = timestamp_counts[hour]
        # Verbrauch berechnen: Anzahl der Datenpunkte * (1/75) kWh
        verbrauch = count * (1/75)
        # Kosten berechnen: Verbrauch * 41 Cent
        kosten = verbrauch * 0.41
        writer.writerow([hour, count, f"{verbrauch:.4f}", f"{kosten:.2f} €"])

print(f"Auswertung abgeschlossen. Ergebnisse wurden in '{output_file}' gespeichert.") 