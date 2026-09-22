import sqlite3
import random
import time
import database

def genera_dati_fittizi(num_pn: int = 40000):
    print(f"🚀 Inizio generazione di {num_pn} record nell'Anagrafica Part Numbers...")
    start_time = time.time()

    # Assicura che il database sia inizializzato
    database.init_db()
    
    conn = database.get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("BEGIN TRANSACTION;")

        # 1. Popolamento Clienti Fittizi
        clienti_dummy = [
            ("CLI-001", "AeroTech S.p.A.", "Marco Rossi", "Cliente Settore Avionico"),
            ("CLI-002", "ElectroAuto S.r.l.", "Giulia Bianchi", "Fornitura Centraline Automotive"),
            ("CLI-003", "Robotics Dynamics", "Luca Verdi", "Progetti R&D Robotica"),
            ("CLI-004", "GreenPower Energy", "Elena Neri", "Inverter e Sistemi BESS")
        ]
        cursor.executemany("""
            INSERT INTO clienti (codice_cliente, ragione_sociale, referente, note)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(codice_cliente) DO NOTHING;
        """, clienti_dummy)

        # 2. Popolamento Massivo 40.000+ Part Numbers & Magazzino
        prefissi = ["RES", "CAP", "IND", "IC", "MOS", "CONN", "PCB", "MCU", "DISP", "TRANS"]
        ubicazioni = [f"MAG-{c}{n}" for c in ["A", "B", "C", "D"] for n in range(1, 20)]

        pn_list = []
        mag_list = []

        for i in range(1, num_pn + 1):
            pref = random.choice(prefissi)
            pn_code = f"{pref}-{i:06d}"
            desc = f"Componente Elettronico {pref} Specifica Standard {i}"
            ubica = random.choice(ubicazioni)
            qta = random.randint(0, 500)

            pn_list.append((pn_code, desc, ubica))
            mag_list.append((pn_code, qta, ubica, "Sistema Batch"))

        # Inserimento ottimizzato in blocchi massivi
        cursor.executemany("""
            INSERT INTO part_numbers (pn_codice, descrizione, ubicazione)
            VALUES (?, ?, ?)
            ON CONFLICT(pn_codice) DO NOTHING;
        """, pn_list)

        cursor.executemany("""
            INSERT INTO magazzino_quantita (pn_codice, quantita_disponibile, ubicazione, operatore)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(pn_codice) DO NOTHING;
        """, mag_list)

        # 3. Popolamento Commesse Fittizie
        commesse_dummy = [
            ("COM-2026-001", "CLI-001", "Master", 50, 50, "Aperta"),
            ("COM-2026-002", "CLI-002", "Slave", 120, 120, "Aperta"),
            ("COM-2026-003", "CLI-003", "StandAlone", 30, 30, "In Lavorazione")
        ]
        cursor.executemany("""
            INSERT INTO commesse (codice_commessa, codice_cliente, modello_centralina, quantita_totale, quantita_originale, stato)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(codice_commessa) DO NOTHING;
        """, commesse_dummy)

        conn.commit()
        elapsed = time.time() - start_time
        print(f"✅ Generazione completata con successo in {elapsed:.2f} secondi!")
        print(f"📊 Part Numbers inseriti: {num_pn}")

    except Exception as e:
        conn.rollback()
        print(f"❌ Errore durante la generazione dei dati fittizi: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    genera_dati_fittizi(40000)
