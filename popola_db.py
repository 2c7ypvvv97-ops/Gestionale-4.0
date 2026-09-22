import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "fabbrica_locale.db")

print(f"📌 Rigenerazione e popolamento del database in corso su: {DB_PATH}")

SQL_SCRIPT = """
PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS schede;
DROP TABLE IF EXISTS schede_magazzino;
DROP TABLE IF EXISTS storico_fasi;
DROP TABLE IF EXISTS centraline;
DROP TABLE IF EXISTS commesse;
DROP TABLE IF EXISTS magazzino_quantita;
DROP TABLE IF EXISTS distinte_basi;
DROP TABLE IF EXISTS part_numbers;
DROP TABLE IF EXISTS clienti;
DROP TABLE IF EXISTS config_tipologie;

PRAGMA foreign_keys = ON;

CREATE TABLE config_tipologie (
    tipologia TEXT PRIMARY KEY,
    numero_partenza INTEGER DEFAULT 1
);

CREATE TABLE clienti (
    codice_cliente TEXT PRIMARY KEY,
    ragione_sociale TEXT NOT NULL,
    referente TEXT,
    note TEXT,
    data_creazione TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE part_numbers (
    pn_codice TEXT PRIMARY KEY,
    descrizione TEXT,
    ubicazione TEXT
);

CREATE TABLE distinte_basi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    modello TEXT NOT NULL,
    pn_componente TEXT REFERENCES part_numbers(pn_codice),
    quantita_richiesta INTEGER NOT NULL
);

CREATE TABLE magazzino_quantita (
    pn_codice TEXT PRIMARY KEY REFERENCES part_numbers(pn_codice),
    quantita_disponibile INTEGER NOT NULL DEFAULT 0,
    ubicazione TEXT,
    operatore TEXT,
    data_ultimo_carico TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE commesse (
    codice_commessa TEXT PRIMARY KEY,
    codice_cliente TEXT REFERENCES clienti(codice_cliente),
    tipologia TEXT REFERENCES config_tipologie(tipologia),
    quantita_massima INTEGER NOT NULL,
    fase_attuale TEXT DEFAULT 'Aperta',
    data_creazione TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE centraline (
    serial_centralina TEXT PRIMARY KEY,
    tipologia TEXT NOT NULL,
    serial_num INTEGER NOT NULL,
    commessa_padre TEXT REFERENCES commesse(codice_commessa),
    fase_attuale TEXT NOT NULL,
    note TEXT DEFAULT '',
    data_creazione TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tipologia, serial_num)
);

CREATE TABLE storico_fasi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    serial_centralina TEXT REFERENCES centraline(serial_centralina),
    fase_destinazione TEXT NOT NULL,
    operatore TEXT NOT NULL,
    data_ora TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE schede_magazzino (
    qr_scheda TEXT PRIMARY KEY,
    codice_commessa TEXT,
    data_carico TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE schede (
    qr_scheda TEXT PRIMARY KEY REFERENCES schede_magazzino(qr_scheda),
    serial_centralina TEXT REFERENCES centraline(serial_centralina),
    data_association TEXT DEFAULT CURRENT_TIMESTAMP
);

-- INSERIMENTO DATI TEST
INSERT INTO config_tipologie (tipologia, numero_partenza) VALUES 
('MOD_PWR_2026', 100),
('CENTRALINA_SLIM', 500),
('BOX_SENSOR_PRO', 1000);

INSERT INTO clienti (codice_cliente, ragione_sociale, referente, note) VALUES
('CLI-001', 'ACME Industries S.r.l.', 'Ing. Mario Rossi', 'Contatti: ordini@acme.it'),
('CLI-002', 'TechPro Automotive Gmbh', 'Klaus Weber', 'Contatti: k.weber@techpro.de'),
('CLI-003', 'Elettronica Veneta SpA', 'Dott.ssa Elena Bianchi', 'Contatti: acquisti@elven.it');

INSERT INTO part_numbers (pn_codice, descrizione, ubicazione) VALUES
('CPU_K', 'Processore di Controllo Principale', 'SCAFFALE-A1'),
('ALIM_K', 'Modulo Alimentazione 12V/24V', 'SCAFFALE-A2'),
('SENS_K', 'Sensore Termico Integrato', 'SCAFFALE-B1'),
('DISP_LCD_01', 'Display LCD TFT 4.3 Pollici', 'SCAFFALE-B2'),
('REL_DRV_02', 'Driver Relè Industriale High Power', 'SCAFFALE-C1');

INSERT INTO distinte_basi (modello, pn_componente, quantita_richiesta) VALUES
('MOD_PWR_2026', 'CPU_K', 1),
('MOD_PWR_2026', 'ALIM_K', 1),
('MOD_PWR_2026', 'SENS_K', 2),
('CENTRALINA_SLIM', 'CPU_K', 1),
('CENTRALINA_SLIM', 'ALIM_K', 1),
('CENTRALINA_SLIM', 'DISP_LCD_01', 1),
('BOX_SENSOR_PRO', 'CPU_K', 1),
('BOX_SENSOR_PRO', 'SENS_K', 4),
('BOX_SENSOR_PRO', 'REL_DRV_02', 2);

INSERT INTO magazzino_quantita (pn_codice, quantita_disponibile, ubicazione, operatore) VALUES
('CPU_K', 45, 'SCAFFALE-A1', 'LUIGI_M'),
('ALIM_K', 30, 'SCAFFALE-A2', 'LUIGI_M'),
('SENS_K', 18, 'SCAFFALE-B1', 'MARCO_B'),
('DISP_LCD_01', 12, 'SCAFFALE-B2', 'MARCO_B'),
('REL_DRV_02', 50, 'SCAFFALE-C1', 'LUIGI_M');

INSERT INTO commesse (codice_commessa, codice_cliente, tipologia, quantita_massima, fase_attuale) VALUES
('C2026-001', 'CLI-001', 'MOD_PWR_2026', 10, 'In Produzione'),
('C2026-002', 'CLI-002', 'CENTRALINA_SLIM', 5, 'Aperta'),
('C2026-003', 'CLI-003', 'BOX_SENSOR_PRO', 20, 'Aperta');

INSERT INTO centraline (serial_centralina, tipologia, serial_num, commessa_padre, fase_attuale, note) VALUES
('MOD_PWR_2026-100', 'MOD_PWR_2026', 100, 'C2026-001', 'Collaudo Superato', 'Assemblaggio completato'),
('MOD_PWR_2026-101', 'MOD_PWR_2026', 101, 'C2026-001', 'Assemblaggio Componenti', 'In lavorazione banco 2'),
('MOD_PWR_2026-102', 'MOD_PWR_2026', 102, 'C2026-001', 'In attesa componenti', 'Pezzi mancanti');

INSERT INTO storico_fasi (serial_centralina, fase_destinazione, operatore) VALUES
('MOD_PWR_2026-100', 'Registrazione Seriale', 'SYSTEM'),
('MOD_PWR_2026-100', 'Assemblaggio Componenti', 'GIOVANNI_V'),
('MOD_PWR_2026-100', 'Collaudo Superato', 'ALBERTO_T'),
('MOD_PWR_2026-101', 'Registrazione Seriale', 'SYSTEM'),
('MOD_PWR_2026-101', 'Assemblaggio Componenti', 'GIOVANNI_V'),
('MOD_PWR_2026-102', 'Registrazione Seriale', 'SYSTEM');
"""

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executescript(SQL_SCRIPT)
    conn.commit()
    conn.close()
    print("✅ Operazione completata! Tabella clienti aggiornata e popolata correttamente.")
except Exception as e:
    print(f"❌ Errore durante il popolamento: {e}")
