# gas_visualizer.py

import csv
import calendar
from collections import defaultdict
from flask import Flask, render_template, send_file
import matplotlib.pyplot as plt
import matplotlib
import matplotlib.ticker as mticker # Import für Achsen-Formatierung
matplotlib.use('Agg')  # Nicht-interaktives Backend für Serverbetrieb
import io
from datetime import datetime
import os
import locale  # Für deutsche Wochentagsnamen (alternativ mapping)
import numpy as np
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator
from dotenv import load_dotenv
import base64

# Lade Umgebungsvariablen aus .env-Datei
load_dotenv()

# --- Versuch, deutsches Locale zu setzen (kann auf Servern variieren) ---
try:
    locale.setlocale(locale.LC_TIME, 'de_DE.UTF-8') # Versuch für Linux/macOS
    USE_LOCALE_WEEKDAY = True
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'de-DE') # Versuch für Windows
        USE_LOCALE_WEEKDAY = True
    except locale.Error:
        print("Warnung: Deutsches Locale konnte nicht gesetzt werden. Wochentage könnten auf Englisch sein.")
        USE_LOCALE_WEEKDAY = False # Fallback auf Mapping

# Fallback-Mapping für Wochentage (falls Locale nicht funktioniert)
WEEKDAY_MAP_DE = {
    0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag",
    4: "Freitag", 5: "Samstag", 6: "Sonntag"
}

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'))

# --- Konfiguration ---
DATA_FILE = os.getenv("GAS_DATA_FILE", os.path.join(os.path.dirname(__file__), "gas_hourly.csv")) # Eingabedatei
PORT_NUMBER = int(os.getenv("PORT_NUMBER", "5001")) # Port für den Webserver
# --- Ende Konfiguration ---

# Sicherstellen, dass das templates-Verzeichnis existiert
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
if not os.path.exists(TEMPLATE_DIR):
    os.makedirs(TEMPLATE_DIR)

def load_gas_data():
    """Liest die Gas-Daten aus der CSV-Datei und gruppiert sie nach Tagen."""
    data_by_day = defaultdict(lambda: [(0.0, 0.0)] * 24) # (Verbrauch kWh, Kosten €)

    try:
        with open(DATA_FILE, 'r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            required_columns = ['Timestamp', 'Verbrauch (kWh)', 'Kosten (€)']
            if not reader.fieldnames or not all(col in reader.fieldnames for col in required_columns):
                missing = [col for col in required_columns if not reader.fieldnames or col not in reader.fieldnames]
                print(f"Fehler: Fehlende Spalten in '{DATA_FILE}': {', '.join(missing)}")
                return {}

            for row in reader:
                try:
                    timestamp_str = row['Timestamp']
                    verbrauch_kwh_str = row['Verbrauch (kWh)']
                    kosten_euro_str = row['Kosten (€)']

                    dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:00')
                    day = dt.strftime('%Y-%m-%d')
                    hour = dt.hour

                    verbrauch_kwh = float(verbrauch_kwh_str.replace(',', '.'))
                    kosten_euro = float(kosten_euro_str.replace(',', '.'))

                    if 0 <= hour < 24:
                        current_data = list(data_by_day[day])
                        current_data[hour] = (verbrauch_kwh, kosten_euro)
                        data_by_day[day] = tuple(current_data)
                    else:
                        print(f"Warnung: Ungültige Stunde {hour} in Zeile: {row}")

                except (ValueError, KeyError, IndexError, TypeError) as e:
                    print(f"Warnung: Zeile konnte nicht verarbeitet werden: {row}. Fehler: {e}")
                    continue

    except FileNotFoundError:
        print(f"Fehler: Datei '{DATA_FILE}' wurde nicht gefunden.")
        return {}
    except Exception as e:
        print(f"Ein unerwarteter Fehler beim Lesen der Datei ist aufgetreten: {e}")
        return {}

    return data_by_day

def create_gas_plot(day, hourly_data):
    """Erstellt ein Kosten-Diagramm (€) für einen Tag, mit kWh-Verbrauch (1 Dez.) als Label."""
    fig, ax = plt.subplots(figsize=(12, 7))

    hours = list(range(24))
    verbrauch_values = [data[0] for data in hourly_data] # Index 0 = Verbrauch kWh
    kosten_values = [data[1] for data in hourly_data]    # Index 1 = Kosten €

    bars = ax.bar(hours, kosten_values, color='darkred', alpha=0.8)
    ax.set_title(f'Gaskosten (€) am {day}')
    ax.set_xlabel('Stunde des Tages')
    ax.set_ylabel('Kosten (€)')

    # --- Y-Achsen-Formatierung: Immer 2 Nachkommastellen ---
    formatter = mticker.FormatStrFormatter('%.2f')
    ax.yaxis.set_major_formatter(formatter)
    # --- Ende Y-Achsen-Formatierung ---

    ax.set_xticks(hours)
    ax.set_xticklabels([f'{h:02d}' for h in hours])
    ax.grid(True, axis='y', linestyle='--', alpha=0.6)

    # --- Label-Änderungen: Verbrauch (kWh) über Balken (1 Dez., ohne Einheit) ---
    for i, bar in enumerate(bars):
        kosten = kosten_values[i]
        verbrauch = verbrauch_values[i]
        if kosten > 0:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.,
                height * 1.01,
                f'{verbrauch:.1f}', # Geändert: 1 Dezimalstelle, keine Einheit
                ha='center',
                va='bottom',
                fontsize=8,
                rotation=0
            )
    # --- Ende Label-Änderungen ---

    max_value = max(kosten_values) if any(v > 0 for v in kosten_values) else 1
    ax.set_ylim(0, max_value * 1.20)

    plt.tight_layout()
    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plt.close(fig)

    return img

