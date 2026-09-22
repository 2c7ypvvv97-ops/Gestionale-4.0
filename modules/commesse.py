import streamlit as st
import pandas as pd
from database import get_db_connection

def render():
    st.header("📊 Gestione Commesse e Monitor Produzione")
    st.markdown("---")

    # Controllo Ruolo Utente
    utente_loggato = st.session_state.get("utente_loggato", {})
    es_admin = utente_loggato.get("ruolo") == "Admin"

    # Definizione dinamica dei Tab
    titoli_tab = ["📋 Stato Avanzamento Commesse", "➕ Apri Nuova Commessa"]
    if es_admin:
        titoli_tab.append("🔧 Gestione Admin & Chiusure")

    tabs = st.tabs(titoli_tab)
    tab_elenco = tabs[0]
    tab_nuova = tabs[1]

    # Caricamento dinamico Clienti e Modelli BOM
    lista_opzioni_clienti = ["NESSUN CLIENTE"]
    list_modelli_bom = []
    
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        
        # Carica i clienti dal DB
        cursor.execute("SELECT codice_cliente, ragione_sociale FROM clienti ORDER BY ragione_sociale ASC")
        clienti_db = cursor.fetchall()
        for r in clienti_db:
            lista_opzioni_clienti.append(f"{r['codice_cliente']} | {r['ragione_sociale']}")
        
        # Carica i modelli da distinte basi
        cursor.execute("SELECT DISTINCT modello FROM distinte_basi ORDER BY modello ASC")
        list_modelli_bom = [r['modello'] for r in cursor.fetchall()]
        
        conn.close()

    # ==========================================
    # TAB 1: TABELLA STATO COMMESSE
    # ==========================================
    with tab_elenco:
        st.subheader("📋 Dashboard & Avanzamento Commesse")
        conn = get_db_connection()
        lista_commesse_esistenti = []
        
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    c.codice_commessa,
                    COALESCE(cli.ragione_sociale, 'N/D') as cliente,
                    COALESCE(c.modello_centralina, 'STD') as modello_centralina,
                    COALESCE(c.quantita_totale, 1) as quantita_totale,
                    COALESCE(c.quantita_originale, c.quantita_totale, 1) as quantita_originale,
                    COALESCE(c.motivo_modifica_qta, '') as motivo_modifica_qta,
                    COALESCE(c.stato, 'Aperta') as stato,
                    c.data_creazione,
                    (SELECT COUNT(*) FROM centraline WHERE commessa_padre = c.codice_commessa) as pezzi_effettivi
                FROM commesse c
                LEFT JOIN clienti cli ON c.codice_cliente = cli.codice_cliente
                ORDER BY c.data_creazione DESC
            """)
            dati_commesse = cursor.fetchall()

            if dati_commesse:
                df_comm = pd.DataFrame([dict(row) for row in dati_commesse])
                lista_commesse_esistenti = df_comm["codice_commessa"].tolist()

                # KPI Top Bar
                col_k1, col_k2, col_k3 = st.columns(3)
                col_k1.metric("Totale Commesse", len(df_comm))
                col_k2.metric("Commesse Aperte", len(df_comm[df_comm['stato'] == 'Aperta']))
                col_k3.metric("Pezzi Totali in Ordine", int(df_comm['quantita_totale'].sum()))

                st.write("")

                def formatta_quantita(row):
                    qta_target = row['quantita_totale']
                    qta_orig = row['quantita_originale']
                    qta_effettiva = row['pezzi_effettivi']
                    motivo = row['motivo_modifica_qta']

                    # Lo sbarrato compare SOLO se la quantità target è stata modificata rispetto all'originale
                    if qta_orig and qta_target != qta_orig:
                        tooltip_motivo = f" title='Motivo: {motivo}'" if motivo else ""
                        return (
                            f"<del style='color:#ff4b4b; font-weight:bold;'{tooltip_motivo}>{qta_orig} pz</del> "
                            f"&nbsp;➡️&nbsp;<b style='color:#00c853;'>{qta_target} pz</b> ({qta_effettiva} prodotti)"
                        )
                    else:
                        return f"<b>{qta_target} pz</b> ({qta_effettiva} prodotti)"

                df_comm['Q.tà Target / Effettiva'] = df_comm.apply(formatta_quantita, axis=1)

                df_display = df_comm[[
                    "codice_commessa", "cliente", "modello_centralina", 
                    "Q.tà Target / Effettiva", "stato", "data_creazione"
                ]].copy()

                df_display.columns = ["Codice Commessa", "Cliente", "Modello Centralina", "Q.tà Target / Effettiva", "Stato", "Data Apertura"]

                style_table = """
                <style>
                    .custom-table {
                        width: 100%; 
                        border-collapse: collapse; 
                        font-family: sans-serif; 
                        margin-bottom: 20px; 
                        color: var(--text-color, inherit);
                    }
                    .custom-table th {
                        background-color: rgba(128, 128, 128, 0.15); 
                        color: var(--text-color, inherit); 
                        text-align: left; 
                        padding: 10px; 
                        font-size: 14px; 
                        border-bottom: 2px solid rgba(128, 128, 128, 0.3);
                    }
                    .custom-table td {
                        padding: 10px; 
                        border-bottom: 1px solid rgba(128, 128, 128, 0.2); 
                        font-size: 14px;
                        color: var(--text-color, inherit);
                    }
                </style>
                """

                html_table = df_display.to_html(classes="custom-table", escape=False, index=False)

                if hasattr(st, "html"):
                    st.html(style_table + html_table)
                else:
                    st.markdown(style_table + html_table, unsafe_allow_html=True)

            else:
                st.info("Nessuna commessa presente nel sistema.")
            conn.close()

    # ==========================================
    # TAB 2: CREAZIONE NUOVA COMMESSA
    # ==========================================
    with tab_nuova:
        st.subheader("➕ Apertura Nuova Commessa di Produzione")
        with st.form("form_nuova_commessa", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)

            with col1:
                cod_commessa = st.text_input("Codice Commessa *", placeholder="Es. C2026-001").strip().upper()
            with col2:
                cliente_sel = st.selectbox("Cliente Associato", options=lista_opzioni_clienti)
            with col3:
                if list_modelli_bom:
                    modello_c = st.selectbox("Modello Centralina (da BOM) *", list_modelli_bom)
                else:
                    modello_c = st.text_input("Modello Centralina Finale *", placeholder="Es. MOD_PWR_2000").strip().upper()

            qta_target = st.number_input("Quantità Totale da Produrre (pz)", min_value=1, value=10, step=1)
            btn_salva = st.form_submit_button("🚀 Salva e Apri Commessa", type="primary", use_container_width=True)

            if btn_salva:
                if not cod_commessa or not modello_c:
                    st.error("Codice Commessa e Modello sono campi obbligatori.")
                else:
                    cod_cli_db = None
                    if cliente_sel and cliente_sel != "NESSUN CLIENTE":
                        cod_cli_db = cliente_sel.split(" | ")[0].strip()

                    conn = get_db_connection()
                    if conn:
                        try:
                            cursor = conn.cursor()
                            
                            if cod_cli_db:
                                cursor.execute("SELECT codice_cliente FROM clienti WHERE codice_cliente = ?", (cod_cli_db,))
                                if not cursor.fetchone():
                                    cod_cli_db = None

                            cursor.execute("""
                                INSERT INTO commesse (
                                    codice_commessa, 
                                    codice_cliente, 
                                    modello_centralina, 
                                    quantita_totale,
                                    quantita_originale, 
                                    stato
                                )
                                VALUES (?, ?, ?, ?, ?, 'Aperta')
                            """, (cod_commessa, cod_cli_db, modello_c, qta_target, qta_target))
                            
                            conn.commit()
                            st.success(f"Commessa **{cod_commessa}** aperta correttamente!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore durante il salvataggio: {e}")
                        finally:
                            conn.close()

    # ==========================================
    # TAB 3: GESTIONE ED ELIMINAZIONE (SOLO ADMIN)
    # ==========================================
    if es_admin:
        tab_elimina = tabs[2]
        with tab_elimina:
            st.subheader("🔧 Gestione Avanzata, Chiusure & Modifiche Commesse")
            st.markdown("---")

            st.markdown("### 🔒 Chiusura / Modifica Quantità Commessa")
            
            if not lista_commesse_esistenti:
                st.info("Nessuna commessa presente nel sistema.")
            else:
                commessa_chiusura = st.selectbox("Seleziona Commessa da Modificare/Chiudere:", lista_commesse_esistenti, key="sel_commessa_chiusura")

                qta_target_orig = 0
                pezzi_attuali = 0
                stato_attuale = "Aperta"
                
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COALESCE(quantita_totale, 1) as qta, stato FROM commesse WHERE codice_commessa = ?", (commessa_chiusura,))
                    row_c = cursor.fetchone()
                    if row_c:
                        qta_target_orig = row_c['qta']
                        stato_attuale = row_c['stato']

                    cursor.execute("SELECT COUNT(*) FROM centraline WHERE commessa_padre = ?", (commessa_chiusura,))
                    pezzi_attuali = cursor.fetchone()[0]
                    conn.close()

                with st.form("form_chiusura_commessa"):
                    col_ch1, col_ch2, col_ch3 = st.columns(3)
                    
                    idx_st = ["Aperta", "Chiusa Parzialmente", "Saldata", "Chiusa", "Annullata"].index(stato_attuale) if stato_attuale in ["Aperta", "Chiusa Parzialmente", "Saldata", "Chiusa", "Annullata"] else 0
                    
                    with col_ch1:
                        nuovo_stato = st.selectbox("Stato Commessa:", ["Aperta", "Chiusa Parzialmente", "Saldata", "Chiusa", "Annullata"], index=idx_st)
                    with col_ch2:
                        st.text_input("Pezzi Attualmente Prodotti", value=f"{pezzi_attuali} pz", disabled=True)
                    with col_ch3:
                        qta_effettiva = st.number_input("Nuova Quantità Target (pz) *", min_value=1, value=qta_target_orig, step=1)

                    motivo_modifica = st.text_input(
                        "Motivo Modifica Quantità (obbligatorio se la quantità varia)", 
                        placeholder="Es. Richiesta cliente riduzione lotto / Modifica d'ordine"
                    ).strip()

                    btn_salda = st.form_submit_button("💾 Salva Modifiche Commessa", type="primary", use_container_width=True)

                    if btn_salda:
                        if qta_effettiva != qta_target_orig and not motivo_modifica:
                            st.error("⚠️ Per modificare la quantità di una commessa è OBBLIGATORIO specificare il motivo!")
                        else:
                            conn = get_db_connection()
                            if conn:
                                try:
                                    cursor = conn.cursor()
                                    
                                    if qta_effettiva != qta_target_orig:
                                        cursor.execute("""
                                            UPDATE commesse 
                                            SET stato = ?, quantita_totale = ?, motivo_modifica_qta = ?
                                            WHERE codice_commessa = ?
                                        """, (nuovo_stato, qta_effettiva, motivo_modifica, commessa_chiusura))
                                    else:
                                        cursor.execute("""
                                            UPDATE commesse 
                                            SET stato = ?
                                            WHERE codice_commessa = ?
                                        """, (nuovo_stato, commessa_chiusura))

                                    conn.commit()
                                    st.success(f"Commessa **{commessa_chiusura}** aggiornata con successo!")
                                    st.rerun()
                                except Exception as e:
                                    conn.rollback()
                                    st.error(f"Errore durante l'aggiornamento: {e}")
                                finally:
                                    conn.close()

            st.markdown("---")
            st.markdown("### 🗑️ Cancellazione Intera Commessa")
            
            if lista_commesse_esistenti:
                st.warning("⚠️ L'eliminazione di una commessa è un'operazione irreversibile.")
                with st.form("form_elimina_commessa"):
                    col_del1, col_del2 = st.columns([2, 1])
                    with col_del1:
                        commessa_da_eliminare = st.selectbox("Seleziona la Commessa da Eliminare:", lista_commesse_esistenti, key="sel_commessa_del")
                    with col_del2:
                        conferma_check = st.checkbox("Confermo l'eliminazione commessa")

                    btn_elimina = st.form_submit_button("🗑️ Elimina Definitivamente Commessa", type="primary", use_container_width=True)

                    if btn_elimina:
                        if not conferma_check:
                            st.error("Devi spuntare la casella 'Confermo l'eliminazione commessa' per procedere.")
                        else:
                            conn = get_db_connection()
                            if conn:
                                try:
                                    cursor = conn.cursor()
                                    cursor.execute("DELETE FROM commesse WHERE codice_commessa = ?", (commessa_da_eliminare,))
                                    conn.commit()
                                    st.success(f"Commessa **{commessa_da_eliminare}** eliminata con successo!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Impossibile eliminare la commessa: {e}")
                                finally:
                                    conn.close()
