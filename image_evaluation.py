import cv2
import re
import os
import numpy as np
import csv
import pandas as pd
import easyocr  # easyocr statt pytesseract importieren
import pytesseract  # pytesseract zusätzlich importieren

def berechne_verbrauch(df):
    """
    Berechnet den Verbrauch für alle Einträge im DataFrame.
    """
    # Sortiere nach Zeitstempel
    df = df.sort_values('Timestamp')
    
    # Konvertiere Number-Spalte zu Float (ersetze Komma durch Punkt)
    df['Number'] = pd.to_numeric(df['Number'].str.replace(',', '.'), errors='coerce')
    
    # Initialisiere Verbrauch mit 0
    df['Verbrauch'] = 0.0
    
    # Berechne Verbrauch für jeden Eintrag
    for i in range(1, len(df)):
        # Nur berechnen, wenn beide Werte vorhanden sind
        if not pd.isna(df.iloc[i]['Number']) and not pd.isna(df.iloc[i-1]['Number']):
            # Differenz im Zählerstand
            consumption_diff = df.iloc[i]['Number'] - df.iloc[i-1]['Number']
            
            # Verbrauch ist einfach die Differenz
            consumption = consumption_diff
            
            # Werte in DataFrame eintragen
            df.at[df.index[i], 'Verbrauch'] = round(consumption, 2)
    
    return df

# --- Konfiguration ---

# !!! WICHTIG: Passen Sie diesen Pfad ggf. an Ihren Tesseract-Installationsort an !!!
# Nur notwendig, wenn Tesseract nicht im System-PATH ist (häufig unter Windows)
# Beispiel für Windows:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# Beispiel für Linux/macOS (oft nicht nötig, wenn korrekt installiert):
# pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract' # Pfad ggf. anpassen

# Pfad zu Ihrem Bild
# !!! ÄNDERN SIE DIES ZU IHREM BILDNAMEN/PFAD !!!
image_path = os.path.join(os.path.dirname(__file__), 'camera_images/cam_20250430_083816.jpg') # Ersetzen Sie dies mit dem Pfad zu Ihrem Bild
csv_path = os.path.join(os.path.dirname(__file__), 'data_gas.csv')  # Pfad zur CSV-Datei
cache_dir = 'cache'  # Ordner für Zwischendateien

# Cache-Verzeichnis erstellen, falls es nicht existiert
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

# --- Vorbereitung ---
# Prüfen, ob das Bild existiert
if not os.path.exists(image_path):
    print(f"Fehler: Bilddatei nicht gefunden unter '{image_path}'")
    exit() # Beendet das Skript, wenn die Datei nicht existiert

# --- Bild laden ---
try:
    image = cv2.imread(image_path)
    if image is None:
        print(f"Fehler: Bild konnte nicht geladen werden. Prüfen Sie den Pfad und das Dateiformat: '{image_path}'")
        exit()
except Exception as e:
    print(f"Ein Fehler ist beim Laden des Bildes aufgetreten: {e}")
    exit()

# Bild um 180 Grad drehen
image = cv2.rotate(image, cv2.ROTATE_180)

# --- Bildvorverarbeitung ---
# 1. Konvertierung in Graustufen (OCR arbeitet oft besser mit Graustufen)
gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

# --- Definition der 6 ROIs ---
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