@app.route('/')
def index():
    """Startseite mit Links, Diagrammen, Wochentagen und Tagesgesamtverbrauch/-kosten."""
    data_by_day = load_gas_data()
    days_sorted = sorted(data_by_day.keys(), reverse=True)

    day_infos = []
    for day in days_sorted:
        try:
            dt_obj = datetime.strptime(day, '%Y-%m-%d')
            if USE_LOCALE_WEEKDAY:
                 weekday_name = dt_obj.strftime('%A').capitalize()
            else:
                 weekday_num = dt_obj.weekday()
                 weekday_name = WEEKDAY_MAP_DE.get(weekday_num, "Unbekannt")

            # --- Tagesgesamtverbrauch UND -kosten berechnen ---
            total_kwh = sum(data[0] for data in data_by_day[day])
            total_cost = sum(data[1] for data in data_by_day[day])
            # --- Ende Berechnung ---

            day_infos.append({
                'date': day,
                'weekday': weekday_name,
                'total_kwh': total_kwh,
                'total_cost': total_cost # Hinzugefügt
            })
        except ValueError:
            print(f"Warnung: Konnte Datum nicht parsen: {day}")
            continue

    return render_template('index_gas.html', day_infos=day_infos, data_file=DATA_FILE) # data_file übergeben für Fehlermeldung


@app.route('/plot/gas/<day>')
def plot_gas(day):
    """Gibt das Gas-Kosten-Diagramm für einen bestimmten Tag zurück."""
    data_by_day = load_gas_data()

    if day not in data_by_day:
        return "Tag nicht gefunden", 404

    img = create_gas_plot(day, data_by_day[day])
    return send_file(img, mimetype='image/png')

# HTML-Template für Gas (angepasst für Gesamtkosten)
index_gas_html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>Gasverbrauch Visualisierung</title>
    <style>
        body {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f8f9fa;
            color: #212529;
        }
        h1 {
            color: #343a40;
            text-align: center;
            margin-bottom: 30px;
        }
        .container {
            max-width: 1100px;
            margin: 0 auto;
            background-color: #ffffff;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 15px rgba(0,0,0,0.08);
        }
        .day-list {
            list-style-type: none;
            padding: 0;
        }
        .day-item {
            margin-bottom: 30px;
            padding: 20px;
            background-color: #f1f3f5;
            border-radius: 6px;
            border: 1px solid #dee2e6;
        }
        .day-header {
            display: block;
            margin-bottom: 15px;
            font-size: 1.1em;
        }
        .day-link {
            color: #c92a2a;
            text-decoration: none;
            font-weight: bold;
        }
        .day-link:hover {
            text-decoration: underline;
        }
        .daily-totals { /* Umbenannt von total-consumption */
            color: #495057; /* Etwas dunkleres Grau */
            font-size: 0.9em;
            margin-left: 15px; /* Mehr Abstand */
            white-space: nowrap; /* Verhindert Umbruch bei schmalen Fenstern */
        }
        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin-top: 10px;
            border: 1px solid #ced4da;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Gasverbrauch Visualisierung</h1>
        {% if not day_infos %}
            <p style="text-align:center;">Keine Daten gefunden oder Datei '{{ data_file }}' konnte nicht gelesen werden. Bitte Konsole auf Fehler prüfen.</p>
        {% else %}
            <ul class="day-list">
                {% for info in day_infos %}
                <li class="day-item">
                    <span class="day-header">
                        <a class="day-link" id="{{ info.date }}" href="#{{ info.date }}">{{ info.date }} ({{ info.weekday }})</a>
                        <!-- Geändert: Gesamt-kWh und Gesamt-Kosten anzeigen -->
                        <span class="daily-totals">Gesamt: {{ '%.2f'|format(info.total_kwh) }} kWh / {{ '%.2f'|format(info.total_cost) }} €</span>
                    </span>
                    <img src="/plot/gas/{{ info.date }}" alt="Gaskosten am {{ info.date }}">
                </li>
                {% endfor %}
            </ul>
        {% endif %}
    </div>
</body>
</html>'''

template_path = os.path.join(TEMPLATE_DIR, 'index_gas.html')
try:
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(index_gas_html_content)
    print(f"Template '{template_path}' erfolgreich erstellt/überschrieben.")
except IOError as e:
    print(f"Fehler beim Schreiben des Templates '{template_path}': {e}")


if __name__ == '__main__':
    print(f"Starting gas visualizer server at http://localhost:{PORT_NUMBER}")
    print(f"Data file: {DATA_FILE}")
    app.run(debug=bool(os.getenv("SERVER_DEBUG", "True").lower() == "true"), port=PORT_NUMBER, host='0.0.0.0')