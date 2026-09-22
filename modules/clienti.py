import streamlit as st
import pandas as pd
from database import get_db_connection

def render():
    st.header("👥 Anagrafica Clienti")
    st.markdown("Gestisci il registro dei clienti e le informazioni di contatto collegate alle commesse.")
    st.markdown("---")

    # Controllo Ruolo Utente
    utente_loggato = st.session_state.get("utente_loggato", {})
    es_admin = utente_loggato.get("ruolo") == "Admin"

    # Gestione dinamica dei Tab in base ai permessi
    titoli_tab = ["➕ Registra Nuovo Cliente", "📋 Registro Clienti"]
    if es_admin:
        titoli_tab.append("⚙️ Modifica / Elimina")

    tabs = st.tabs(titoli_tab)
    tab_registra = tabs[0]
    tab_elenco = tabs[1]

    # ==========================================
    # TAB 1: REGISTRAZIONE NUOVO CLIENTE
    # ==========================================
    with tab_registra:
        st.subheader("Inserisci Dati Anagrafici")
        with st.form("form_nuovo_cliente", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                cod_cliente = st.text_input("Codice Cliente / P.IVA *", placeholder="Es. CLI-001 o IT12345678901").strip().upper()
                rag_sociale = st.text_input("Ragione Sociale / Nome Azienda *", placeholder="Es. Acme S.r.l.").strip()
            with col2:
                referente = st.text_input("Referente / Contatto", placeholder="Es. Ing. Mario Rossi").strip()
                email_tel = st.text_input("Email / Telefono", placeholder="Es. ordini@acme.it - 02 123456").strip()

            note_cli = st.text_area("Note Commerciali / Indirizzo Spedizione", placeholder="Es. Consegna presso stabilimento B, orari 8-12").strip()

            if st.form_submit_button("💾 Salva Cliente in Anagrafica", type="primary", use_container_width=True):
                if not cod_cliente or not rag_sociale:
                    st.error("I campi Codice Cliente e Ragione Sociale sono obbligatori.")
                else:
                    conn = get_db_connection()
                    if conn:
                        try:
                            cursor = conn.cursor()
                            
                            # Composizione note pulita
                            note_finali = f"Contatti: {email_tel} | Note: {note_cli}".strip(" |") if email_tel or note_cli else ""

                            cursor.execute("""
                                INSERT INTO clienti (codice_cliente, ragione_sociale, referente, note)
                                VALUES (?, ?, ?, ?)
                            """, (cod_cliente, rag_sociale, referente, note_finali))
                            conn.commit()
                            st.success(f"✅ Cliente **{rag_sociale}** ({cod_cliente}) salvato con successo!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore durante il salvataggio (il codice cliente potrebbe già esistere): {e}")
                        finally:
                            conn.close()

    # ==========================================
    # TAB 2: ELENCO E RICERCA CLIENTE
    # ==========================================
    with tab_elenco:
        st.subheader("📋 Registro Clienti Attivi")
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    codice_cliente AS 'Codice Cliente',
                    ragione_sociale AS 'Ragione Sociale',
                    referente AS 'Referente',
                    note AS 'Contatti e Note',
                    data_creazione AS 'Data Registrazione'
                FROM clienti
                ORDER BY ragione_sociale ASC
            """)
            rows = cursor.fetchall()
            conn.close()

            if rows:
                df_clienti = pd.DataFrame([dict(r) for r in rows])
                
                # Barra di ricerca rapida
                search_query = st.text_input("🔍 Cerca per Nome o Codice:", placeholder="Digita per filtrare...").strip().lower()
                if search_query:
                    df_clienti = df_clienti[
                        df_clienti["Codice Cliente"].str.lower().str.contains(search_query, na=False) | 
                        df_clienti["Ragione Sociale"].str.lower().str.contains(search_query, na=False)
                    ]

                st.dataframe(df_clienti, use_container_width=True, hide_index=True)
            else:
                st.info("Nessun cliente presente in anagrafica.")

    # ==========================================
    # TAB 3: MODIFICA / ELIMINAZIONE (SOLO ADMIN)
    # ==========================================
    if es_admin:
        tab_gestisci = tabs[2]
        with tab_gestisci:
            st.subheader("⚙️ Modifica o Rimuovi Cliente")
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT codice_cliente, ragione_sociale FROM clienti ORDER BY ragione_sociale ASC")
                list_cli = cursor.fetchall()
                conn.close()

                if list_cli:
                    options = [f"{r['codice_cliente']} - {r['ragione_sociale']}" for r in list_cli]
                    cli_scelto = st.selectbox("Seleziona Cliente:", options)
                    cod_scelto = cli_scelto.split(" - ")[0]

                    st.markdown("---")
                    col_del1, col_del2 = st.columns([3, 1])
                    with col_del1:
                        check_del = st.checkbox(f"Confermo di voler eliminare permanentemente il cliente {cli_scelto}")
                    with col_del2:
                        if st.button("🗑️ Elimina Cliente", type="primary"):
                            if not check_del:
                                st.error("Spunta la casella di conferma.")
                            else:
                                conn = get_db_connection()
                                if conn:
                                    try:
                                        cursor = conn.cursor()
                                        cursor.execute("DELETE FROM clienti WHERE codice_cliente = ?", (cod_scelto,))
                                        conn.commit()
                                        st.success("Cliente rimosso correttamente.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Impossibile eliminare il cliente. Verificare che non ci siano commesse o RMA collegate. Errore: {e}")
                                    finally:
                                        conn.close()
                else:
                    st.info("Nessun cliente da gestire.")