# --- OCR mit EasyOCR und pytesseract ---
try:
    # EasyOCR Reader initialisieren (nur einmal, für bessere Performance)
    # Wir verwenden nur deutsche Sprache und schränken auf Zahlen ein
    reader = easyocr.Reader(['de'], gpu=False, model_storage_directory=cache_dir)
    
    # Konfiguration für pytesseract
    pytesseract_config = '--psm 10 -c tessedit_char_whitelist=0123456789'  # PSM 10 für einzelne Zeichen
    
    # Sammeln aller Erkennungsergebnisse
    all_recognition_results = []

    for i, roi in enumerate(rois):
        if i >= len(roi_processed_images):
            print(f"Überspringe ROI {roi['name']}, da sie nicht erfolgreich verarbeitet wurde.")
            continue
            
        roi_processed = roi_processed_images[i]
        
        # Erkennung mit verschiedenen Bildvorverarbeitungen durchführen
        results = {}
        
        # 1. Original-ROI OCR mit EasyOCR
        result_original = reader.readtext(roi_processed["original"], 
                                          allowlist='0123456789', 
                                          detail=1)
        
        # 2. Adaptive Threshold mit EasyOCR
        result_adapt = reader.readtext(roi_processed["adaptive"], 
                                       allowlist='0123456789', 
                                       detail=1)
        
        # 3. Minimal verarbeitet mit EasyOCR
        result_min = reader.readtext(roi_processed["minimal"], 
                                     allowlist='0123456789', 
                                     detail=1)
        
        # 4. Vergrößerte Version mit EasyOCR
        result_resized = reader.readtext(roi_processed["resized"], 
                                         allowlist='0123456789', 
                                         detail=1)
        
        # --- pytesseract OCR für die gleichen Bilder ---
        # Hilfsfunktion für pytesseract Konfidenzberechnung
        def extract_pytesseract_text_and_confidence(data):
            texts = []
            confs = []
            
            for i in range(len(data['text'])):
                if data['text'][i].strip() and int(data['conf'][i]) > 0:  # Nur gültige Konfidenzwerte (> 0) und nicht-leere Texte
                    texts.append(data['text'][i])
                    confs.append(float(data['conf'][i]))
            
            if texts:
                text = ' '.join(texts).strip()
                avg_conf = sum(confs) / len(confs) if confs else 0
                return text, avg_conf
            else:
                return "", 0.0
                
        # 1. Original mit pytesseract
        try:
            text_pytess_orig = pytesseract.image_to_string(roi_processed["original"], 
                                                       config=pytesseract_config).strip()
            # Berechnung der Konfidenz für pytesseract
            pytess_orig_data = pytesseract.image_to_data(roi_processed["original"], 
                                                     config=pytesseract_config, 
                                                     output_type=pytesseract.Output.DICT)
            text_pytess_orig, conf_pytess_orig = extract_pytesseract_text_and_confidence(pytess_orig_data)
        except:
            text_pytess_orig = ""
            conf_pytess_orig = 0.0
            
        # 2. Adaptive mit pytesseract
        try:
            text_pytess_adapt = pytesseract.image_to_string(roi_processed["adaptive"], 
                                                        config=pytesseract_config).strip()
            pytess_adapt_data = pytesseract.image_to_data(roi_processed["adaptive"], 
                                                      config=pytesseract_config, 
                                                      output_type=pytesseract.Output.DICT)
            text_pytess_adapt, conf_pytess_adapt = extract_pytesseract_text_and_confidence(pytess_adapt_data)
        except:
            text_pytess_adapt = ""
            conf_pytess_adapt = 0.0
            
        # 3. Minimal mit pytesseract
        try:
            text_pytess_min = pytesseract.image_to_string(roi_processed["minimal"], 
                                                      config=pytesseract_config).strip()
            pytess_min_data = pytesseract.image_to_data(roi_processed["minimal"], 
                                                    config=pytesseract_config, 
                                                    output_type=pytesseract.Output.DICT)
            text_pytess_min, conf_pytess_min = extract_pytesseract_text_and_confidence(pytess_min_data)
        except:
            text_pytess_min = ""
            conf_pytess_min = 0.0
            
        # 4. Resized mit pytesseract
        try:
            text_pytess_resized = pytesseract.image_to_string(roi_processed["resized"], 
                                                          config=pytesseract_config).strip()
            pytess_resized_data = pytesseract.image_to_data(roi_processed["resized"], 
                                                        config=pytesseract_config, 
                                                        output_type=pytesseract.Output.DICT)
            text_pytess_resized, conf_pytess_resized = extract_pytesseract_text_and_confidence(pytess_resized_data)
        except:
            text_pytess_resized = ""
            conf_pytess_resized = 0.0
        
        # Hilfsfunktion, um Text und Konfidenz aus den OCR-Daten zu extrahieren
        def extract_text_and_confidence(result):
            if not result:
                return "", 0.0
                
            texts = []
            confs = []
            
            for box in result:
                texts.append(box[1])  # Text ist an zweiter Stelle
                confs.append(box[2])  # Konfidenz ist an dritter Stelle
            
            text = ' '.join(texts).strip()
            avg_conf = sum(confs) / len(confs) if confs else 0
            return text, avg_conf * 100  # EasyOCR gibt Konfidenz zwischen 0-1, wir multiplizieren mit 100
        
        # Ergebnisse mit Konfidenzwerten extrahieren für EasyOCR
        text_original, conf_original = extract_text_and_confidence(result_original)
        text_adapt, conf_adapt = extract_text_and_confidence(result_adapt)
        text_min, conf_min = extract_text_and_confidence(result_min)
        text_resized, conf_resized = extract_text_and_confidence(result_resized)
        
        # Ergebnisse sammeln für beide OCR-Engines
        results = {
            # EasyOCR Ergebnisse
            "EasyOCR Original": {"text": text_original, "conf": conf_original},
            "EasyOCR Adaptive": {"text": text_adapt, "conf": conf_adapt},
            "EasyOCR Minimal": {"text": text_min, "conf": conf_min},
            "EasyOCR Resized": {"text": text_resized, "conf": conf_resized},
            # pytesseract Ergebnisse
            "Pytesseract Original": {"text": text_pytess_orig, "conf": conf_pytess_orig},
            "Pytesseract Adaptive": {"text": text_pytess_adapt, "conf": conf_pytess_adapt},
            "Pytesseract Minimal": {"text": text_pytess_min, "conf": conf_pytess_min},
            "Pytesseract Resized": {"text": text_pytess_resized, "conf": conf_pytess_resized}
        }
        
        # Beste Methode auswählen - bevorzuge Methoden mit höherer Konfidenz
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
            best_text = text_original if text_original else ""
            best_method = "EasyOCR Original"
            best_conf = conf_original
            
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
    print(f"Ein Fehler ist während der OCR-Verarbeitung aufgetreten: {e}")
    print("Stellen Sie sicher, dass EasyOCR und Tesseract korrekt installiert sind.")
    print("Installation mit: pip install easyocr pytesseract")
    print("Tesseract muss separat installiert werden: https://github.com/tesseract-ocr/tesseract")
    exit()

