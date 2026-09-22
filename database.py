import sqlite3
import hashlib
import os

DB_NAME = "fabbrica_locale.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    # Ottimizzazione prestazioni SQLite per letture veloci
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn

# --- FUNZIONI SECURITY PER PASSWORDS ---
def hash_password(password: str, salt: bytes = None) -> tuple[str, str]:
    if salt is None:
        salt = os.urandom(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return hashed.hex(), salt.hex()

def verify_password(stored_hash: str, stored_salt: str, password_provided: str) -> bool:
    salt = bytes.fromhex(stored_salt)
    hashed_provided = hashlib.pbkdf2_hmac('sha256', password_provided.encode('utf-8'), salt, 100000).hex()
    return hashed_provided == stored_hash

# --- INIZIALIZZAZIONE DATABASE ---
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 0. Tabella Utenti
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS utenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            nome_completo TEXT NOT NULL,
            ruolo TEXT NOT NULL,
            attivo INTEGER DEFAULT 1,
            data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM utenti")
    if cursor.fetchone()[0] == 0:
        pwd_hash, salt = hash_password("admin123")
        cursor.execute("""
            INSERT INTO utenti (username, password_hash, salt, nome_completo, ruolo, attivo)
            VALUES (?, ?, ?, ?, ?, 1)
        """, ('admin', pwd_hash, salt, 'Amministratore di Sistema', 'Admin'))

    # 1. Anagrafica Part Numbers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS part_numbers (
            pn_codice TEXT PRIMARY KEY,
            descrizione TEXT,
            ubicazione TEXT
        )
    """)

    # 2. Anagrafica Clienti
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clienti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codice_cliente TEXT UNIQUE NOT NULL,
            ragione_sociale TEXT NOT NULL,
            referente TEXT,
            note TEXT,
            data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 3. Quantità Magazzino
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS magazzino_quantita (
            pn_codice TEXT PRIMARY KEY,
            quantita_disponibile INTEGER DEFAULT 0,
            ubicazione TEXT,
            operatore TEXT,
            data_ultimo_carico TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pn_codice) REFERENCES part_numbers(pn_codice)
        )
    """)

    # 4. Storico Carichi Magazzino
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS storico_carichi_magazzino (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pn_codice TEXT NOT NULL,
            quantita_caricata INTEGER NOT NULL,
            ubicazione TEXT NOT NULL,
            operatore TEXT NOT NULL,
            data_ora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pn_codice) REFERENCES part_numbers(pn_codice)
        )
    """)

    # 5. Commesse
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS commesse (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codice_commessa TEXT UNIQUE NOT NULL,
            codice_cliente TEXT,
            modello_centralina TEXT NOT NULL DEFAULT 'STD',
            quantita_totale INTEGER NOT NULL DEFAULT 1,
            quantita_originale INTEGER,
            motivo_modifica_qta TEXT,
            stato TEXT DEFAULT 'Aperta',
            data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (codice_cliente) REFERENCES clienti(codice_cliente)
        )
    """)

    cursor.execute("PRAGMA table_info(commesse)")
    colonne_esistenti = [row['name'] for row in cursor.fetchall()]

    if 'codice_cliente' not in colonne_esistenti:
        try: cursor.execute("ALTER TABLE commesse ADD COLUMN codice_cliente TEXT")
        except Exception: pass

    if 'modello_centralina' not in colonne_esistenti:
        try: cursor.execute("ALTER TABLE commesse ADD COLUMN modello_centralina TEXT NOT NULL DEFAULT 'STD'")
        except Exception: pass

    if 'quantita_totale' not in colonne_esistenti:
        try: cursor.execute("ALTER TABLE commesse ADD COLUMN quantita_totale INTEGER NOT NULL DEFAULT 1")
        except Exception: pass

    if 'quantita_originale' not in colonne_esistenti:
        try: cursor.execute("ALTER TABLE commesse ADD COLUMN quantita_originale INTEGER")
        except Exception: pass

    if 'motivo_modifica_qta' not in colonne_esistenti:
        try: cursor.execute("ALTER TABLE commesse ADD COLUMN motivo_modifica_qta TEXT")
        except Exception: pass

    if 'stato' not in colonne_esistenti:
        try: cursor.execute("ALTER TABLE commesse ADD COLUMN stato TEXT DEFAULT 'Aperta'")
        except Exception: pass

    # Allinea la quantita_originale per i record creati precedentemente
    cursor.execute("UPDATE commesse SET quantita_originale = quantita_totale WHERE quantita_originale IS NULL")

    # 6. Distinta Base Centraline Finali
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS distinte_basi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            modello TEXT NOT NULL,
            pn_componente TEXT NOT NULL,
            quantita_richiesta INTEGER NOT NULL,
            UNIQUE(modello, pn_componente),
            FOREIGN KEY (pn_componente) REFERENCES part_numbers(pn_codice)
        )
    """)

    # 7. Distinta Base Sotto-Schede
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS distinte_sotto_schede (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pn_sotto_scheda TEXT NOT NULL,
            pn_componente TEXT NOT NULL,
            quantita_richiesta INTEGER NOT NULL,
            UNIQUE(pn_sotto_scheda, pn_componente),
            FOREIGN KEY (pn_componente) REFERENCES part_numbers(pn_codice)
        )
    """)

    # 8. Schede Centraline Prodotte
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS centraline (
            serial_centralina TEXT PRIMARY KEY,
            commessa_padre TEXT NOT NULL,
            tipologia TEXT NOT NULL,
            fase_attuale TEXT DEFAULT 'Assemblaggio',
            note TEXT,
            data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (commessa_padre) REFERENCES commesse(codice_commessa)
        )
    """)

    # 9. Componenti Utilizzati per Centralina
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS componenti_centralina (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_centralina TEXT NOT NULL,
            pn_codice TEXT NOT NULL,
            quantita_usata INTEGER NOT NULL,
            data_associazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (serial_centralina) REFERENCES centraline(serial_centralina),
            FOREIGN KEY (pn_codice) REFERENCES part_numbers(pn_codice)
        )
    """)

    # 10. Storico Fasi Avanzamento
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS storico_fasi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_centralina TEXT NOT NULL,
            fase_destinazione TEXT NOT NULL,
            operatore TEXT NOT NULL,
            data_ora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (serial_centralina) REFERENCES centraline(serial_centralina)
        )
    """)

    # 11. Configurazione Tipologie Modelli
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config_tipologie (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipologia TEXT UNIQUE NOT NULL
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM config_tipologie")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO config_tipologie (tipologia) VALUES (?)",
            [('Master',), ('Slave',), ('StandAlone',)]
        )

    # 12. RMA Segnalazioni
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rma_segnalazioni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codice_rma TEXT UNIQUE NOT NULL,
            data_segnalazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            origine TEXT CHECK(origine IN ('Collaudo Interno', 'Reso Cliente')),
            serial_centralina TEXT,
            codice_cliente TEXT,
            sintomo_guasto TEXT NOT NULL,
            gravita TEXT CHECK(gravita IN ('Bassa', 'Media', 'Alta', 'Critica')),
            stato TEXT DEFAULT 'In Attesa' CHECK(stato IN ('In Attesa', 'In Lavorazione', 'Riparato', 'Scartato')),
            operatore_segnalatore TEXT NOT NULL,
            FOREIGN KEY (serial_centralina) REFERENCES centraline(serial_centralina),
            FOREIGN KEY (codice_cliente) REFERENCES clienti(codice_cliente)
        )
    """)

    # 13. Log Riparazioni / Interventi RMA
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rma_riparazioni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rma_id INTEGER NOT NULL,
            tecnico TEXT NOT NULL,
            data_intervento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            diagnosi TEXT,
            azioni_eseguite TEXT,
            esito TEXT CHECK(esito IN ('In Lavorazione', 'Riparato', 'Scartato')),
            FOREIGN KEY (rma_id) REFERENCES rma_segnalazioni(id)
        )
    """)

    # 14. Ricambi Usati nelle Riparazioni
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rma_ricambi_usati (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rma_id INTEGER NOT NULL,
            pn_componente TEXT NOT NULL,
            quantita INTEGER NOT NULL DEFAULT 1,
            tecnico TEXT NOT NULL,
            data_utilizzo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (rma_id) REFERENCES rma_segnalazioni(id),
            FOREIGN KEY (pn_componente) REFERENCES part_numbers(pn_codice)
        )
    """)

    # --- INDICI PER PRESTAZIONI SU TABELLE AD ALTO VOLUME (40.000+ RECORD) ---
    indici = [
        "CREATE INDEX IF NOT EXISTS idx_pn_descrizione ON part_numbers(descrizione);",
        "CREATE INDEX IF NOT EXISTS idx_pn_ubicazione ON part_numbers(ubicazione);",
        "CREATE INDEX IF NOT EXISTS idx_magazzino_pn ON magazzino_quantita(pn_codice);",
        "CREATE INDEX IF NOT EXISTS idx_storico_carichi_pn ON storico_carichi_magazzino(pn_codice);",
        "CREATE INDEX IF NOT EXISTS idx_commesse_cliente ON commesse(codice_cliente);",
        "CREATE INDEX IF NOT EXISTS idx_commesse_stato ON commesse(stato);",
        "CREATE INDEX IF NOT EXISTS idx_distinte_modello ON distinte_basi(modello);",
        "CREATE INDEX IF NOT EXISTS idx_distinte_pn ON distinte_basi(pn_componente);",
        "CREATE INDEX IF NOT EXISTS idx_distinte_sub_scheda ON distinte_sotto_schede(pn_sotto_scheda);",
        "CREATE INDEX IF NOT EXISTS idx_centraline_commessa ON centraline(commessa_padre);",
        "CREATE INDEX IF NOT EXISTS idx_centraline_fase ON centraline(fase_attuale);",
        "CREATE INDEX IF NOT EXISTS idx_componenti_serial ON componenti_centralina(serial_centralina);",
        "CREATE INDEX IF NOT EXISTS idx_componenti_pn ON componenti_centralina(pn_codice);",
        "CREATE INDEX IF NOT EXISTS idx_storico_fasi_serial ON storico_fasi(serial_centralina);",
        "CREATE INDEX IF NOT EXISTS idx_rma_serial ON rma_segnalazioni(serial_centralina);",
        "CREATE INDEX IF NOT EXISTS idx_rma_cliente ON rma_segnalazioni(codice_cliente);",
        "CREATE INDEX IF NOT EXISTS idx_rma_stato ON rma_segnalazioni(stato);",
        "CREATE INDEX IF NOT EXISTS idx_rma_riparazioni_rma_id ON rma_riparazioni(rma_id);",
        "CREATE INDEX IF NOT EXISTS idx_rma_ricambi_rma_id ON rma_ricambi_usati(rma_id);"
    ]

    for idx_sql in indici:
        cursor.execute(idx_sql)

    conn.commit()
    conn.close()

