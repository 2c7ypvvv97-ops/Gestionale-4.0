import os
import streamlit as st
import pandas as pd
from database import get_db_connection

def render():
    st.header("📋 Gestione Distinte Basi (BOM)")
    st.markdown("Gestisci la composizione dei modelli di centraline e delle sotto-schede componibili.")

    # Inizializza la chiave per il reset del file_uploader se non esiste
    if "bom_uploader_key" not in st.session_state:
        st.session_state["bom_uploader_key"] = 0

    # Controllo Ruolo Utente
    utente_loggato = st.session_state.get("utente_loggato", {})
    es_admin = utente_loggato.get("ruolo") == "Admin"

    tab_import, tab_view = st.tabs(["📥 Importa / Crea BOM", "🔍 Consulta e Gestisci BOM Presenti"])

    # ==========================================
    # TAB 1: IMPORTA O CREA NUOVA BOM
    # ==========================================
    with tab_import:
        st.subheader("1. Seleziona Tipologia BOM")
        tipo_bom = st.radio(
            "Cosa stai configurando?",
            ["Centralina Finale (BOM Padre)", "Sotto-Scheda Componente (BOM Figlia)"],
            horizontal=True
        )

        st.divider()
        st.subheader("2. Carica da File (Excel / CSV)")

        # Utilizziamo una key dinamica legata allo stato per resettare il file_uploader dopo l'import
        uploaded_file = st.file_uploader(
            "Carica File BOM (.xlsx, .xls, .csv)", 
            type=["xlsx", "xls", "csv"],
            key=f"uploader_bom_{st.session_state['bom_uploader_key']}"
        )

        if uploaded_file is not None:
            try:
                # Estrarre nome del modello dal nome del file (es: "CENTRALINA_XYZ.xlsx" -> "CENTRALINA_XYZ")
                nome_modello_da_filename = os.path.splitext(uploaded_file.name)[0].strip().upper()

                if uploaded_file.name.endswith('.csv'):
                    df_upload = pd.read_csv(uploaded_file)
                else:
                    df_upload = pd.read_excel(uploaded_file)

                st.success(f"📂 File **{uploaded_file.name}** letto con successo! ({len(df_upload)} righe trovate)")
                st.dataframe(df_upload.head(5), use_container_width=True, hide_index=True)

                st.markdown("##### ⚙️ Mappatura Dati e Colonne")

                # Opzione per definire la fonte del nome della centralina/modello
                fonte_modello = st.radio(
                    "Da dove prendere il Nome del Modello / Centralina?",
                    ["Nome del File Caricato", "Da una Colonna del File"],
                    horizontal=True
                )

                colonne = list(df_upload.columns)

                if fonte_modello == "Nome del File Caricato":
                    modello_finale = st.text_input(
                        "Codice Modello / Centralina estratto dal nome del file:",
                        value=nome_modello_da_filename
                    ).strip().upper()
                    col_modello = None
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        col_pn = st.selectbox("Colonna Part Number Componente", colonne, index=0 if len(colonne) > 0 else 0)
                    with c2:
                        col_qta = st.selectbox("Colonna Quantità Richiesta", colonne, index=1 if len(colonne) > 1 else 0)
                else:
                    modello_finale = None
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        col_modello = st.selectbox("Colonna Modello / Codice Scheda", colonne, index=0 if len(colonne) > 0 else 0)
                    with c2:
                        col_pn = st.selectbox("Colonna Part Number Componente", colonne, index=1 if len(colonne) > 1 else 0)
                    with c3:
                        col_qta = st.selectbox("Colonna Quantità Richiesta", colonne, index=2 if len(colonne) > 2 else 0)

                if st.button("🚀 Conferma e Importa File nel Database", type="primary", use_container_width=True):
                    if fonte_modello == "Nome del File Caricato" and not modello_finale:
                        st.error("Inserisci un nome valido per il Modello/Centralina.")
                    else:
                        conn = get_db_connection()
                        if conn:
                            try:
                                cursor = conn.cursor()
                                count_ins = 0

                                for _, row in df_upload.iterrows():
                                    # Determina il modello in base alla scelta dell'utente
                                    if fonte_modello == "Nome del File Caricato":
                                        mod = modello_finale
                                    else:
                                        mod = str(row[col_modello]).strip().upper()

                                    pn = str(row[col_pn]).strip().upper()

                                    try:
                                        qta = int(float(row[col_qta])) if pd.notnull(row[col_qta]) else 1
                                    except (ValueError, TypeError):
                                        qta = 1

                                    if mod and pn and mod != "NAN" and pn != "NAN" and qta > 0:
                                        # Registra in Part Numbers se assente
                                        cursor.execute("""
                                            INSERT OR IGNORE INTO part_numbers (pn_codice, descrizione, ubicazione)
                                            VALUES (?, ?, 'SCAFFALE-STD')
                                        """, (pn, f"Componente {pn}"))

                                        # Registra in Magazzino se assente
                                        cursor.execute("""
                                            INSERT OR IGNORE INTO magazzino_quantita (pn_codice, quantita_disponibile, ubicazione)
                                            VALUES (?, 0, 'SCAFFALE-STD')
                                        """, (pn,))

                                        # Salvataggio BOM
                                        if "Centralina Finale" in tipo_bom:
                                            cursor.execute("""
                                                INSERT OR REPLACE INTO distinte_basi (modello, pn_componente, quantita_richiesta)
                                                VALUES (?, ?, ?)
                                            """, (mod, pn, qta))
                                        else:
                                            cursor.execute("""
                                                INSERT OR REPLACE INTO distinte_sotto_schede (pn_sotto_scheda, pn_componente, quantita_richiesta)
                                                VALUES (?, ?, ?)
                                            """, (mod, pn, qta))

                                        count_ins += 1

                                conn.commit()
                                
                                # Incrementa la chiave per resettare automaticamente il file_uploader al reload
                                st.session_state["bom_uploader_key"] += 1
                                
                                st.success(f"🎉 Importazione completata con successo per il modello **'{modello_finale if modello_finale else 'selezionato'}'**! Registrate/Aggiornate **{count_ins}** righe.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Errore durante l'importazione: {e}")
                            finally:
                                conn.close()

            except Exception as e:
                st.error(f"Impossibile leggere il file: {e}")

        st.divider()
        st.subheader("3. Inserimento Manuale Singolo Componente")

        with st.form("form_manual_bom", clear_on_submit=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                input_modello = st.text_input("Codice Modello / Sotto-Scheda", placeholder="Es. MOD_POWER_2000").strip().upper()
            with f_col2:
                input_pn = st.text_input("Part Number Componente", placeholder="Es. RES_10K_0805").strip().upper()
            with f_col3:
                input_qta = st.number_input("Quantità Richiesta", min_value=1, value=1, step=1)

            submit_manual = st.form_submit_button("➕ Aggiungi Componente a BOM", type="primary")

            if submit_manual:
                if not input_modello or not input_pn:
                    st.error("I campi Modello e Part Number sono obbligatori.")
                else:
                    conn = get_db_connection()
                    if conn:
                        try:
                            cursor = conn.cursor()
                            # Assicura presenza del PN
                            cursor.execute("""
                                INSERT OR IGNORE INTO part_numbers (pn_codice, descrizione, ubicazione)
                                VALUES (?, ?, 'SCAFFALE-STD')
                            """, (input_pn, f"Componente {input_pn}"))

                            cursor.execute("""
                                INSERT OR IGNORE INTO magazzino_quantita (pn_codice, quantita_disponibile, ubicazione)
                                VALUES (?, 0, 'SCAFFALE-STD')
                            """, (input_pn,))

                            if "Centralina Finale" in tipo_bom:
                                cursor.execute("""
                                    INSERT OR REPLACE INTO distinte_basi (modello, pn_componente, quantita_richiesta)
                                    VALUES (?, ?, ?)
                                """, (input_modello, input_pn, input_qta))
                            else:
                                cursor.execute("""
                                    INSERT OR REPLACE INTO distinte_sotto_schede (pn_sotto_scheda, pn_componente, quantita_richiesta)
                                    VALUES (?, ?, ?)
                                """, (input_modello, input_pn, input_qta))

                            conn.commit()
                            st.success(f"✅ Aggiunto componente **{input_pn}** (x{input_qta}) al modello **{input_modello}**!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore nel salvataggio: {e}")
                        finally:
                            conn.close()

    # ==========================================
    # TAB 2: CONSULTAZIONE E GESTIONE BOM
    # ==========================================
    with tab_view:
        st.subheader("🔍 Distinte Basi Registrate nel Sistema")

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()

            c_type1, c_type2 = st.columns(2)

            # ----- CENTRALINE FINALI -----
            with c_type1:
                st.markdown("#### 📱 Centraline Finali (BOM Padre)")
                cursor.execute("SELECT DISTINCT modello FROM distinte_basi ORDER BY modello ASC")
                modelli_padre = [r['modello'] for r in cursor.fetchall()]

                if modelli_padre:
                    mod_scelto = st.selectbox("Seleziona Modello Centralina", modelli_padre, key="sel_mod_padre")

                    cursor.execute("""
                        SELECT id, pn_componente, quantita_richiesta 
                        FROM distinte_basi 
                        WHERE modello = ?
                        ORDER BY pn_componente ASC
                    """, (mod_scelto,))
                    righe = cursor.fetchall()

                    df_padre = pd.DataFrame([dict(r) for r in righe])
                    st.dataframe(
                        df_padre[['pn_componente', 'quantita_richiesta']].rename(columns={
                            'pn_componente': 'Part Number',
                            'quantita_richiesta': 'Quantità'
                        }), 
                        use_container_width=True, 
                        hide_index=True
                    )

                    # Pulsante di eliminazione visibile SOLO per Admin
                    if es_admin:
                        if st.button(f"🗑️ Elimina Intera BOM '{mod_scelto}'", key="del_bom_padre", type="secondary"):
                            cursor.execute("DELETE FROM distinte_basi WHERE modello = ?", (mod_scelto,))
                            conn.commit()
                            st.success(f"Eliminata BOM del modello {mod_scelto}")
                            st.rerun()
                else:
                    st.info("Nessuna BOM per centraline finali registrata.")

            # ----- SOTTO-SCHEDE -----
            with c_type2:
                st.markdown("#### 🧩 Sotto-Schede Componibili (BOM Figlia)")
                cursor.execute("SELECT DISTINCT pn_sotto_scheda FROM distinte_sotto_schede ORDER BY pn_sotto_scheda ASC")
                schede_figlie = [r['pn_sotto_scheda'] for r in cursor.fetchall()]

                if schede_figlie:
                    figlia_scelta = st.selectbox("Seleziona Sotto-Scheda", schede_figlie, key="sel_mod_figlia")

                    cursor.execute("""
                        SELECT id, pn_componente, quantita_richiesta 
                        FROM distinte_sotto_schede 
                        WHERE pn_sotto_scheda = ?
                        ORDER BY pn_componente ASC
                    """, (figlia_scelta,))
                    righe_f = cursor.fetchall()

                    df_figlia = pd.DataFrame([dict(r) for r in righe_f])
                    st.dataframe(
                        df_figlia[['pn_componente', 'quantita_richiesta']].rename(columns={
                            'pn_componente': 'Part Number',
                            'quantita_richiesta': 'Quantità'
                        }), 
                        use_container_width=True, 
                        hide_index=True
                    )

                    # Pulsante di eliminazione visibile SOLO per Admin
                    if es_admin:
                        if st.button(f"🗑️ Elimina Intera BOM Sotto-Scheda '{figlia_scelta}'", key="del_bom_figlia", type="secondary"):
                            cursor.execute("DELETE FROM distinte_sotto_schede WHERE pn_sotto_scheda = ?", (figlia_scelta,))
                            conn.commit()
                            st.success(f"Eliminata BOM della sotto-scheda {figlia_scelta}")
                            st.rerun()
                else:
                    st.info("Nessuna BOM per sotto-schede registrata.")

            conn.close()