# --- Ergebnisse ausgeben ---
print("\n--- OCR-Erkennungsergebnisse für alle ROIs ---")
for result in all_recognition_results:
    print(f"\n{result['roi_name']}:")
    print(f"  Erkannter Text: '{result['detected_text']}'")
    print(f"  Extrahierte Ziffern: '{result['extracted_digits']}'")
    print(f"  Beste Methode: {result['best_method']}")
    print(f"  Konfidenz: {result['best_confidence']:.2f}%")
    
    print("  Detaillierte Ergebnisse je Methode:")
    for method, res in result["results"].items():
        print(f"    - {method}: '{res['text']}' (Konfidenz: {res['conf']:.2f}%)")

# --- Optional: Zusammenfassung aller erkannten Zahlen mit Konfidenz ---
all_digits = [(result["extracted_digits"], result["best_confidence"]) for result in all_recognition_results]
print("\n--- Zusammenfassung aller erkannten Ziffern mit Konfidenz ---")

# Zusammenfügen aller erkannten Ziffern zu einer Zahl
combined_digits = ""
for i, (digits, conf) in enumerate(all_digits):
    if i < len(all_recognition_results):
        print(f"{all_recognition_results[i]['roi_name']}: {digits} (Konfidenz: {conf:.2f}%)")
        combined_digits += digits

# Komma an vorvorletzter Stelle einfügen, wenn die Zahl lang genug ist
if len(combined_digits) >= 3:
    combined_digits_with_comma = combined_digits[:-2] + ',' + combined_digits[-2:]
    print(f"\nKombinierte Zahl aus allen ROIs: {combined_digits}")
    print(f"Mit Komma an vorvorletzter Stelle: {combined_digits_with_comma}")
else:
    print(f"\nKombinierte Zahl aus allen ROIs: {combined_digits}")
    print("Zahl ist zu kurz für Komma-Einfügung")

# Variable für CSV-Update verwenden
csv_value = combined_digits
if len(combined_digits) >= 3:
    csv_value = combined_digits_with_comma

# Extrahieren des Zeitstempels aus dem Bildnamen
# Format: cam_YYYYMMDD_HHMMSS.jpg
image_filename = os.path.basename(image_path)
timestamp_match = re.search(r'cam_(\d{8})_(\d{6})\.jpg', image_filename)