# --- FUNZIONI OPERATIVE PER ANAGRAFICA E MAGAZZINO AD ALTE PRESTAZIONI (PAGINAZIONE & RICERCA) ---

def get_part_numbers_paginati(limit: int = 50, offset: int = 0, filtro_ricerca: str = ""):
    """Restituisce solo i campi necessari paginati, gestendo la ricerca rapida per codice o descrizione."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if filtro_ricerca:
        pattern = f"%{filtro_ricerca.strip()}%"
        query = """
            SELECT pn.pn_codice, pn.descrizione, pn.ubicazione, COALESCE(m.quantita_disponibile, 0) AS quantita_disponibile
            FROM part_numbers pn
            LEFT JOIN magazzino_quantita m ON pn.pn_codice = m.pn_codice
            WHERE pn.pn_codice LIKE ? OR pn.descrizione LIKE ?
            ORDER BY pn.pn_codice ASC
            LIMIT ? OFFSET ?
        """
        cursor.execute(query, (pattern, pattern, limit, offset))
    else:
        query = """
            SELECT pn.pn_codice, pn.descrizione, pn.ubicazione, COALESCE(m.quantita_disponibile, 0) AS quantita_disponibile
            FROM part_numbers pn
            LEFT JOIN magazzino_quantita m ON pn.pn_codice = m.pn_codice
            ORDER BY pn.pn_codice ASC
            LIMIT ? OFFSET ?
        """
        cursor.execute(query, (limit, offset))
        
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def count_part_numbers(filtro_ricerca: str = "") -> int:
    """Conta il numero totale di Part Numbers per calcolare il numero di pagine nell'interfaccia."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if filtro_ricerca:
        pattern = f"%{filtro_ricerca.strip()}%"
        cursor.execute("SELECT COUNT(*) FROM part_numbers WHERE pn_codice LIKE ? OR descrizione LIKE ?", (pattern, pattern))
    else:
        cursor.execute("SELECT COUNT(*) FROM part_numbers")
    totale = cursor.fetchone()[0]
    conn.close()
    return totale

