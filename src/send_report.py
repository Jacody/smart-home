import telegram
import asyncio
import os
import logging
from dotenv import load_dotenv

# Lade Umgebungsvariablen aus .env-Datei
load_dotenv()

# --- Konfiguration ---
# Lese Konfiguration aus Umgebungsvariablen
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "DEIN_BOT_TOKEN_HIER_EINFUEGEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "DEINE_GRUPPEN_CHAT_ID_HIER_EINFUEGEN")
DATEINAME = os.getenv("TELEGRAM_DATEINAME", "Wochenbericht_Energie_KW_2025_17.png")
# --- Ende Konfiguration ---

# Logging einrichten (optional, aber hilfreich zur Fehlersuche)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- GEÄNDERTE FUNKTION ---
# Funktion umbenannt zu sende_dokument (war vorher sende_foto)
async def sende_dokument(bot_token, chat_id, dateipfad):
    """
    Sendet eine Datei als Dokument (ohne Komprimierung)
    an den angegebenen Telegram-Chat.
    """
    # Überprüfen, ob die Datei existiert
    if not os.path.exists(dateipfad):
        logger.error(f"Fehler: Datei nicht gefunden unter {dateipfad}")
        return

    # Bot-Instanz erstellen
    bot = telegram.Bot(token=bot_token)

    try:
        # Log-Nachricht angepasst
        logger.info(f"Versuche, Dokument {dateipfad} an Chat-ID {chat_id} zu senden...")
        # Datei im Binärmodus öffnen und senden
        with open(dateipfad, 'rb') as dokument_datei: # Variable umbenannt für Klarheit
            # HIER IST DIE ÄNDERUNG: send_document statt send_photo
            await bot.send_document(chat_id=chat_id, document=dokument_datei)
        # Log-Nachricht angepasst
        logger.info(f"Dokument {dateipfad} erfolgreich an Chat-ID {chat_id} gesendet.")
    except telegram.error.TelegramError as e:
        # Log-Nachricht angepasst
        logger.error(f"Telegram Fehler beim Senden des Dokuments: {e}")
        # Mögliche spezifische Fehler prüfen:
        if "chat not found" in str(e).lower():
            logger.error("-> Überprüfe, ob die CHAT_ID korrekt ist und der Bot Mitglied der Gruppe ist.")
        elif "bot was blocked by the user" in str(e).lower():
             logger.error("-> Der Bot wurde möglicherweise im Zielchat blockiert.")
        elif "wrong file identifier" in str(e).lower() or "failed to get HTTP URL content" in str(e).lower():
             logger.error("-> Problem mit der Datei oder dem Senden. Ist die Datei gültig?")
    except FileNotFoundError:
        logger.error(f"Fehler: Datei nicht gefunden unter {dateipfad}")
    except Exception as e:
        logger.error(f"Ein unerwarteter Fehler ist aufgetreten: {e}")

# Hauptteil des Skripts
if __name__ == "__main__":
    # Überprüfen, ob Platzhalter ersetzt wurden (BOT_TOKEN prüfen!)
    if BOT_TOKEN == "DEIN_BOT_TOKEN_HIER_EINFUEGEN":
        print("FEHLER: Bitte ersetze den Platzhalter für TELEGRAM_BOT_TOKEN in der .env-Datei!")
    # CHAT_ID Check
    elif CHAT_ID == "DEINE_GRUPPEN_CHAT_ID_HIER_EINFUEGEN":
         print("FEHLER: Bitte ersetze den Platzhalter für TELEGRAM_CHAT_ID in der .env-Datei!")
    else:
        # Absoluten Pfad zur Datei erstellen (angenommen, die Datei liegt im selben Ordner wie das Skript)
        script_verzeichnis = os.path.dirname(__file__)
        voller_dateipfad = os.path.join(script_verzeichnis, DATEINAME)

        # Die asynchrone Funktion ausführen
        # --- GEÄNDERTER FUNKTIONSAUFRUF ---
        asyncio.run(sende_dokument(BOT_TOKEN, CHAT_ID, voller_dateipfad)) # Ruft jetzt sende_dokument auf 