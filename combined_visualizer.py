# combined_visualizer.py

import csv
import calendar
from collections import defaultdict
from flask import Flask, render_template, send_file, request, abort
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import matplotlib.image as mpimg
import numpy as np
import io
from datetime import datetime, timedelta
import os
import locale
import base64 # Import base64 module
import argparse
from dotenv import load_dotenv

# Lade Umgebungsvariablen aus .env-Datei
load_dotenv()

# Konfiguration
PORT_NUMBER = int(os.getenv("PORT_NUMBER", "5001"))
ELEC_DATA_FILE = os.getenv("ELEC_DATA_FILE", "hourly_counts.csv")
GAS_DATA_FILE = os.getenv("GAS_DATA_FILE", "gas_hourly.csv")

app = Flask(__name__)

# --- Imports and Configuration (Keep as before) ---
PLOT_TITLE_FONTSIZE = 14
AXIS_LABEL_FONTSIZE = 10
XTICK_LABEL_FONTSIZE = 8 # Adjusted for weekly plot
LEGEND_FONTSIZE = 9
KWH_LABEL_FONTSIZE = 7
# --- End Configuration ---

# --- Locale Setting (Keep as before) ---
try:
    locale.setlocale(locale.LC_TIME, 'de_DE.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'German_Germany')
    except locale.Error:
        print("Warnung: Deutsches Locale für Wochentage konnte nicht gesetzt werden.")
        pass # Keep going with default locale if German fails

TEMPLATE_DIR = 'templates'
if not os.path.exists(TEMPLATE_DIR):
    os.makedirs(TEMPLATE_DIR)

# --- Data Loading (Keep load_combined_data as before) ---
def load_combined_data():
    # ... (Keep the existing load_combined_data function exactly as it was) ...
    """Reads data from both electricity and gas CSV files and merges them by day and hour."""
    data_by_day = defaultdict(lambda: [((0.0, 0.0), (0.0, 0.0))] * 24) # (elec_kwh, elec_cost), (gas_kwh, gas_cost)
    # --- Load Electricity Data ---
    try:
        with open(ELEC_DATA_FILE, 'r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            try:
                header = next(reader) # Skip header
            except StopIteration:
                # print(f"Warnung: Strom-Datei '{ELEC_DATA_FILE}' ist leer oder hat keinen Header.")
                pass # Continue, maybe gas data exists

            required_elec_cols = 4 # Stunde, Anzahl, Verbrauch, Kosten
            for i, row in enumerate(reader):
                if len(row) >= required_elec_cols:
                    hour_str, _, verbrauch_str, kosten_str = row[:required_elec_cols]
                    try:
                        dt = datetime.strptime(hour_str, '%Y-%m-%d %H:00')
                        day = dt.strftime('%Y-%m-%d')
                        hour = dt.hour
                        # Try converting, default to 0.0 if empty or invalid
                        try:
                            verbrauch_kwh = float(verbrauch_str) if verbrauch_str else 0.0
                        except ValueError:
                            verbrauch_kwh = 0.0
                        try:
                            kosten_euro_str_cleaned = kosten_str.replace('€', '').replace(',', '.').strip()
                            kosten_euro = float(kosten_euro_str_cleaned) if kosten_euro_str_cleaned else 0.0
                        except ValueError:
                            kosten_euro = 0.0

                        if 0 <= hour < 24:
                             # Get existing gas data or default if not yet present
                            existing_gas_data = data_by_day[day][hour][1] if day in data_by_day and len(data_by_day[day]) > hour else (0.0, 0.0)
                            data_by_day[day][hour] = ((verbrauch_kwh, kosten_euro), existing_gas_data)
                    except (ValueError, IndexError) as e:
                        # print(f"Warnung (Strom): Überspringe Zeile {i+2} wegen Fehler: {e}. Zeile: {row}")
                        continue
                # else: print(f"Warnung (Strom): Zeile {i+2} hat nicht genug Spalten ({len(row)} statt {required_elec_cols}). Zeile: {row}")

    except FileNotFoundError:
        print(f"Warnung: Strom-Datei '{ELEC_DATA_FILE}' nicht gefunden.")
    except Exception as e:
        print(f"Fehler beim Lesen der Stromdaten: {e}")

    # --- Load Gas Data ---
    try:
        with open(GAS_DATA_FILE, 'r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            required_gas_columns = ['Timestamp', 'Verbrauch (kWh)', 'Kosten (€)']
            if not reader.fieldnames:
                 # print(f"Warnung: Gas-Datei '{GAS_DATA_FILE}' ist leer oder hat keinen Header.")
                 pass # Continue, maybe elec data exists
            elif not all(col in reader.fieldnames for col in required_gas_columns):
                 print(f"Fehler: Fehlende Spalten in {GAS_DATA_FILE}. Benötigt: {required_gas_columns}. Gefunden: {reader.fieldnames}")
            else:
                for i, row in enumerate(reader):
                    try:
                        # Check if all required keys exist and have non-empty values in the row
                        if not all(key in row and row[key] for key in required_gas_columns):
                            # print(f"Warnung (Gas): Überspringe Zeile {i+2} wegen fehlender/leerer Werte. Zeile: {row}")
                            continue
                        timestamp_str = row['Timestamp']
                        verbrauch_kwh_str = row['Verbrauch (kWh)']
                        kosten_euro_str = row['Kosten (€)']

                        dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:00')
                        day = dt.strftime('%Y-%m-%d')
                        hour = dt.hour

                        # Try converting, default to 0.0 if invalid
                        try:
                            verbrauch_kwh = float(verbrauch_kwh_str.replace(',', '.')) if verbrauch_kwh_str else 0.0
                        except ValueError:
                            verbrauch_kwh = 0.0
                        try:
                            kosten_euro = float(kosten_euro_str.replace(',', '.')) if kosten_euro_str else 0.0
                        except ValueError:
                            kosten_euro = 0.0

                        if 0 <= hour < 24:
                            # Get existing elec data or default if not yet present
                            existing_elec_data = data_by_day[day][hour][0] if day in data_by_day and len(data_by_day[day]) > hour else (0.0, 0.0)
                            data_by_day[day][hour] = (existing_elec_data, (verbrauch_kwh, kosten_euro))
                    except (ValueError, KeyError, IndexError) as e:
                        # print(f"Warnung (Gas): Überspringe Zeile {i+2} wegen Fehler: {e}. Zeile: {row}")
                        continue

    except FileNotFoundError:
        print(f"Warnung: Gas-Datei '{GAS_DATA_FILE}' nicht gefunden.")
    except Exception as e:
        print(f"Fehler beim Lesen der Gasdaten: {e}")

    if not data_by_day:
        print("Keine gültigen Daten zum Verarbeiten gefunden.")
    return dict(data_by_day)

# --- Plotting Function for Daily Combined (Keep as before) ---
def create_combined_plot(day, hourly_data, ax=None):
    """
    Creates a combined bar chart showing COSTS (€) on Y-axis
    and labeling bars with HOURLY COST value (no unit).
    Can draw on a provided Matplotlib axis 'ax' or create its own figure.
    """
    # ... (Keep the existing create_combined_plot function exactly as it was) ...
    img_data = None # Initialize image data as None
    if ax is None:
        fig, ax = plt.subplots(figsize=(15, 7))
        created_figure = True
        # print(f"Debug: create_combined_plot creating NEW figure/axis for day {day}") # Less verbose
    else:
        created_figure = False
        fig = ax.figure
        # print(f"Debug: create_combined_plot using PROVIDED axis for day {day}") # Less verbose


    hours = np.arange(24)
    bar_width = 0.35

    elec_cost_hourly = [data[0][1] for data in hourly_data]
    gas_cost_hourly = [data[1][1] for data in hourly_data]

    # --- Function to add COST labels ---
    def add_cost_labels(rects, cost_values):
        for i, rect in enumerate(rects):
            cost_height = rect.get_height()
            cost_value = cost_values[i]
            if cost_value > 0.001: # Only label values > 0.001 €
                ax.text(rect.get_x() + rect.get_width() / 2., cost_height,
                        f'{cost_value:.2f}',
                        ha='center', va='bottom', fontsize=KWH_LABEL_FONTSIZE, rotation=0,
                        bbox=dict(boxstyle='round,pad=0.15', fc='white', alpha=0.6, ec='none'))
    # --- End Function ---

    rects1 = ax.bar(hours - bar_width/2, elec_cost_hourly, bar_width, label='Strom Kosten (€)', color='cornflowerblue', alpha=0.85)
    rects2 = ax.bar(hours + bar_width/2, gas_cost_hourly, bar_width, label='Gas Kosten (€)', color='darkorange', alpha=0.85)

    ax.set_xlabel('Stunde des Tages', fontsize=AXIS_LABEL_FONTSIZE)
    ax.set_ylabel('Stündliche Kosten (€)', fontsize=AXIS_LABEL_FONTSIZE)

    try:
        dt_obj = datetime.strptime(day, '%Y-%m-%d')
        # Try German full name, fallback to abbreviation or English if locale failed
        try:
            weekday_name = dt_obj.strftime('%A') # Full name if locale is set
        except ValueError: # Fallback for potential issues
            weekday_name = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"][dt_obj.weekday()]
        title = f'{weekday_name}, {day}'
    except Exception:
        title = f'Tag: {day}' # Fallback title

    ax.set_title(title, fontsize=PLOT_TITLE_FONTSIZE, pad=10) # Adjusted padding
    ax.set_xticks(hours)
    # Use only hour numbers for x-tick labels in daily plot
    ax.set_xticklabels([f'{h:02d}' for h in hours], fontsize=XTICK_LABEL_FONTSIZE)
    ax.legend(fontsize=LEGEND_FONTSIZE)
    ax.grid(True, axis='y', linestyle='--', alpha=0.6)

    formatter = matplotlib.ticker.FormatStrFormatter('%.2f €')
    ax.yaxis.set_major_formatter(formatter)

    add_cost_labels(rects1, elec_cost_hourly)
    add_cost_labels(rects2, gas_cost_hourly)

    # Find max cost including labels to adjust ylim
    max_elec_cost = max(elec_cost_hourly) if elec_cost_hourly else 0
    max_gas_cost = max(gas_cost_hourly) if gas_cost_hourly else 0
    max_hourly_cost = max(max_elec_cost, max_gas_cost)

    # Simple heuristic: if max cost is very small, use a fixed minimum height
    if max_hourly_cost < 0.05:
        ylimit_upper = 0.10
    else:
        ylimit_upper = max_hourly_cost * 1.35 # Buffer for labels

    ax.set_ylim(0, ylimit_upper)

    if created_figure:
        # print(f"Debug: create_combined_plot saving and closing ITS OWN figure for day {day}")
        img_data = io.BytesIO()
        fig.tight_layout(pad=1.0) # Add padding
        fig.savefig(img_data, format='png', bbox_inches='tight')
        img_data.seek(0)
        plt.close(fig)

    return ax, img_data


# --- *** NEW Plotting Function for Weekly Summary *** ---
def create_weekly_summary_plot(daily_summaries, kw_str):
    """
    Creates a bar chart summarizing total daily costs for a week.

    Args:
        daily_summaries (list): List of daily summary dicts for the week.
                                Each dict must contain 'weekday', 'total_elec_cost', 'total_gas_cost'.
        kw_str (str): The calendar week string (e.g., '2024-18').

    Returns:
        io.BytesIO: BytesIO object containing the PNG image data, or None if error.
    """
    if not daily_summaries:
        return None

    # Extract data, ensuring chronological order (already sorted in index route)
    # Use German abbreviations for weekdays on X-axis
    weekdays_short = [s['weekday'][:2] for s in daily_summaries] # Mo, Di, Mi...
    elec_costs_daily = [s['total_elec_cost'] for s in daily_summaries]
    gas_costs_daily = [s['total_gas_cost'] for s in daily_summaries]

    num_days = len(weekdays_short)
    x_indices = np.arange(num_days) # 0, 1, 2... for x-axis positions
    bar_width = 0.35

    fig, ax = plt.subplots(figsize=(12, 6)) # Adjust size as needed

    # --- Function to add COST labels (adapted for daily totals) ---
    def add_daily_cost_labels(rects, cost_values):
        for i, rect in enumerate(rects):
            cost_height = rect.get_height()
            cost_value = cost_values[i]
            if cost_value > 0.001: # Only label non-zero costs
                ax.text(rect.get_x() + rect.get_width() / 2., cost_height,
                        f'{cost_value:.2f}€', # Add € symbol here
                        ha='center', va='bottom', fontsize=KWH_LABEL_FONTSIZE + 1, rotation=0, # Slightly larger font
                        bbox=dict(boxstyle='round,pad=0.15', fc='white', alpha=0.7, ec='none'))
    # --- End Function ---

    rects1 = ax.bar(x_indices - bar_width/2, elec_costs_daily, bar_width, label='Strom Kosten (€)', color='cornflowerblue', alpha=0.9)
    rects2 = ax.bar(x_indices + bar_width/2, gas_costs_daily, bar_width, label='Gas Kosten (€)', color='darkorange', alpha=0.9)

    ax.set_xlabel('Wochentag', fontsize=AXIS_LABEL_FONTSIZE)
    ax.set_ylabel('Gesamte Tageskosten (€)', fontsize=AXIS_LABEL_FONTSIZE)

    try:
        year, week = map(int, kw_str.split('-'))
        title = f'Wochenübersicht Kosten - KW {week}, {year}'
    except ValueError:
         title = f'Wochenübersicht Kosten - {kw_str}'

    ax.set_title(title, fontsize=PLOT_TITLE_FONTSIZE, pad=15)
    ax.set_xticks(x_indices)
    ax.set_xticklabels(weekdays_short, fontsize=XTICK_LABEL_FONTSIZE + 1) # Use short weekday names, slightly larger font
    ax.legend(fontsize=LEGEND_FONTSIZE)
    ax.grid(True, axis='y', linestyle='--', alpha=0.6)

    formatter = matplotlib.ticker.FormatStrFormatter('%.2f €')
    ax.yaxis.set_major_formatter(formatter)

    add_daily_cost_labels(rects1, elec_costs_daily)
    add_daily_cost_labels(rects2, gas_costs_daily)

    # Adjust Y limit based on max daily total cost
    max_elec_daily = max(elec_costs_daily) if elec_costs_daily else 0
    max_gas_daily = max(gas_costs_daily) if gas_costs_daily else 0
    max_total_daily = max(max_elec_daily, max_gas_daily)
    ax.set_ylim(0, max_total_daily * 1.25) # 25% buffer for labels

    # Save to BytesIO
    img_data = io.BytesIO()
    try:
        fig.tight_layout(pad=1.0)
        fig.savefig(img_data, format='png', bbox_inches='tight')
        img_data.seek(0)
        plt.close(fig) # Close the figure
        print(f"Wöchentlicher Übersichtsplot für KW {kw_str} erstellt.")
        return img_data
    except Exception as e:
        print(f"Fehler beim Erstellen/Speichern des wöchentlichen Plots: {e}")
        plt.close(fig)
        return None


# --- Flask Routes ---

# --- Index Route (Modified to generate and pass weekly plot) ---
@app.route('/')
def index():
    """
    Main page: Handles selection of calendar week (KW) via dropdown.
    Shows weekly summary plot, plots and summaries for the selected week.
    Accepts 'kw' query parameter (e.g., /?kw=2024-18).
    Defaults to the latest available week if no 'kw' is provided.
    """
    print("Request received for index page.")
    data_by_day = load_combined_data()
    all_daily_summaries = []
    available_kws = set()

    print(f"Calculating summaries for {len(data_by_day)} days...")
    # --- Calculate summaries and extract available weeks ---
    for day, hourly_data in data_by_day.items():
        try:
            dt = datetime.strptime(day, '%Y-%m-%d')
            year, week_num, _ = dt.isocalendar()
            kw_str = f"{year}-{week_num:02d}"
            available_kws.add(kw_str)

            try:
                # Attempt to get German full weekday name
                weekday_name = dt.strftime('%A')
            except ValueError:
                # Fallback if locale/strftime fails
                weekday_name = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"][dt.weekday()]
            except Exception as e:
                 print(f"Error getting weekday for {day}: {e}")
                 weekday_name = "Unbekannt" # Generic fallback

            total_elec_kwh = sum(h[0][0] for h in hourly_data)
            total_elec_cost = sum(h[0][1] for h in hourly_data)
            total_gas_kwh = sum(h[1][0] for h in hourly_data)
            total_gas_cost = sum(h[1][1] for h in hourly_data)

            all_daily_summaries.append({
                'day': day,
                'weekday': weekday_name,
                'kw': kw_str,
                'total_elec_kwh': total_elec_kwh,
                'total_elec_cost': total_elec_cost,
                'total_gas_kwh': total_gas_kwh,
                'total_gas_cost': total_gas_cost,
            })
        except ValueError:
            print(f"Error parsing date: {day}. Skipping this day.")
            continue
        except IndexError:
            print(f"Error accessing hourly data for day {day} (length {len(hourly_data)}). Skipping.")
            continue


    sorted_available_kws = sorted(list(available_kws), reverse=True)

    # --- Determine selected week ---
    selected_kw = request.args.get('kw')

    if not selected_kw and sorted_available_kws:
        selected_kw = sorted_available_kws[0]
        print(f"No week selected, defaulting to latest: {selected_kw}")
    elif selected_kw and selected_kw not in available_kws:
        print(f"Warnung: Ausgewählte Woche '{selected_kw}' nicht in Daten gefunden.")
        original_selection = selected_kw
        selected_kw = sorted_available_kws[0] if sorted_available_kws else None
        print(f"Ungültige Auswahl '{original_selection}', wechsle zu: {selected_kw}")


    # --- Filter summaries and Generate Weekly Plot ---
    filtered_summaries = []
    weekly_plot_base64 = None # Initialize weekly plot data as None

    if selected_kw:
        print(f"Filtering data for week: {selected_kw}")
        # Filter first
        filtered_summaries = [s for s in all_daily_summaries if s['kw'] == selected_kw]
        # Then sort the filtered list by date (day)
        filtered_summaries.sort(key=lambda x: x['day'])

        # *** Generate weekly summary plot if data exists for the week ***
        if filtered_summaries:
            print(f"Attempting to generate weekly summary plot for {selected_kw}...")
            weekly_plot_img_data = create_weekly_summary_plot(filtered_summaries, selected_kw)
            if weekly_plot_img_data:
                # Encode the PNG image data as Base64
                weekly_plot_base64 = base64.b64encode(weekly_plot_img_data.getvalue()).decode('utf-8')
                print("Weekly summary plot generated and encoded as Base64.")
            else:
                print("Failed to generate weekly summary plot.")
        else:
             print(f"No summaries found for KW {selected_kw} to generate weekly plot.")

    else:
        print("Keine Woche ausgewählt oder keine Daten verfügbar.")


    print(f"Prepared {len(filtered_summaries)} daily summaries for display (KW: {selected_kw}).")

    return render_template(
        'index_combined.html',
        daily_summaries=filtered_summaries,
        available_kws=sorted_available_kws,
        selected_kw=selected_kw,
        weekly_plot_base64=weekly_plot_base64 # Pass base64 data to template
    )

# --- Plot Route for Single Day (Keep as before) ---
@app.route('/plot/combined/<day>')
def plot_combined(day):
    """Serves the combined plot image for a specific day."""
    print(f"Request received for SINGLE plot for day: {day}")
    data_by_day = load_combined_data()

    if day not in data_by_day:
        print(f"Error: Day {day} not found in data.")
        abort(404, description=f"Daten für Tag {day} nicht gefunden.")

    hourly_data = data_by_day[day]
    _, img_data = create_combined_plot(day, hourly_data, ax=None)

    if img_data:
        print(f"Generated single plot (Cost Y-axis) for {day}.")
        return send_file(img_data, mimetype='image/png')
    else:
        print(f"Error: Failed to generate single plot image for {day}")
        abort(500, description="Fehler beim Erstellen des Einzelbildes.")


# --- Route for Weekly Report Download (Keep as before) ---
@app.route('/report/week/<kw_str>')
def download_week_report(kw_str):
    """
    Generates a single image containing the weekly summary plot followed by
    plots for all days in the specified calendar week and sends it as a
    downloadable file.
    """
    print(f"Request received for WEEKLY report for KW: {kw_str}")
    data_by_day = load_combined_data()

    # --- 1. Filter data and Calculate Daily Summaries for the Week ---
    days_in_week_data = {}
    weekly_summaries_for_report = [] # Need summaries for the weekly plot

    # Temporary dictionary to hold data before sorting
    temp_week_data = {}

    for day, hourly_data in data_by_day.items():
        try:
            dt = datetime.strptime(day, '%Y-%m-%d')
            year, week_num, _ = dt.isocalendar()
            current_kw_str = f"{year}-{week_num:02d}"

            if current_kw_str == kw_str:
                # Store hourly data keyed by day
                temp_week_data[day] = hourly_data

                # Calculate daily totals needed for the summary plot
                try:
                    weekday_name = dt.strftime('%A')
                except ValueError:
                    weekday_name = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"][dt.weekday()]

                total_elec_kwh = sum(h[0][0] for h in hourly_data)
                total_elec_cost = sum(h[0][1] for h in hourly_data)
                total_gas_kwh = sum(h[1][0] for h in hourly_data)
                total_gas_cost = sum(h[1][1] for h in hourly_data)

                weekly_summaries_for_report.append({
                    'day': day, # Keep day for sorting
                    'weekday': weekday_name, # Keep full name for potential use
                    'total_elec_cost': total_elec_cost,
                    'total_gas_cost': total_gas_cost,
                })

        except (ValueError, IndexError):
             # print(f"Skipping day {day} due to parsing/indexing error during report generation.")
             continue

    if not temp_week_data:
        print(f"Error: No data found for week {kw_str} to generate report.")
        abort(404, description=f"Keine Daten für Kalenderwoche {kw_str} gefunden.")

    # Sort days chronologically
    sorted_days = sorted(temp_week_data.keys())
    # Sort the summaries list to match the sorted days
    weekly_summaries_for_report.sort(key=lambda x: x['day'])
    # Now create the final days_in_week_data in sorted order
    days_in_week_data = {day: temp_week_data[day] for day in sorted_days}

    num_days = len(sorted_days)
    num_plots_total = 1 + num_days # 1 for summary + N for daily plots

    # --- 2. Generate Weekly Summary Plot ---
    print(" -> Generating weekly summary plot for report...")
    weekly_summary_img_data = create_weekly_summary_plot(weekly_summaries_for_report, kw_str)

    # --- 3. Create Figure with Adjusted Layout ---
    # Adjust height: Add height for summary plot + height per day
    summary_plot_height = 6 # Fixed height for the summary plot part
    height_per_day_plot = 6.5
    fig_height = summary_plot_height + (num_days * height_per_day_plot)
    # Ensure minimum height
    fig_height = max(10, fig_height)

    fig, axes = plt.subplots(num_plots_total, 1, figsize=(15, fig_height), squeeze=False)
    print(f"Generating combined report image with {num_plots_total} total subplots ({num_days} days)...")

    # --- 4. Plot the Weekly Summary (if generated) ---
    if weekly_summary_img_data:
        try:
            # Load the image data from BytesIO using matplotlib.image
            weekly_summary_img_data.seek(0) # Rewind buffer
            summary_img = mpimg.imread(weekly_summary_img_data, format='png')

            # Display the image on the first axis
            ax_summary = axes[0, 0]
            ax_summary.imshow(summary_img)
            ax_summary.axis('off') # Hide axes for the image plot
            print(" -> Weekly summary plot added to report figure.")
        except Exception as e:
            print(f"Error loading/plotting weekly summary image: {e}")
            # Turn off the axis anyway if plotting failed
            axes[0, 0].axis('off')
            axes[0, 0].set_title("Fehler beim Laden der Wochenübersicht", color='red')

    else:
        print(" -> Weekly summary plot could not be generated. Skipping in report.")
        # Optionally add a placeholder title
        axes[0, 0].axis('off')
        axes[0, 0].set_title("Wochenübersicht nicht verfügbar", color='grey')


    # --- 5. Plot the Daily Details ---
    # Daily plots start from the second axis (index 1)
    for i, day in enumerate(sorted_days):
        print(f" -> Drawing daily plot for {day} onto axis {i+1}...")
        hourly_data = days_in_week_data[day]
        # Daily plot 'i' goes onto axis 'i+1'
        create_combined_plot(day, hourly_data, ax=axes[i + 1, 0])

    # --- 6. Add Overall Title and Adjust Layout ---
    try:
        year, week = map(int, kw_str.split('-'))
        # Adjust title slightly higher if needed due to more plots
        fig.suptitle(f'Wochenbericht Energieverbrauch - KW {week}, {year}', fontsize=20, y=0.995)
    except ValueError:
         fig.suptitle(f'Wochenbericht Energieverbrauch - {kw_str}', fontsize=20, y=0.995)

    # Adjust layout AFTER plotting everything
    try:
        # Adjust top (e.g., 0.98 or 0.975) to leave space for suptitle
        # rect=[left, bottom, right, top]
        fig.tight_layout(rect=[0, 0.01, 1, 0.98]) # Fine-tune padding
    except Exception as e:
        print(f"Warnung: tight_layout fehlgeschlagen: {e}. Spacing might be suboptimal.")
        # Alternative: Try subplots_adjust
        # fig.subplots_adjust(top=0.97, bottom=0.03, hspace=0.4) # Example values


    # --- 7. Save and Send ---
    img_combined = io.BytesIO()
    fig.savefig(img_combined, format='png', bbox_inches='tight')
    img_combined.seek(0)
    plt.close(fig) # Close the combined figure
    print(f"Combined report image generated successfully for KW {kw_str}.")

    filename = f"Wochenbericht_Energie_KW_{kw_str.replace('-', '_')}.png"

    return send_file(
        img_combined,
        mimetype='image/png',
        as_attachment=True,
        download_name=filename
    )

# --- Create/Update HTML Template (Keep generation as before - HTML itself updated below) ---
index_combined_html_content = '''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>Energie Visualisierung</title> <!-- Shortened Title -->
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 25px; background-color: #f0f2f5; color: #1c1e21; line-height: 1.6; }
        h1, h2 { color: #333; text-align: center; margin-bottom: 20px; font-weight: 600; }
        h1 { font-size: 1.8em; margin-bottom: 15px;}
        h2 { font-size: 1.5em; margin-top: 40px; margin-bottom: 15px; border-bottom: 1px solid #ddd; padding-bottom: 5px;}
        .container { max-width: 1200px; margin: 0 auto; background-color: #ffffff; padding: 20px 30px 30px 30px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24); }
        .controls-container { display: flex; justify-content: center; align-items: center; flex-wrap: wrap; margin-bottom: 30px; padding: 15px; background-color: #e9ecef; border-radius: 6px; }
        .week-selector-form { display: inline-flex; align-items: center; margin: 5px 15px 5px 0; }
        .week-selector-form label { margin-right: 10px; font-weight: 500; }
        .week-selector-form select { padding: 8px 12px; border: 1px solid #ced4da; border-radius: 4px; min-width: 150px; margin-right: 10px; }
        .week-selector-form button { padding: 8px 18px; background-color: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 500; transition: background-color 0.2s; }
        .week-selector-form button:hover { background-color: #0056b3; }
        .report-button { display: inline-block; padding: 8px 18px; background-color: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 500; text-decoration: none; transition: background-color 0.2s; margin: 5px 0 5px 15px; }
        .report-button:hover { background-color: #218838; color: white; }
        .weekly-summary-plot { /* Style for the weekly plot container */
            margin-bottom: 40px;
            padding: 20px;
            background-color: #fdfdfe; /* Slightly off-white */
            border-radius: 6px;
            border: 1px solid #e1e4e8;
        }
        .weekly-summary-plot img {
             max-width: 100%;
             height: auto;
             display: block;
             margin: 10px auto 0 auto; /* Center image */
             border: 1px solid #d1d5da;
             border-radius: 4px;
             background-color: #fff;
        }
        .day-list { list-style-type: none; padding: 0; margin-top: 20px;} /* Added margin */
        .day-item { margin-bottom: 40px; padding: 25px; background-color: #f7f8fa; border-radius: 6px; border: 1px solid #e1e4e8; }
        .day-header { margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;}
        .day-link { color: #0056b3; text-decoration: none; font-weight: bold; font-size: 1.4em; margin-bottom: 8px; display: block; flex-basis: 100%; /* Take full width on small screens */ }
        @media (min-width: 600px) { .day-link { flex-basis: auto; margin-right: 20px; margin-bottom: 0;} } /* Adjust layout on larger screens */
        .day-link:hover { text-decoration: underline; color: #003d80; }
        .day-summary { font-size: 0.90em; color: #444; background-color: #e9ecef; padding: 8px 12px; border-radius: 4px; flex-grow: 1; /* Allow summary to take space */ min-width: 250px;}
        .summary-line { margin-bottom: 3px; }
        .summary-label { font-weight: 600; min-width: 45px; display: inline-block; margin-right: 5px;}
        .day-item img { /* Specific styling for daily plot images */
            max-width: 100%;
            height: auto;
            display: block;
            margin-top: 15px;
            border: 1px solid #d1d5da;
            border-radius: 4px;
            background-color: #fff;
        }
        .no-data, .no-week-selected { text-align: center; font-style: italic; color: #555; margin-top: 40px; padding: 20px; background-color: #f8d7da; border: 1px solid #f5c6cb; border-radius: 4px; color: #721c24;}
    </style>
</head>
<body>
    <div class="container">
        <h1>Energie Visualisierung</h1>

        <!-- Controls Container -->
        <div class="controls-container">
            <!-- Week Selector Form -->
            <form method="GET" action="/" class="week-selector-form">
                <label for="kw_select">Woche:</label>
                <select name="kw" id="kw_select">
                    {% if not available_kws %}
                        <option value="">Keine Daten</option>
                    {% else %}
                        {% for kw in available_kws %}
                            <option value="{{ kw }}" {% if kw == selected_kw %}selected{% endif %}>
                                KW {{ kw.split('-')[1] }}, {{ kw.split('-')[0] }}
                            </option>
                        {% endfor %}
                    {% endif %}
                </select>
                <button type="submit">Anzeigen</button>
            </form>

            <!-- Download Report Button/Link -->
            {% if selected_kw and daily_summaries %} {# Only show if week selected AND data exists #}
                <a href="/report/week/{{ selected_kw }}" download class="report-button">
                    Tagesbericht KW {{ selected_kw.split('-')[1] }} <span style="font-size:0.8em;">(Download)</span>
                </a>
            {% endif %}
        </div>

        <!-- *** NEW: Display Area for Weekly Summary Plot *** -->
        {% if weekly_plot_base64 %}
            <div class="weekly-summary-plot">
                <h2>Wochenübersicht Kosten</h2>
                <img src="data:image/png;base64,{{ weekly_plot_base64 }}" alt="Wöchentliche Kostenübersicht für KW {{ selected_kw.split('-')[1] if selected_kw else '' }}">
            </div>
        {% elif selected_kw and not daily_summaries %}
             {# Message if week selected but no data found for it - handled below too #}
        {% elif not selected_kw and available_kws %}
             {# Message if data available but no week selected yet #}
             <p class="no-week-selected">Bitte wählen Sie oben eine Kalenderwoche aus, um die Daten anzuzeigen.</p>
        {% endif %}


        <!-- Display Area for Daily Data -->
        {% if not available_kws %}
             <p class="no-data">Keine Daten gefunden. Bitte überprüfen Sie die CSV-Dateien.</p>
        {% elif not selected_kw %}
             {# Message already shown above if needed #}
        {% elif not daily_summaries %}
             <p class="no-data">Keine Daten für die ausgewählte Woche ({{ selected_kw }}) gefunden.</p>
        {% else %}
            <h2>Tägliche Kosten (Strom & Gas) - KW {{ selected_kw.split('-')[1] }}</h2>
            <ul class="day-list">
                {% for summary in daily_summaries %}
                <li class="day-item">
                    <div class="day-header">
                        {# Link to the anchor ID (created implicitly by browser or manually) #}
                        <a class="day-link" href="#{{ summary.day }}">
                            {{ summary.weekday }}, {{ summary.day }}
                        </a>
                        <div class="day-summary">
                             <div class="summary-line"><span class="summary-label">Strom:</span> {{ '%.2f'|format(summary.total_elec_kwh) }} kWh / <strong>{{ '%.2f €'|format(summary.total_elec_cost) }}</strong></div>
                             <div class="summary-line"><span class="summary-label">Gas:</span> {{ '%.2f'|format(summary.total_gas_kwh) }} kWh / <strong>{{ '%.2f €'|format(summary.total_gas_cost) }}</strong></div>
                        </div>
                    </div>
                    {# Individual daily plot image - generated by the /plot/combined/<day> route #}
                    {# Added id attribute to the image's parent or the image itself if needed for anchor link #}
                    <div id="{{ summary.day }}"> {# Anchor target ID #}
                        <img src="/plot/combined/{{ summary.day }}" alt="Energiekosten am {{ summary.day }}">
                    </div>
                </li>
                {% endfor %}
            </ul>
        {% endif %}
    </div>
</body>
</html>'''

template_path = os.path.join(TEMPLATE_DIR, 'index_combined.html')
try:
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(index_combined_html_content)
    print(f"Template '{template_path}' wurde erfolgreich aktualisiert.")
except IOError as e:
    print(f"Fehler beim Schreiben des Templates '{template_path}': {e}")


# --- Run Flask App (Keep as before) ---
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Combined Gas & Electricity Visualization")
    parser.add_argument("--port", type=int, default=PORT_NUMBER,
                        help=f"Port on which to run the server (default: {PORT_NUMBER})")
    args = parser.parse_args()

    print(f"Loading data from {ELEC_DATA_FILE} and {GAS_DATA_FILE}")
    print(f"Starting server at http://localhost:{args.port}")
    app.run(debug=bool(os.getenv("SERVER_DEBUG", "True").lower() == "true"), port=args.port, host='0.0.0.0')