import pandas as pd
import io
import streamlit as st
import database

def genera_template_excel(tipo: str) -> bytes:
    """Genera un file Excel in memoria da usare come template da far scaricare agli utenti."""
    buffer = io.BytesIO()
    
    if tipo == "part_numbers":
        df = pd.DataFrame(columns=["pn_codice", "descrizione", "ubicazione", "quantita_iniziale"])
        # Esempio di riga
        df.loc[0] = ["PN-10001", "Resistenza 10k 0805", "MAG-A1", 100]
    elif tipo == "clienti":
        df = pd.DataFrame(columns=["codice_cliente", "ragione_sociale", "referente", "note"])
        df.loc[0] = ["CLI-001", "Acme S.r.l.", "Mario Rossi", "Cliente Premium"]
    elif tipo == "distinta_base":
        df = pd.DataFrame(columns=["modello", "pn_componente", "quantita_richiesta"])
        df.loc[0] = ["MOD-STD-01", "PN-10001", 4]

    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Template')
        
    return buffer.getvalue()


def importa_part_numbers_df(df: pd.DataFrame) -> tuple[bool, str]:
    """Elabora il dataframe per l'inserimento o aggiornamento di massa dei Part Numbers."""
    colonne_richieste = {"pn_codice", "descrizione", "ubicazione"}
    if not colonne_richieste.issubset(set(df.columns)):
        return False, f"Colonne mancanti. Il file deve contenere: {', '.join(colonne_richieste)}"

    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN TRANSACTION;")
        
        # Inserimento o aggiornamento Anagrafica PN
        dati_pn = [(str(row['pn_codice']).strip(), str(row['descrizione']).strip(), str(row['ubicazione']).strip()) for _, row in df.iterrows()]
        
        cursor.executemany("""
            INSERT INTO part_numbers (pn_codice, descrizione, ubicazione)
            VALUES (?, ?, ?)
            ON CONFLICT(pn_codice) DO UPDATE SET
                descrizione = excluded.descrizione,
                ubicazione = excluded.ubicazione;
        """, dati_pn)

        # Se nel file è presente la colonna quantita_iniziale, aggiorna anche il magazzino
        if "quantita_iniziale" in df.columns:
            dati_mag = [(str(row['pn_codice']).strip(), int(row['quantita_iniziale']), str(row['ubicazione']).strip()) 
                        for _, row in df.iterrows() if pd.notnull(row['quantita_iniziale'])]
            
            cursor.executemany("""
                INSERT INTO magazzino_quantita (pn_codice, quantita_disponibile, ubicazione)
                VALUES (?, ?, ?)
                ON CONFLICT(pn_codice) DO UPDATE SET
                    quantita_disponibile = excluded.quantita_disponibile,
                    ubicazione = excluded.ubicazione;
            """, dati_mag)

        conn.commit()
        return True, f"Importazione completata con successo! Inseriti/Aggiornati {len(df)} record."
    except Exception as e:
        conn.rollback()
        return False, f"Errore durante l'importazione massiva: {e}"
    finally:
        conn.close()


def render_importazione_ui():
    st.title("📥 Importazione Massiva Dati (Excel / CSV)")
    st.write("Carica elenchi di Part Numbers, Clienti o Distinte Base da file Excel per popolare rapidamente il database.")

    tab1, tab2 = st.tabs(["📦 Anagrafica Part Numbers (BOM)", "👥 Clienti e Distinte Base"])

    with tab1:
        st.subheader("Importa Anagrafica Articoli (fino a 40.000+ record)")
        
        col_dl, col_up = st.columns([1, 2])
        
        with col_dl:
            st.markdown("##### 1. Scarica Template")
            template_bytes = genera_template_excel("part_numbers")
            st.download_button(
                label="📄 Scarica Template Excel",
                data=template_bytes,
                file_name="template_part_numbers.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with col_up:
            st.markdown("##### 2. Carica File Compilato")
            uploaded_file = st.file_uploader("Scegli un file .xlsx o .csv", type=["xlsx", "csv"], key="up_pn")
            
            if uploaded_file is not None:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        df = pd.read_csv(uploaded_file)
                    else:
                        df = pd.read_excel(uploaded_file)

                    st.write(f"Anteprima dati da importare ({len(df)} righe):")
                    st.dataframe(df.head(5), use_container_width=True)

                    if st.button("🚀 Avvia Importazione Massiva", type="primary"):
                        with st.spinner("Importazione ed elaborazione in corso..."):
                            ok, msg = importa_part_numbers_df(df)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                except Exception as e:
                    st.error(f"Impossibile leggere il file: {e}")
