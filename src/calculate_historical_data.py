import pandas as pd
import numpy as np
from datetime import datetime
import os

def calculate_consumption_and_costs(csv_path):
    """
    Berechnet den Verbrauch in Watt und die Kosten pro Stunde für alle vorhandenen Datenpunkte
    in der CSV-Datei und aktualisiert die Werte in der Datei.
    
    Args:
        csv_path: Pfad zur CSV-Datei mit den Sensordaten
    """
    try:
        # CSV-Datei mit pandas lesen
        df = pd.read_csv(csv_path)
        
        # Prüfen, ob die nötigen Spalten existieren, falls nicht, hinzufügen
        if 'Verbrauch' not in df.columns:
            df['Verbrauch'] = np.nan
            
        if 'Kosten_pro_Stunde' not in df.columns:
            df['Kosten_pro_Stunde'] = np.nan
        
        # DataFrame nach Zeitstempel sortieren
        df_sorted = df.sort_values(by='Timestamp')
        
        # Anzahl der erfolgreichen Berechnungen
        successful_calculations = 0
        
        # Über alle Zeilen iterieren (außer der ersten, da wir einen vorherigen Datenpunkt benötigen)
        for i in range(1, len(df_sorted)):
            current_row = df_sorted.iloc[i]
            prev_row = df_sorted.iloc[i-1]
            
            # Zählerstände extrahieren
            current_value_str = current_row['Number']
            prev_value_str = prev_row['Number']
            
            # Prüfen, ob beide Werte vorhanden sind und das richtige Format haben
            if (isinstance(current_value_str, str) and ',' in current_value_str and 
                isinstance(prev_value_str, str) and ',' in prev_value_str):
                
                # Werte in Float umwandeln
                current_value = float(current_value_str.replace(',', '.'))
                prev_value = float(prev_value_str.replace(',', '.'))
                
                # Zeitstempel in Datetime-Objekte umwandeln
                current_timestamp = datetime.strptime(current_row['Timestamp'], '%Y-%m-%d %H:%M:%S')
                prev_timestamp = datetime.strptime(prev_row['Timestamp'], '%Y-%m-%d %H:%M:%S')
                
                # Zeitdifferenz berechnen
                time_diff_seconds = (current_timestamp - prev_timestamp).total_seconds()
                
                if time_diff_seconds > 0:
                    # Differenz im Zählerstand (kWh)
                    consumption_diff_kwh = current_value - prev_value
                    
                    # Verbrauch in Watt = (Differenz in kWh) * 1000 / (Zeit in Stunden)
                    consumption_watts = (consumption_diff_kwh * 1000) / (time_diff_seconds / 3600)
                    
                    # Kosten pro Stunde (in Cent) = Verbrauch in kW * Preis pro kWh
                    cost_per_hour = (consumption_watts / 1000) * 21.11
                    
                    # Negative Werte ignorieren (falls der Zählerstand zurückgesetzt wurde)
                    if consumption_watts >= 0:
                        # Begrenzung auf sinnvolle Werte (um Ausreißer zu vermeiden)
                        if consumption_watts < 10000:  # Max. 10 kW ist für einen Haushalt plausibel
                            # In DataFrame eintragen (mit dem original Index)
                            original_idx = df_sorted.index[i]
                            df.at[original_idx, 'Verbrauch'] = round(consumption_watts, 2)
                            df.at[original_idx, 'Kosten_pro_Stunde'] = round(cost_per_hour, 2)
                            successful_calculations += 1
        
        # Aktualisierte Daten zurückschreiben
        df.to_csv(csv_path, index=False)
        
        print(f"Berechnungen abgeschlossen. {successful_calculations} von {len(df_sorted)-1} möglichen Datenpunkten wurden aktualisiert.")
        
    except Exception as e:
        print(f"Fehler bei der Berechnung: {e}")

if __name__ == "__main__":
    # Standardpfad zur CSV-Datei oder aus Kommandozeilenargumenten
    import argparse
    
    parser = argparse.ArgumentParser(description='Verbrauch und Kosten für historische Daten berechnen')
    parser.add_argument('--csv', type=str, help='Pfad zur CSV-Datei')
    
    args = parser.parse_args()
    
    csv_path = args.csv or os.path.join(os.path.dirname(__file__), 'gas_data.csv')
    
    if os.path.exists(csv_path):
        print(f"Verarbeite CSV-Datei: {csv_path}")
        calculate_consumption_and_costs(csv_path)
    else:
        print(f"Fehler: CSV-Datei {csv_path} nicht gefunden!") 