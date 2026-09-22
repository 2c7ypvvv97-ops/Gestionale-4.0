import pandas as pd
import io
import streamlit as st
import database

def genera_template_excel(tipo: str) -> bytes:
    """Genera un file Excel in memoria da usare come template da far scaricare agli utenti."""
    buffer = io.BytesIO()
    
    if tipo == "part_numbers":
        df = pd.DataFrame(columns=["pn_codice", "descrizione", "ubicazione", "quantita_iniziale"])
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
        
        dati_pn = [(str(row['pn_codice']).strip(), str(row['descrizione']).strip(), str(row['ubicazione']).strip()) for _, row in df.iterrows()]
        
        cursor.executemany("""
            INSERT INTO part_numbers (pn_codice, descrizione, ubicazione)
            VALUES (?, ?, ?)
            ON CONFLICT(pn_codice) DO UPDATE SET
                descrizione = excluded.descrizione,
                ubicazione = excluded.ubicazione;
        """, dati_pn)

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


def importa_clienti_df(df: pd.DataFrame) -> tuple[bool, str]:
    """Elabora il dataframe per l'inserimento o aggiornamento dei Clienti."""
    colonne_richieste = {"codice_cliente", "ragione_sociale"}
    if not colonne_richieste.issubset(set(df.columns)):
        return False, f"Colonne mancanti. Il file deve contenere almeno: {', '.join(colonne_richieste)}"

    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN TRANSACTION;")
        
        dati_clienti = [
            (
                str(row['codice_cliente']).strip(), 
                str(row['ragione_sociale']).strip(), 
                str(row.get('referente', '')).strip(), 
                str(row.get('note', '')).strip()
            ) 
            for _, row in df.iterrows()
        ]
        
        cursor.executemany("""
            INSERT INTO clienti (codice_cliente, ragione_sociale, referente, note)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(codice_cliente) DO UPDATE SET
                ragione_sociale = excluded.ragione_sociale,
                referente = excluded.referente,
                note = excluded.note;
        """, dati_clienti)

        conn.commit()
        return True, f"Importazione Clienti completata! Inseriti/Aggiornati {len(df)} record."
    except Exception as e:
        conn.rollback()
        return False, f"Errore durante l'importazione clienti: {e}"
    finally:
        conn.close()


def importa_distinta_base_df(df: pd.DataFrame) -> tuple[bool, str]:
    """Elabora il dataframe per l'inserimento delle Distinte Base (BOM)."""
    colonne_richieste = {"modello", "pn_componente", "quantita_richiesta"}
    if not colonne_richieste.issubset(set(df.columns)):
        return False, f"Colonne mancanti. Il file deve contenere: {', '.join(colonne_richieste)}"

    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN TRANSACTION;")
        
        dati_bom = [
            (
                str(row['modello']).strip(), 
                str(row['pn_componente']).strip(), 
                int(row['quantita_richiesta'])
            ) 
            for _, row in df.iterrows()
        ]
        
        cursor.executemany("""
            INSERT INTO distinta_base (modello, pn_componente, quantita_richiesta)
            VALUES (?, ?, ?)
            ON CONFLICT(modello, pn_componente) DO UPDATE SET
                quantita_richiesta = excluded.quantita_richiesta;
        """, dati_bom)

        conn.commit()
        return True, f"Importazione Distinte Base completata! Inseriti/Aggiornati {len(df)} componenti."
    except Exception as e:
        conn.rollback()
        return False, f"Errore durante l'importazione della Distinta Base: {e}"
    finally:
        conn.close()


def render_importazione_ui():
    st.title("📥 Importazione Massiva Dati (Excel / CSV)")
    st.write("Carica elenchi di Part Numbers, Clienti o Distinte Base da file Excel per popolare rapidamente il database.")

    tab1, tab2, tab3 = st.tabs(["📦 Anagrafica Part Numbers", "👥 Importa Clienti", "📋 Importa Distinta Base (BOM)"])

    # --- TAB 1: PART NUMBERS ---
    with tab1:
        st.subheader("Importa Anagrafica Articoli & Giacenze Iniziali")
        col_dl, col_up = st.columns([1, 2])
        
        with col_dl:
            st.markdown("##### 1. Scarica Template")
            template_bytes = genera_template_excel("part_numbers")
            st.download_button(
                label="📄 Scarica Template PN",
                data=template_bytes,
                file_name="template_part_numbers.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with col_up:
            st.markdown("##### 2. Carica File Compilato")
            uploaded_file = st.file_uploader("Scegli un file .xlsx o .csv", type=["xlsx", "csv"], key="up_pn")
            
            if uploaded_file is not None:
                try:
                    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                    st.write(f"Anteprima dati ({len(df)} righe):")
                    st.dataframe(df.head(5), use_container_width=True)

                    if st.button("🚀 Avvia Importazione Part Numbers", type="primary"):
                        with st.spinner("Importazione in corso..."):
                            ok, msg = importa_part_numbers_df(df)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                except Exception as e:
                    st.error(f"Impossibile leggere il file: {e}")

    # --- TAB 2: CLIENTI ---
    with tab2:
        st.subheader("Importa Anagrafica Clienti")
        col_dl, col_up = st.columns([1, 2])
        
        with col_dl:
            st.markdown("##### 1. Scarica Template")
            template_bytes = genera_template_excel("clienti")
            st.download_button(
                label="📄 Scarica Template Clienti",
                data=template_bytes,
                file_name="template_clienti.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with col_up:
            st.markdown("##### 2. Carica File Compilato")
            uploaded_file_cli = st.file_uploader("Scegli un file .xlsx o .csv", type=["xlsx", "csv"], key="up_cli")
            
            if uploaded_file_cli is not None:
                try:
                    df_cli = pd.read_csv(uploaded_file_cli) if uploaded_file_cli.name.endswith('.csv') else pd.read_excel(uploaded_file_cli)
                    st.write(f"Anteprima Clienti ({len(df_cli)} righe):")
                    st.dataframe(df_cli.head(5), use_container_width=True)

                    if st.button("🚀 Avvia Importazione Clienti", type="primary"):
                        with st.spinner("Importazione Clienti in corso..."):
                            ok, msg = importa_clienti_df(df_cli)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                except Exception as e:
                    st.error(f"Impossibile leggere il file: {e}")

    # --- TAB 3: DISTINTA BASE (BOM) ---
    with tab3:
        st.subheader("Importa Distinta Base (BOM Componenti)")
        col_dl, col_up = st.columns([1, 2])
        
        with col_dl:
            st.markdown("##### 1. Scarica Template")
            template_bytes = genera_template_excel("distinta_base")
            st.download_button(
                label="📄 Scarica Template Distinta Base",
                data=template_bytes,
                file_name="template_distinta_base.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with col_up:
            st.markdown("##### 2. Carica File Compilato")
            uploaded_file_bom = st.file_uploader("Scegli un file .xlsx o .csv", type=["xlsx", "csv"], key="up_bom")
            
            if uploaded_file_bom is not None:
                try:
                    df_bom = pd.read_csv(uploaded_file_bom) if uploaded_file_bom.name.endswith('.csv') else pd.read_excel(uploaded_file_bom)
                    st.write(f"Anteprima BOM ({len(df_bom)} righe):")
                    st.dataframe(df_bom.head(5), use_container_width=True)

                    if st.button("🚀 Avvia Importazione Distinta Base", type="primary"):
                        with st.spinner("Importazione Distinta Base in corso..."):
                            ok, msg = importa_distinta_base_df(df_bom)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                except Exception as e:
                    st.error(f"Impossibile leggere il file: {e}")
