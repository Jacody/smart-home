import cv2
import pytesseract
import re
import os
import pandas as pd
import numpy as np
import easyocr
from datetime import datetime

def evaluate_image(image_path, csv_path):
    """
    Wertet ein Bild aus und aktualisiert die CSV-Datei mit dem erkannten Zahlenwert.
    
    Args:
        image_path: Pfad zum Bild
        csv_path: Pfad zur CSV-Datei mit den Sensordaten
    
    Returns:
        Erkannter Zahlenwert oder None im Fehlerfall
    """
    # Basis- und Cache-Verzeichnis bestimmen
    base_dir = os.path.dirname(os.path.dirname(__file__))
    cache_dir = os.path.join(base_dir, 'cache')
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    
    # Prüfen, ob das Bild existiert
    if not os.path.exists(image_path):
        print(f"Fehler: Bilddatei nicht gefunden unter '{image_path}'")
        return None
    
    try:
        # Bild laden
        image = cv2.imread(image_path)
        if image is None:
            print(f"Fehler: Bild konnte nicht geladen werden: '{image_path}'")
            return None
            
        # Bild um 180 Grad drehen
        image = cv2.rotate(image, cv2.ROTATE_180)
        
        # Konvertierung in Graustufen
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Definition der 6 ROIs
        rois = [
            {"name": "ROI 1", "x": 0, "y": 300, "w": 80, "h": 110, "color": (0, 255, 0)},    # ROI 1 in Grün
            {"name": "ROI 2", "x": 140, "y": 315, "w": 80, "h": 110, "color": (255, 0, 0)},   # ROI 2 in Blau
            {"name": "ROI 3", "x": 280, "y": 330, "w": 80, "h": 110, "color": (0, 0, 255)},   # ROI 3 in Rot
            {"name": "ROI 4", "x": 430, "y": 345, "w": 80, "h": 110, "color": (255, 255, 0)},# ROI 4 in Cyan
            {"name": "ROI 5", "x": 565, "y": 375, "w": 80, "h": 100, "color": (255, 0, 255)},# ROI 5 in Magenta
            {"name": "ROI 6", "x": 720, "y": 365, "w": 80, "h": 120, "color": (0, 255, 255)} # ROI 6 in Gelb
        ]
        
        # ROIs in Originalbild einzeichnen und extrahieren
        image_with_rois = image.copy()
        roi_images = []
        roi_processed_images = []
        
        for roi in rois:
            # ROI einzeichnen
            cv2.rectangle(image_with_rois, 
                         (roi["x"], roi["y"]), 
                         (roi["x"] + roi["w"], roi["y"] + roi["h"]), 
                         roi["color"], 2)
            cv2.putText(image_with_rois, roi["name"], 
                        (roi["x"], roi["y"] - 5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, roi["color"], 2)
            
            # Prüfen, ob die ROI innerhalb des Bildes liegt
            if (roi["x"] >= 0 and roi["y"] >= 0 and 
                roi["x"] + roi["w"] <= image.shape[1] and 
                roi["y"] + roi["h"] <= image.shape[0]):
                
                # ROI extrahieren
                roi_img = gray_image[roi["y"]:roi["y"]+roi["h"], roi["x"]:roi["x"]+roi["w"]]
                
                # Prüfen, ob ROI nicht leer ist
                if roi_img.size > 0:
                    roi_images.append(roi_img)
                    
                    # ROI verarbeiten
                    # 1. Adaptive Threshold
                    roi_adapt = cv2.adaptiveThreshold(roi_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                                    cv2.THRESH_BINARY_INV, 11, 2)
                    
                    # 2. Minimale Verarbeitung mit Otsu-Thresholding
                    roi_min = cv2.GaussianBlur(roi_img, (3, 3), 0)
                    _, roi_min_thresh = cv2.threshold(roi_min, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                    
                    # 3. Vergrößerte Version für bessere OCR
                    roi_resized = cv2.resize(roi_img, (roi_img.shape[1]*3, roi_img.shape[0]*3), 
                                           interpolation=cv2.INTER_CUBIC)
                    _, roi_resized_thresh = cv2.threshold(roi_resized, 0, 255, 
                                                        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                    
                    # Speichern der verarbeiteten ROIs
                    roi_processed = {
                        "original": roi_img,
                        "adaptive": roi_adapt,
                        "minimal": roi_min_thresh,
                        "resized": roi_resized_thresh
                    }
                    roi_processed_images.append(roi_processed)
                    
                    # Speichern der ROIs als separate Bilder
                    cv2.imwrite(os.path.join(cache_dir, f'{roi["name"].replace(" ", "_")}_original.png'), roi_img)
                    cv2.imwrite(os.path.join(cache_dir, f'{roi["name"].replace(" ", "_")}_adaptive.png'), roi_adapt)
                    cv2.imwrite(os.path.join(cache_dir, f'{roi["name"].replace(" ", "_")}_minimal.png'), roi_min_thresh)
                    cv2.imwrite(os.path.join(cache_dir, f'{roi["name"].replace(" ", "_")}_resized.png'), roi_resized_thresh)
                else:
                    print(f"Warnung: ROI {roi['name']} ist leer oder außerhalb des Bildes.")
            else:
                print(f"Warnung: ROI {roi['name']} liegt außerhalb des Bildes und wird übersprungen.")
        
        # Speichern des Bildes mit allen ROIs im Cache-Ordner
        cv2.imwrite(os.path.join(cache_dir, 'image_with_all_rois.png'), image_with_rois)
        
        # OCR-Konfigurationen für pytesseract
        config_single_char = r'--oem 3 --psm 10 -c tessedit_char_whitelist=0123456789'
        
        # EasyOCR Reader initialisieren
        reader = easyocr.Reader(['de'], gpu=False, model_storage_directory=cache_dir)
        
        # Sammeln aller Erkennungsergebnisse
        all_recognition_results = []
        
        # Hilfsfunktion für pytesseract Text und Konfidenz Extraktion
        def extract_pytess_text_and_confidence(data):
            texts = []
            confs = []
            
            for i in range(len(data['text'])):
                if data['text'][i].strip() and int(data['conf'][i]) > 0:  # Nur gültige Konfidenzwerte (> 0)
                    texts.append(data['text'][i])
                    confs.append(float(data['conf'][i]))
            
            if texts:
                text = ' '.join(texts).strip()
                avg_conf = sum(confs) / len(confs) if confs else 0
                return text, avg_conf
            else:
                return "", 0.0
        
        # Hilfsfunktion für EasyOCR Text und Konfidenz Extraktion
        def extract_easyocr_text_and_confidence(result):
            if not result:
                return "", 0.0
                
            texts = []
            confs = []
            
            for box in result:
                texts.append(box[1])  # Text ist an zweiter Stelle
                confs.append(box[2])  # Konfidenz ist an dritter Stelle
            
            text = ' '.join(texts).strip()
            avg_conf = sum(confs) / len(confs) if confs else 0
            return text, avg_conf * 100  # EasyOCR gibt Konfidenz zwischen 0-1, multiplizieren mit 100
        
        # OCR für jede ROI durchführen
        for i, roi in enumerate(rois):
            if i >= len(roi_processed_images):
                print(f"Überspringe ROI {roi['name']}, da sie nicht erfolgreich verarbeitet wurde.")
                continue
                
            roi_processed = roi_processed_images[i]
            
            try:
                # --- pytesseract OCR ---
                # 1. Original mit pytesseract
                try:
                    data_original = pytesseract.image_to_data(roi_processed["original"], config=config_single_char, 
                                                            output_type=pytesseract.Output.DICT)
                    text_pytess_orig, conf_pytess_orig = extract_pytess_text_and_confidence(data_original)
                except:
                    text_pytess_orig, conf_pytess_orig = "", 0.0
                
                # 2. Adaptive mit pytesseract
                try:
                    data_adapt = pytesseract.image_to_data(roi_processed["adaptive"], config=config_single_char, 
                                                        output_type=pytesseract.Output.DICT)
                    text_pytess_adapt, conf_pytess_adapt = extract_pytess_text_and_confidence(data_adapt)
                except:
                    text_pytess_adapt, conf_pytess_adapt = "", 0.0
                
                # 3. Minimal mit pytesseract
                try:
                    data_min = pytesseract.image_to_data(roi_processed["minimal"], config=config_single_char, 
                                                      output_type=pytesseract.Output.DICT)
                    text_pytess_min, conf_pytess_min = extract_pytess_text_and_confidence(data_min)
                except:
                    text_pytess_min, conf_pytess_min = "", 0.0
                
                # 4. Vergrößert mit pytesseract
                try:
                    data_resized = pytesseract.image_to_data(roi_processed["resized"], config=config_single_char, 
                                                          output_type=pytesseract.Output.DICT)
                    text_pytess_resized, conf_pytess_resized = extract_pytess_text_and_confidence(data_resized)
                except:
                    text_pytess_resized, conf_pytess_resized = "", 0.0
                
                # --- EasyOCR ---
                # 1. Original mit EasyOCR
                try:
                    result_original = reader.readtext(roi_processed["original"], 
                                                    allowlist='0123456789', 
                                                    detail=1)
                    text_easyocr_orig, conf_easyocr_orig = extract_easyocr_text_and_confidence(result_original)
                except:
                    text_easyocr_orig, conf_easyocr_orig = "", 0.0
                
                # 2. Adaptive mit EasyOCR
                try:
                    result_adapt = reader.readtext(roi_processed["adaptive"], 
                                               allowlist='0123456789', 
                                               detail=1)
                    text_easyocr_adapt, conf_easyocr_adapt = extract_easyocr_text_and_confidence(result_adapt)
                except:
                    text_easyocr_adapt, conf_easyocr_adapt = "", 0.0
                
                # 3. Minimal mit EasyOCR
                try:
                    result_min = reader.readtext(roi_processed["minimal"], 
                                             allowlist='0123456789', 
                                             detail=1)
                    text_easyocr_min, conf_easyocr_min = extract_easyocr_text_and_confidence(result_min)
                except:
                    text_easyocr_min, conf_easyocr_min = "", 0.0
                
                # 4. Vergrößert mit EasyOCR
                try:
                    result_resized = reader.readtext(roi_processed["resized"], 
                                                 allowlist='0123456789', 
                                                 detail=1)
                    text_easyocr_resized, conf_easyocr_resized = extract_easyocr_text_and_confidence(result_resized)
                except:
                    text_easyocr_resized, conf_easyocr_resized = "", 0.0
                
                # Ergebnis mit der besten Erkennung verwenden
                results = {
                    # pytesseract Ergebnisse
                    "Pytesseract Original": {"text": text_pytess_orig, "conf": conf_pytess_orig},
                    "Pytesseract Adaptive": {"text": text_pytess_adapt, "conf": conf_pytess_adapt},
                    "Pytesseract Minimal": {"text": text_pytess_min, "conf": conf_pytess_min},
                    "Pytesseract Vergrößert": {"text": text_pytess_resized, "conf": conf_pytess_resized},
                    # EasyOCR Ergebnisse
                    "EasyOCR Original": {"text": text_easyocr_orig, "conf": conf_easyocr_orig},
                    "EasyOCR Adaptive": {"text": text_easyocr_adapt, "conf": conf_easyocr_adapt},
                    "EasyOCR Minimal": {"text": text_easyocr_min, "conf": conf_easyocr_min},
                    "EasyOCR Vergrößert": {"text": text_easyocr_resized, "conf": conf_easyocr_resized}
                }
                
                # Beste Methode auswählen
                best_method = None
                best_conf = -1
                best_text = ""
                
                for method, result in results.items():
                    if result["text"] and result["conf"] > best_conf:
                        best_conf = result["conf"]
                        best_text = result["text"]
                        best_method = method
                
                # Wenn keine Methode erfolgreich war, Standard-Fallback
                if not best_text:
                    best_text = text_easyocr_orig if text_easyocr_orig else ""
                    best_method = "EasyOCR Original"
                    best_conf = conf_easyocr_orig
                    
                # Bereinigen - nur Ziffern behalten
                extracted_digits = re.sub(r'\D', '', best_text)
                
                # Wenn keine Ziffer erkannt wurde, verwende 9 als Fallback
                if not extracted_digits:
                    extracted_digits = "9"
                # Beschränke auf eine einzelne Ziffer (0-9)
                elif len(extracted_digits) > 1:
                    # Wenn mehrere Ziffern erkannt wurden, nimm nur die erste und begrenze auf 0-9
                    extracted_digits = extracted_digits[0]
                
                # Stelle sicher, dass nur Werte von 0-9 verwendet werden
                if extracted_digits and (not extracted_digits.isdigit() or int(extracted_digits) > 9):
                    extracted_digits = "9"  # Fallback, wenn ungültige Ziffer
                
                # Ergebnisse speichern
                all_recognition_results.append({
                    "roi_name": roi["name"],
                    "results": results,
                    "best_method": best_method,
                    "best_confidence": best_conf,
                    "detected_text": best_text,
                    "extracted_digits": extracted_digits
                })
                
            except Exception as e:
                print(f"Fehler bei OCR für ROI {roi['name']}: {e}")
                all_recognition_results.append({
                    "roi_name": roi["name"],
                    "best_method": "Error",
                    "best_confidence": 0,
                    "detected_text": "",
                    "extracted_digits": "9"  # Fallback-Wert
                })
        
        # --- Zusammenfassung aller erkannten Zahlen ---
        all_digits = [(result["extracted_digits"], result["best_confidence"]) for result in all_recognition_results]
        
        # Zusammenfügen aller erkannten Ziffern zu einer Zahl
        combined_digits = ""
        for i, (digits, conf) in enumerate(all_digits):
            if i < len(all_recognition_results):
                combined_digits += digits
        
        # Komma an vorvorletzter Stelle einfügen, wenn die Zahl lang genug ist
        if len(combined_digits) >= 3:
            combined_digits_with_comma = combined_digits[:-2] + ',' + combined_digits[-2:]
            csv_value = combined_digits_with_comma
        else:
            csv_value = combined_digits
        
        # Extrahieren des Zeitstempels aus dem Bildnamen
        image_filename = os.path.basename(image_path)
        timestamp_match = re.search(r'cam_(\d{8})_(\d{6})\.jpg', image_filename)
        
        if timestamp_match:
            date_part = timestamp_match.group(1)
            time_part = timestamp_match.group(2)
            
            # Formatieren als YYYY-MM-DD HH:MM:SS
            formatted_timestamp = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:]} {time_part[:2]}:{time_part[2:4]}:{time_part[4:]}"
            
            # CSV-Datei aktualisieren
            try:
                # CSV-Datei mit pandas lesen
                df = pd.read_csv(csv_path)
                
                # Prüfen, ob die nötigen Spalten existieren, falls nicht, hinzufügen
                if 'Number' not in df.columns:
                    df['Number'] = ""
                
                if 'Verbrauch' not in df.columns:
                    df['Verbrauch'] = np.nan
                
                # Zeile mit dem Zeitstempel finden
                matching_rows = df[df['Timestamp'] == formatted_timestamp]
                
                if len(matching_rows) > 0:
                    # Zeitstempel gefunden, 'Number' mit erkannter Zahl aktualisieren
                    row_index = matching_rows.index[0]
                    
                    # Anführungszeichen entfernen und Komma durch Punkt ersetzen
                    clean_value = str(csv_value).strip('"').replace(',', '.')
                    df.at[row_index, 'Number'] = clean_value
                    
                    # Verbrauch berechnen
                    # Aktuellen Zählerstand in eine Fließkommazahl umwandeln
                    current_value = float(clean_value)
                    
                    # Den Index der aktuellen Zeile in der sortierten DataFrame ermitteln
                    df_sorted = df.sort_values(by='Timestamp')
                    current_idx = df_sorted.index.get_loc(row_index)
                    
                    # Wenn es einen vorherigen Eintrag gibt, berechne Verbrauch
                    if current_idx > 0 and current_idx < len(df_sorted):
                        # Vorherigen Zählerstand holen
                        prev_idx = df_sorted.index[current_idx - 1]
                        prev_value_str = str(df_sorted.at[prev_idx, 'Number']).strip('"').replace(',', '.')
                        prev_timestamp_str = df_sorted.at[prev_idx, 'Timestamp']
                        
                        # Prüfen, ob der vorherige Wert vorhanden ist
                        if prev_value_str and prev_value_str != 'nan':
                            prev_value = float(prev_value_str)
                            
                            # Zeitdifferenz berechnen
                            current_timestamp = datetime.strptime(formatted_timestamp, '%Y-%m-%d %H:%M:%S')
                            prev_timestamp = datetime.strptime(prev_timestamp_str, '%Y-%m-%d %H:%M:%S')
                            time_diff_seconds = (current_timestamp - prev_timestamp).total_seconds()
                            
                            if time_diff_seconds > 0:
                                # Differenz im Zählerstand (kWh)
                                consumption_diff_kwh = current_value - prev_value
                                
                                # Verbrauch in Watt = (Differenz in kWh) * 1000 / (Zeit in Stunden)
                                consumption_watts = (consumption_diff_kwh * 1000) / (time_diff_seconds / 3600)
                                
                                # In DataFrame eintragen
                                df.at[row_index, 'Verbrauch'] = round(consumption_watts, 2)
                    
                    # Aktualisierte Daten zurückschreiben
                    df.to_csv(csv_path, index=False)
                    print(f"CSV-Datei erfolgreich aktualisiert. Nummer {clean_value} für Zeitstempel {formatted_timestamp} eingetragen.")
                    
                    # Ausgabe des berechneten Verbrauchs, wenn vorhanden
                    if not pd.isna(df.at[row_index, 'Verbrauch']):
                        print(f"Verbrauch: {df.at[row_index, 'Verbrauch']} Watt")
                else:
                    print(f"Warnung: Kein Eintrag mit Zeitstempel {formatted_timestamp} in der CSV-Datei gefunden.")
                    
            except Exception as e:
                print(f"Fehler beim Aktualisieren der CSV-Datei: {e}")
                return None
        else:
            print(f"Warnung: Konnte keinen Zeitstempel aus dem Bildnamen '{image_filename}' extrahieren.")
            return None
            
        return csv_value
        
    except pytesseract.TesseractNotFoundError:
        print("Fehler: Tesseract wurde nicht gefunden.")
        print("Stellen Sie sicher, dass Tesseract OCR installiert ist und der Pfad ggf.")
        print("in der Variable 'pytesseract.pytesseract.tesseract_cmd' oben im Skript korrekt gesetzt ist.")
        return None
    except Exception as e:
        print(f"Ein Fehler ist während der Bildauswertung aufgetreten: {e}")
        return None

if __name__ == "__main__":
    # Beim direkten Ausführen des Skripts können Bild und CSV-Pfad als Argumente übergeben werden
    import argparse
    
    parser = argparse.ArgumentParser(description='Bild auswerten und CSV aktualisieren')
    parser.add_argument('--image', type=str, help='Pfad zum Bild')
    parser.add_argument('--csv', type=str, help='Pfad zur CSV-Datei')
    
    args = parser.parse_args()
    
    image_path = args.image or os.path.join(os.path.dirname(__file__), 'camera_images/cam_20250414_124517.jpg')
    csv_path = args.csv or os.path.join(os.path.dirname(__file__), 'data_gas.csv')
    
    result = evaluate_image(image_path, csv_path)
    if result:
        print(f"Erkannter Wert: {result}") 