if timestamp_match:
    date_part = timestamp_match.group(1)
    time_part = timestamp_match.group(2)
    
    # Formatieren als YYYY-MM-DD HH:MM:SS
    formatted_timestamp = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:]} {time_part[:2]}:{time_part[2:4]}:{time_part[4:]}"
    print(f"Extrahierter Zeitstempel aus Bildname: {formatted_timestamp}")
    
    # CSV-Datei aktualisieren
    try:
        # CSV-Datei mit pandas lesen
        print(f"Lese CSV-Datei von {csv_path}")
        df = pd.read_csv(csv_path)
        
        # Finde die Zeile mit dem entsprechenden Zeitstempel
        mask = df['Timestamp'] == formatted_timestamp
        if mask.any():
            # Aktualisiere nur den Number-Wert in der gefundenen Zeile
            # Entferne Anführungszeichen und ersetze Komma durch Punkt
            clean_value = str(csv_value).strip('"').replace(',', '.')
            df.loc[mask, 'Number'] = clean_value
            print(f"Aktualisiere Number auf {clean_value} für Zeitstempel {formatted_timestamp}")
            
            # Berechne Verbrauch und Kosten nur für die aktualisierte Zeile
            row_idx = df[mask].index[0]
            if row_idx > 0:  # Nur berechnen, wenn es einen vorherigen Eintrag gibt
                prev_value = df.iloc[row_idx-1]['Number']
                if not pd.isna(prev_value) and not pd.isna(clean_value):
                    # Konvertiere die Werte in Float (ersetze Komma durch Punkt)
                    current_value = float(str(clean_value).replace(',', '.'))
                    prev_value = float(str(prev_value).replace(',', '.'))
                    
                    # Differenz im Zählerstand
                    consumption_diff = current_value - prev_value
                    
                    # Verbrauch ist einfach die Differenz
                    consumption = consumption_diff
                    
                    # Werte in DataFrame eintragen
                    df.at[row_idx, 'Verbrauch'] = round(consumption, 2)
        
        # Aktualisierte Daten zurückschreiben
        print(f"\nSchreibe aktualisierte Daten in {csv_path}")
        df.to_csv(csv_path, index=False)
        print("CSV-Datei erfolgreich aktualisiert.")
        
    except Exception as e:
        print(f"Fehler beim Aktualisieren der CSV-Datei: {e}")
        print(f"Fehlerdetails: {str(e)}")
else:
    print(f"Warnung: Konnte keinen Zeitstempel aus dem Bildnamen '{image_filename}' extrahieren.")

# --- Bilder anzeigen ---
# Zeige das Originalbild mit allen ROIs
cv2.imshow("Originalbild mit allen ROIs", image_with_rois)

# Erstelle ein Gitter zum Anzeigen aller ROI-Bilder
if roi_images:  # Nur fortfahren, wenn wir ROIs haben
    # ROIs in einer Reihe anzeigen
    roi_display_images = []
    for i, roi_processed in enumerate(roi_processed_images):
        # Originales ROI anzeigen
        img = roi_processed["original"]
        h, w = img.shape
        # Text hinzufügen mit erkannten Ziffern und Konfidenz
        img_color = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        text = f"{all_recognition_results[i]['extracted_digits']} ({all_recognition_results[i]['best_confidence']:.1f}%)"
        cv2.putText(img_color, text, (5, h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        roi_display_images.append(img_color)
        
        # Adaptive Threshold anzeigen 
        img_adapt_color = cv2.cvtColor(roi_processed["adaptive"], cv2.COLOR_GRAY2BGR)
        cv2.putText(img_adapt_color, text, (5, h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        roi_display_images.append(img_adapt_color)

    # Erstelle ein Gitter zum Anzeigen aller ROI-Bilder
    rows = 2
    cols = 6
    grid_h = rows * roi_images[0].shape[0]
    grid_w = cols * roi_images[0].shape[1]
    grid_image = np.zeros((grid_h, grid_w, 3), dtype=np.uint8)

    # Platziere die Bilder im Gitter
    for i, img in enumerate(roi_display_images):
        if i >= rows * cols:
            break
        r, c = divmod(i, cols)
        h, w = roi_images[0].shape[:2]
        y, x = r * h, c * w
        
        # Resize falls nötig
        if img.shape[:2] != (h, w):
            img = cv2.resize(img, (w, h))
        
        # BGR konvertieren falls Grayscale
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        
        grid_image[y:y+h, x:x+w] = img

    cv2.imshow("Alle ROIs mit Erkennungen und Konfidenz", grid_image)
    # Im Cache-Ordner speichern
    cv2.imwrite(os.path.join(cache_dir, "all_rois_grid_with_confidence.png"), grid_image)

cv2.waitKey(0)  # Warte auf eine Taste
cv2.destroyAllWindows()  # Schließe alle Fenster 