def get_tutti_pn_codici_light():
    """Versione ultraleggera per popolare solo le selezioni Selectbox (es. nei form), estraendo solo la chiave primaria."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT pn_codice FROM part_numbers ORDER BY pn_codice ASC")
    lista = [row['pn_codice'] for row in cursor.fetchall()]
    conn.close()
    return lista

# --- FUNZIONI UTENTI CRUD ---
def autentica_utente(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password_hash, salt, nome_completo, ruolo, attivo FROM utenti WHERE username = ? AND attivo = 1", (username,))
    user = cursor.fetchone()
    conn.close()

    if user and verify_password(user['password_hash'], user['salt'], password):
        return dict(user)
    return None

def get_tutti_utenti():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, nome_completo, ruolo, attivo FROM utenti")
    utenti = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return utenti

def crea_utente(username, password, nome_completo, ruolo):
    pwd_hash, salt = hash_password(password)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO utenti (username, password_hash, salt, nome_completo, ruolo, attivo)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (username, pwd_hash, salt, nome_completo, ruolo))
        conn.commit()
        return True, "Utente creato con successo!"
    except sqlite3.IntegrityError:
        return False, "Username già esistente."
    finally:
        conn.close()

def aggiorna_stato_utente(username, nuovo_ruolo, nuovo_stato_attivo):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE utenti 
            SET ruolo = ?, attivo = ? 
            WHERE username = ?
        """, (nuovo_ruolo, nuovo_stato_attivo, username))
        conn.commit()
        return True, f"Utente '{username}' aggiornato con successo!"
    except Exception as e:
        return False, f"Errore durante l'aggiornamento: {e}"
    finally:
        conn.close()

