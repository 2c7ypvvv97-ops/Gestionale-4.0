import os
import shutil
from datetime import datetime
from cryptography.fernet import Fernet

DB_PATH = "fabbrica_locale.db"
KEY_FILE = "secret.key"

def genera_o_carica_chiave(key_path: str = KEY_FILE) -> bytes:
    """Genera una nuova chiave Fernet se non esiste, altrimenti la carica."""
    if not os.path.exists(key_path):
        key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key)
        return key
    else:
        with open(key_path, "rb") as f:
            return f.read()

def esegui_backup_cifrato(cartella_destinazione: str, cifrato: bool = True) -> tuple[bool, str]:
    """
    Esegue una copia del database SQLite.
    Se cifrato=True, la copia viene cifrata tramite AES (Fernet) prima del salvataggio.
    """
    if not os.path.exists(DB_PATH):
        return False, f"File database '{DB_PATH}' non trovato."

    if not os.path.exists(cartella_destinazione):
        try:
            os.makedirs(cartella_destinazione, exist_ok=True)
        except Exception as e:
            return False, f"Impossibile creare la cartella di destinazione: {e}"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    try:
        if cifrato:
            key = genera_o_carica_chiave()
            fernet = Fernet(key)
            
            nome_backup = f"backup_fabbrica_{timestamp}.db.enc"
            percorso_finale = os.path.join(cartella_destinazione, nome_backup)

            with open(DB_PATH, "rb") as f_in:
                dati_db = f_in.read()

            dati_cifrati = fernet.encrypt(dati_db)

            with open(percorso_finale, "wb") as f_out:
                f_out.write(dati_cifrati)

            return True, f"Backup cifrato salvato con successo: {nome_backup}"
        else:
            nome_backup = f"backup_fabbrica_{timestamp}.db"
            percorso_finale = os.path.join(cartella_destinazione, nome_backup)
            shutil.copy2(DB_PATH, percorso_finale)
            return True, f"Backup standard salvato con successo: {nome_backup}"

    except Exception as e:
        return False, f"Errore durante l'esecuzione del backup: {e}"

def ripristina_backup_cifrato(percorso_file_enc: str, key_path: str = KEY_FILE) -> tuple[bool, str]:
    """Decifra un file di backup .enc e sovrascrive il file database attuale."""
    if not os.path.exists(percorso_file_enc):
        return False, "File di backup specificato non trovato."
    
    if not os.path.exists(key_path):
        return False, "Chiave di decifratura (secret.key) non trovata."

    try:
        with open(key_path, "rb") as f:
            key = f.read()
        
        fernet = Fernet(key)

        with open(percorso_file_enc, "rb") as f_enc:
            dati_cifrati = f_enc.read()

        dati_decifrati = fernet.decrypt(dati_cifrati)

        with open(DB_PATH, "wb") as f_db:
            f_db.write(dati_decifrati)

        return True, "Database ripristinato con successo!"
    except Exception as e:
        return False, f"Errore durante il ripristino (chiave errata o file corrotto): {e}"

def controlla_ed_esegui_backup_automatico(cartella_destinazione: str = "./backups", intervallo_ore: int = 24) -> tuple[bool, str]:
    """
    Controlla la data dell'ultimo backup presente nella cartella.
    Se sono trascorse più di 'intervallo_ore' ore (o non esistono backup),
    esegue automaticamente un nuovo backup cifrato.
    """
    if not os.path.exists(cartella_destinazione):
        os.makedirs(cartella_destinazione, exist_ok=True)

    files = [os.path.join(cartella_destinazione, f) for f in os.listdir(cartella_destinazione) if f.startswith("backup_fabbrica_")]

    esegui = False
    if not files:
        esegui = True
    else:
        ultimo_file = max(files, key=os.path.getmtime)
        ora_ultimo_backup = datetime.fromtimestamp(os.path.getmtime(ultimo_file))
        ore_trascorse = (datetime.now() - ora_ultimo_backup).total_seconds() / 3600

        if ore_trascorse >= intervallo_ore:
            esegui = True

    if esegui:
        return esegui_backup_cifrato(cartella_destinazione, cifrato=True)
    
    return False, "Backup non necessario: l'ultimo backup è recente."
