import os
from image_evaluator import evaluate_image
import pandas as pd
from datetime import datetime

def batch_evaluate_images():
    """
    Wertet alle Bilder im camera_images-Ordner aus und aktualisiert die CSV-Datei.
    """
    # Pfade definieren
    base_dir = os.path.dirname(os.path.dirname(__file__))
    camera_images_dir = os.path.join(base_dir, 'camera_images')
    csv_path = os.path.join(os.path.dirname(__file__), 'gas_data.csv')
    
    # Alle Bilddateien im Ordner finden
    image_files = [f for f in os.listdir(camera_images_dir) if f.startswith('cam_') and f.endswith('.jpg')]
    image_files.sort()  # Nach Zeitstempel sortieren
    
    print(f"Gefundene Bilder: {len(image_files)}")
    
    # CSV-Datei laden oder erstellen
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print("CSV-Datei nicht gefunden. Erstelle neue Datei.")
        df = pd.DataFrame(columns=['Timestamp', 'Number', 'Verbrauch', 'Kosten_pro_Stunde'])
    
    # Jedes Bild auswerten
    for image_file in image_files:
        image_path = os.path.join(camera_images_dir, image_file)
        print(f"\nVerarbeite Bild: {image_file}")
        
        # Bild auswerten
        result = evaluate_image(image_path, csv_path)
        
        if result:
            print(f"Erkannter Wert: {result}")
        else:
            print(f"Fehler bei der Auswertung von {image_file}")
    
    print("\nBatch-Verarbeitung abgeschlossen.")

if __name__ == "__main__":
    batch_evaluate_images() 