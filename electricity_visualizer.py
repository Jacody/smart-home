# --- START OF FILE electricity_visualizer.py ---

import csv
import calendar
from collections import defaultdict
from flask import Flask, render_template, send_file
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Nicht-interaktives Backend
import matplotlib.ticker as mticker
import io
from datetime import datetime
import os
import locale # Import für Wochentage hinzugefügt
import numpy as np
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator
import base64
from dotenv import load_dotenv

# Lade Umgebungsvariablen aus .env-Datei
load_dotenv()

# Konfiguration
PORT_NUMBER = int(os.getenv("PORT_NUMBER", "5001"))
DATA_FILE = os.getenv("ELEC_DATA_FILE", "hourly_counts.csv")

app = Flask(__name__)

# --- Locale für deutsche Wochentage setzen ---
try:
    locale.setlocale(locale.LC_TIME, 'de_DE.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'de_DE')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'German_Germany') # Für Windows
        except locale.Error:
            print("Warnung: Deutsches Locale konnte nicht gesetzt werden. Wochentage könnten auf Englisch sein.")
            pass # Standard-Locale beibehalten


# Stellen Sie sicher, dass das templates-Verzeichnis existiert
if not os.path.exists('templates'):
    os.makedirs('templates')

def load_data():
    """Liest die Daten aus der CSV-Datei und gruppiert sie nach Tagen"""
    data_by_day = defaultdict(lambda: [(0.0, 0.0)] * 24)

    try:
        with open(DATA_FILE, 'r') as file:
            reader = csv.reader(file)
            next(reader)  # Header überspringen
            for row in reader:
                if len(row) >= 4:
                    hour_str, _, verbrauch_str, kosten_str = row
                    try:
                        dt = datetime.strptime(hour_str, '%Y-%m-%d %H:00')
                        day = dt.strftime('%Y-%m-%d')
                        hour = dt.hour
                        verbrauch = float(verbrauch_str)
                        kosten = float(kosten_str.replace('€', '').strip())

                        current_day_data = list(data_by_day[day])
                        while len(current_day_data) < 24:
                            current_day_data.append((0.0, 0.0))

                        if 0 <= hour < 24:
                           current_day_data[hour] = (verbrauch, kosten)
                           data_by_day[day] = tuple(current_day_data)

                    except (ValueError, IndexError):
                        print(f"Warnung: Konnte Zeile nicht verarbeiten: {row}")
                        continue
    except FileNotFoundError:
        print(f"Datei '{DATA_FILE}' wurde nicht gefunden.")

    return {day: list(hourly_data) for day, hourly_data in data_by_day.items()}


def create_plot(day, hourly_data):
    """Erstellt ein Diagramm für einen bestimmten Tag (Kosten auf Y-Achse)"""
    fig, ax = plt.subplots(figsize=(10, 6))
    hours = list(range(24))
    verbrauch_values = [data[0] for data in hourly_data]
    kosten_values = [data[1] for data in hourly_data]

    bars = ax.bar(hours, kosten_values, color='green', alpha=0.7)
    ax.set_title(f'Stündliche Stromkosten & Verbrauch am {day}')
    ax.set_xlabel('Stunde')
    ax.set_ylabel('Kosten (€)')
    ax.set_xticks(hours)
    ax.set_xticklabels([f'{(h+1):02d}' for h in hours])
    ax.grid(True, linestyle='--', alpha=0.7)

    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.2f €'))

    max_kosten = max(kosten_values) if any(k > 0 for k in kosten_values) else 0.1
    text_offset = max_kosten * 0.015 # Dynamischer Offset basierend auf maximalen Kosten

    for i, bar in enumerate(bars):
        if kosten_values[i] > 0.0001:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.,
                height + text_offset, # Angepasster Offset
                f'{verbrauch_values[i]:.1f}', # Verbrauch mit 1 Dezimalstelle
                ha='center',
                va='bottom',
                fontsize=8
            )

    ax.set_ylim(0, max_kosten * 1.25) # Etwas mehr Platz nach oben

    img = io.BytesIO()
    plt.tight_layout()
    fig.savefig(img, format='png')
    img.seek(0)
    plt.close(fig)
    return img