def elimina_utente_protetto(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT nome_completo FROM utenti WHERE username = ?", (username,))
        row = cursor.fetchone()
        if not row:
            return False, "Utente non trovato."
        
        nome_completo = row['nome_completo']

        cursor.execute("""
            SELECT COUNT(*) FROM storico_fasi WHERE operatore LIKE ? OR operatore LIKE ?
        """, (f"%{username}%", f"%{nome_completo}%"))
        fasi_tot = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM storico_carichi_magazzino WHERE operatore LIKE ? OR operatore LIKE ?
        """, (f"%{username}%", f"%{nome_completo}%"))
        carichi_tot = cursor.fetchone()[0]

        if (fasi_tot + carichi_tot) > 0:
            return False, f"Impossibile eliminare: l'utente ha registrato {fasi_tot + carichi_tot} operazioni nel sistema. Disabilita l'account per preservare la tracciabilità."

        cursor.execute("DELETE FROM utenti WHERE username = ?", (username,))
        conn.commit()
        return True, f"Utente '{username}' eliminato definitivamente!"
    except Exception as e:
        return False, f"Errore durante l'eliminazione: {e}"
    finally:
        conn.close()

# --- FUNZIONI OPERATIVE RMA & QUALITÀ ---

def genera_codice_rma():
    import datetime
    anno = datetime.datetime.now().strftime("%Y")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM rma_segnalazioni WHERE codice_rma LIKE ?", (f"RMA-{anno}-%",))
    count = cursor.fetchone()[0] + 1
    conn.close()
    return f"RMA-{anno}-{count:04d}"

def inserisci_segnalazione_rma(origine, serial_centralina, codice_cliente, sintomo_guasto, gravita, operatore):
    codice_rma = genera_codice_rma()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO rma_segnalazioni 
            (codice_rma, origine, serial_centralina, codice_cliente, sintomo_guasto, gravita, operatore_segnalatore)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (codice_rma, origine, serial_centralina, codice_cliente, sintomo_guasto, gravita, operatore))
        conn.commit()
        return True, f"Segnalazione registrata con successo! Codice: {codice_rma}"
    except Exception as e:
        return False, f"Errore durante l'inserimento: {e}"
    finally:
        conn.close()

def get_rma_attivi():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.id, r.codice_rma, r.data_segnalazione, r.origine, r.serial_centralina, 
               r.codice_cliente, r.sintomo_guasto, r.gravita, r.stato, r.operatore_segnalatore, 
               c.ragione_sociale 
        FROM rma_segnalazioni r
        LEFT JOIN clienti c ON r.codice_cliente = c.codice_cliente
        WHERE r.stato IN ('In Attesa', 'In Lavorazione')
        ORDER BY r.data_segnalazione DESC
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def registra_intervento_rma(rma_id, tecnico, diagnosi, azioni, esito_finale):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN TRANSACTION;")
        
        cursor.execute("""
            INSERT INTO rma_riparazioni (rma_id, tecnico, diagnosi, azioni_eseguite, esito)
            VALUES (?, ?, ?, ?, ?)
        """, (rma_id, tecnico, diagnosi, azioni, esito_finale))
        
        cursor.execute("UPDATE rma_segnalazioni SET stato = ? WHERE id = ?", (esito_finale, rma_id))
        
        conn.commit()
        return True, "Intervento registrato ed esito aggiornato!"
    except Exception as e:
        conn.rollback()
        return False, f"Errore durante il salvataggio: {e}"
    finally:
        conn.close()

def scarica_ricambio_rma(rma_id, pn_componente, quantita, tecnico):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN TRANSACTION;")
        
        cursor.execute("SELECT quantita_disponibile FROM magazzino_quantita WHERE pn_codice = ?", (pn_componente,))
        row = cursor.fetchone()
        if not row or row['quantita_disponibile'] < quantita:
            qta_disp = row['quantita_disponibile'] if row else 0
            conn.rollback()
            return False, f"Giacenza insufficiente per {pn_componente}. Disponibili: {qta_disp}, Richiesti: {quantita}"
        
        cursor.execute("""
            UPDATE magazzino_quantita 
            SET quantita_disponibile = quantita_disponibile - ? 
            WHERE pn_codice = ?
        """, (quantita, pn_componente))
        
        cursor.execute("""
            INSERT INTO rma_ricambi_usati (rma_id, pn_componente, quantita, tecnico)
            VALUES (?, ?, ?, ?)
        """, (rma_id, pn_componente, quantita, tecnico))
        
        conn.commit()
        return True, f"Scaricate {quantita} pz di {pn_componente} dal magazzino."
    except Exception as e:
        conn.rollback()
        return False, f"Errore nello scarico del componente: {e}"
    finally:
        conn.close()

def get_storico_completo_rma():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.id, r.codice_rma, r.data_segnalazione, r.origine, r.serial_centralina, 
               r.codice_cliente, r.sintomo_guasto, r.gravita, r.stato, r.operatore_segnalatore, 
               c.ragione_sociale 
        FROM rma_segnalazioni r
        LEFT JOIN clienti c ON r.codice_cliente = c.codice_cliente
        ORDER BY r.data_segnalazione DESC
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_dettagli_rma(rma_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, rma_id, tecnico, data_intervento, diagnosi, azioni_eseguite, esito FROM rma_riparazioni WHERE rma_id = ? ORDER BY data_intervento DESC", (rma_id,))
    interventi = [dict(r) for r in cursor.fetchall()]
    
    cursor.execute("SELECT id, rma_id, pn_componente, quantita, tecnico, data_utilizzo FROM rma_ricambi_usati WHERE rma_id = ? ORDER BY data_utilizzo DESC", (rma_id,))
    ricambi = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    return interventi, ricambi

def cerca_kb_soluzioni(query_txt):
    """Cerca tra gli RMA passati risolti con successo matching con il sintomo o con la diagnosi."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    like_pattern = f"%{query_txt.strip()}%"
    cursor.execute("""
        SELECT r.id, r.codice_rma, r.serial_centralina, r.sintomo_guasto, 
               p.diagnosi, p.azioni_eseguite, p.tecnico, p.data_intervento
        FROM rma_riparazioni p
        JOIN rma_segnalazioni r ON p.rma_id = r.id
        WHERE p.esito = 'Riparato' 
        AND (UPPER(r.sintomo_guasto) LIKE UPPER(?) OR UPPER(p.diagnosi) LIKE UPPER(?) OR UPPER(p.azioni_eseguite) LIKE UPPER(?))
        ORDER BY p.data_intervento DESC
    """, (like_pattern, like_pattern, like_pattern))
    
    risultati = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return risultati
