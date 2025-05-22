# gas_data_evaluator.py

import pandas as pd
import os

# --- Konfiguration ---
input_csv_file = 'data_gas.csv'
output_csv_file = 'gas_hourly.csv'
timestamp_column = 'Timestamp'
meter_reading_column = 'Number'
consumption_column = 'Verbrauch' # Original name in input CSV
image_column = 'ImageFile'
temperature_column = 'Temperature'
humidity_column = 'Humidity'

# Werte von Ihrer Gasrechnung für die kWh-Berechnung
BRENNWERT = 11.507      # kWh/m³ (von Seite 2 Ihrer Rechnung)
ZUSTANDSZAHL = 0.9663     # (von Seite 2 Ihrer Rechnung)

# Kosten pro kWh
PRICE_PER_KWH_CENT = 21.11
PRICE_PER_KWH_EURO = PRICE_PER_KWH_CENT / 100 # Umrechnung Cent in Euro

# Neue Spaltennamen
output_consumption_m3_col = 'Verbrauch (m^3)'
output_consumption_kwh_col = 'Verbrauch (kWh)'
output_cost_col = 'Kosten (€)' # Neue Spalte für Kosten
# --- Ende Konfiguration ---

def process_gas_data(input_file, output_file):
    """
    Liest die Gasverbrauchs-CSV-Datei ein, transformiert die Daten
    (Timestamp anpassen, Spalten auswählen/umbenennen, kWh und Kosten berechnen)
    und speichert das Ergebnis in einer neuen CSV-Datei.
    """
    print(f"Lese Eingabedatei: {input_file}")

    # Prüfen, ob die Eingabedatei existiert
    if not os.path.exists(input_file):
        print(f"Fehler: Eingabedatei '{input_file}' nicht gefunden.")
        return

    try:
        # Lese die CSV-Datei mit Pandas. Wichtig: parse_dates sorgt dafür,
        # dass die Timestamp-Spalte als Datum/Zeit-Objekt erkannt wird.
        df = pd.read_csv(input_file, parse_dates=[timestamp_column])

        print(f"Verarbeite {len(df)} Zeilen...")

        # 1. Timestamp anpassen: Nur Jahr-Monat-Tag Stunde:00 behalten
        df[timestamp_column] = df[timestamp_column].dt.strftime('%Y-%m-%d %H:00')

        # 2. 'Verbrauch'-Spalte umbenennen (wird für kWh-Berechnung gebraucht)
        df = df.rename(columns={consumption_column: output_consumption_m3_col})

        # 3. Verbrauch in kWh berechnen
        df[output_consumption_kwh_col] = df[output_consumption_m3_col] * ZUSTANDSZAHL * BRENNWERT

        # 4. Kosten berechnen (Verbrauch kWh * Preis pro kWh in Euro)
        df[output_cost_col] = df[output_consumption_kwh_col] * PRICE_PER_KWH_EURO

        # 5. Gewünschte Spalten für die Ausgabe auswählen und anordnen
        #    ImageFile wird hier ausgelassen.
        output_columns = [
            timestamp_column,
            temperature_column,
            humidity_column,
            meter_reading_column,
            output_consumption_m3_col,    # Die umbenannte m³-Spalte
            output_consumption_kwh_col,   # Die neu berechnete kWh-Spalte
            output_cost_col               # Die neu berechnete Kosten-Spalte
        ]
        df_output = df[output_columns]

        # Schreibe das Ergebnis in die neue CSV-Datei ohne den Pandas Index
        # mit Formatierung auf 2 Nachkommastellen für Fließkommazahlen (passt auch für Euro)
        df_output.to_csv(output_file, index=False, encoding='utf-8', float_format='%.2f')

        print(f"Ausgabedatei '{output_file}' erfolgreich erstellt.")

    except FileNotFoundError:
        print(f"Fehler: Eingabedatei '{input_file}' konnte nicht gefunden werden.")
    except KeyError as e:
        print(f"Fehler: Spalte {e} nicht in der CSV-Datei gefunden. Bitte Spaltennamen prüfen.")
        if str(e) == f"'{consumption_column}'":
             print(f"-> Überprüfen Sie, ob die Spalte '{consumption_column}' in '{input_csv_file}' existiert.")
        elif str(e) in [f"'{temperature_column}'", f"'{humidity_column}'", f"'{meter_reading_column}'", f"'{timestamp_column}'"]:
             print(f"-> Überprüfen Sie, ob die Spalte {e} in '{input_csv_file}' existiert.")
    except TypeError as e:
        print(f"Fehler bei der Berechnung (kWh oder Kosten): {e}")
        print(f"-> Stellen Sie sicher, dass die Spalte '{output_consumption_m3_col}' nur Zahlen enthält.")
    except Exception as e:
        print(f"Ein unerwarteter Fehler ist aufgetreten: {e}")

# --- Hauptteil des Skripts ---
if __name__ == "__main__":
    process_gas_data(input_csv_file, output_csv_file)