@app.route('/')
def index():
    """Startseite mit Links, Wochentagen und Tagesgesamtsummen"""
    data_by_day = load_data()
    sorted_days = sorted(data_by_day.keys())

    daily_summary = []
    for day_str in sorted_days:
        hourly_data = list(data_by_day[day_str])
        while len(hourly_data) < 24:
            hourly_data.append((0.0, 0.0))
        hourly_data = hourly_data[:24]

        total_kwh = sum(item[0] for item in hourly_data)
        total_eur = sum(item[1] for item in hourly_data)

        try:
            dt = datetime.strptime(day_str, '%Y-%m-%d')
            weekday = dt.strftime('%A')
        except ValueError:
            weekday = ""

        daily_summary.append({
            'date': day_str,
            'weekday': weekday,
            'total_kwh': total_kwh,
            'total_eur': total_eur
        })

    return render_template('index.html', daily_summary=daily_summary)

@app.route('/plot/<day>')
def plot(day):
    """Gibt das Diagramm für einen bestimmten Tag zurück"""
    data_by_day = load_data()

    if day not in data_by_day:
        return "Tag nicht gefunden", 404

    day_data = list(data_by_day[day])
    while len(day_data) < 24:
        day_data.append((0.0, 0.0))

    img = create_plot(day, day_data[:24])
    return send_file(img, mimetype='image/png')

# --- HTML-Template wird beim Start erstellt (angepasst) ---
# Stelle sicher, dass das templates-Verzeichnis existiert
if not os.path.exists('templates'):
    os.makedirs('templates')

# --- START DER ÄNDERUNG IM TEMPLATE ---
with open('templates/index.html', 'w', encoding='utf-8') as f: # UTF-8 für Umlaute
    f.write('''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>Stromverbrauch Visualisierung</title>
    <style>
        body {
            font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;
        }
        h1, h2 { color: #333; }
        .container {
            max-width: 1000px; margin: 0 auto; background-color: white;
            padding: 20px; border-radius: 5px; box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        .nav-list { list-style-type: none; padding: 0; margin-bottom: 20px; }
        .nav-list li { display: inline; margin-right: 10px; }
        .day-list { list-style-type: none; padding: 0; }
        .day-item {
            margin-bottom: 25px; padding: 20px; background-color: #f9f9f9;
            border-radius: 5px; border: 1px solid #eee;
        }
        .day-item h2 { margin-top: 0; margin-bottom: 5px; }
        .daily-totals { font-size: 0.9em; color: #555; margin-bottom: 15px; }
        .day-link { color: #0066cc; text-decoration: none; font-weight: bold; }
        .day-link:hover { text-decoration: underline; }
        .weekday { font-weight: normal; color: #666; font-size: 0.9em; }
        :target::before {
          content: ""; display: block; height: 60px; margin-top: -60px; visibility: hidden;
        }
        img {
            max-width: 100%; height: auto; border: 1px solid #ddd;
            border-radius: 4px; display: block; margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Stromkosten & Verbrauch Visualisierung</h1>
        <p>Wähle einen Tag:</p>
        <ul class="nav-list">
            {% for day_info in daily_summary %}
            <li>
                <a class="day-link" href="#{{ day_info.date }}">
                    {{ day_info.date }} <span class="weekday">({{ day_info.weekday }})</span>
                </a>
            </li>
            {% endfor %}
        </ul>
        <hr>
        <ul class="day-list">
            {% for day_info in daily_summary %}
            <li class="day-item" id="{{ day_info.date }}">
                <h2>{{ day_info.date }} ({{ day_info.weekday }})</h2>
                <p class="daily-totals">
                    <!-- Hier die Änderung: "Gesamt Strom:" statt "Gesamt:" -->
                    Gesamt Strom: {{ "%.1f" | format(day_info.total_kwh) }} kWh / {{ "%.2f" | format(day_info.total_eur) }} €
                </p>
                <img src="/plot/{{ day_info.date }}" alt="Stromkosten & Verbrauch am {{ day_info.date }}">
            </li>
            {% endfor %}
        </ul>
    </div>
</body>
</html>''')
# --- ENDE DER ÄNDERUNG IM TEMPLATE ---


if __name__ == '__main__':
    print(f"Starting electricity visualizer server at http://localhost:{PORT_NUMBER}")
    print(f"Data file: {DATA_FILE}")
    if not os.path.exists('templates/index.html'):
        print("Fehler: Template konnte nicht erstellt werden.")
    else:
        print("Besuche http://127.0.0.1:5000/ (oder die IP deines Servers) in deinem Browser")
        app.run(debug=bool(os.getenv("SERVER_DEBUG", "True").lower() == "true"), port=PORT_NUMBER, host='0.0.0.0')
# --- END OF FILE electricity_visualizer.py ---