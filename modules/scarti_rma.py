import streamlit as st
import pandas as pd
import database as db
from modules import pdf_generator as pdf_gen

def render():
    db.init_db()
    utente_attuale = st.session_state.get("utente_loggato", {})
    st.title("🛡️ Gestione Qualità, Scarti & RMA")
    st.markdown("Monitoraggio difettosità, riparazioni da collaudo/reso cliente e gestione ricambi.")

    tab1, tab2, tab3 = st.tabs([
        "📥 Segnalazione Guasto / RMA", 
        "🔧 Scheda Riparazione & Ricambi", 
        "📋 Registro & Statistiche Qualità"
    ])

    # ==========================================
    # TAB 1: SEGNALAZIONE GUASTO / RMA
    # ==========================================
    with tab1:
        st.subheader("Registra Nuovo Pezzo Difettoso o Reso")
        
        with st.form("form_nuovo_rma", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                origine = st.selectbox(
                    "Origine Segnalazione *", 
                    ["Collaudo Interno", "Reso Cliente"],
                    help="Seleziona se il problema è emerso internamente o da cliente."
                )
                
                conn = db.get_db_connection()
                seriali = []
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT serial_centralina FROM centraline ORDER BY serial_centralina DESC")
                    seriali = [row['serial_centralina'] for row in cursor.fetchall()]
                    conn.close()
                
                serial_centralina = st.selectbox(
                    "Seriale Centralina (se presente)", 
                    [""] + seriali,
                    index=0
                )

            with col2:
                conn = db.get_db_connection()
                clienti_rows = []
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT codice_cliente, ragione_sociale FROM clienti ORDER BY ragione_sociale ASC")
                    clienti_rows = cursor.fetchall()
                    conn.close()
                
                mappa_clienti = {f"{c['codice_cliente']} - {c['ragione_sociale']}": c['codice_cliente'] for c in clienti_rows}
                
                cliente_sel = st.selectbox(
                    "Cliente (Obbligatorio per Reso Cliente)", 
                    ["Nessuno / Interno"] + list(mappa_clienti.keys())
                )
                codice_cliente = mappa_clienti.get(cliente_sel, None)

                gravita = st.select_slider(
                    "Gravità Guasto *",
                    options=["Bassa", "Media", "Alta", "Critica"],
                    value="Media"
                )

            sintomo_guasto = st.text_area("Sintomo del Guasto / Descrizione Anomalia *", placeholder="Es. Mancata accensione LED2, Cortocircuito su linea VCC...")

            btn_segnala = st.form_submit_button("📥 Registra Segnalazione RMA", use_container_width=True, type="primary")

            if btn_segnala:
                if not sintomo_guasto.strip():
                    st.error("⚠️ La descrizione del sintomo guasto è obbligatoria.")
                elif origine == "Reso Cliente" and not codice_cliente:
                    st.error("⚠️ Per i resi clienti è obbligatorio selezionare un cliente.")
                else:
                    operatore = utente_attuale.get('nome_completo', utente_attuale.get('username', 'OPERATORE'))
                    success, msg = db.inserisci_segnalazione_rma(
                        origine=origine,
                        serial_centralina=serial_centralina if serial_centralina else None,
                        codice_cliente=codice_cliente,
                        sintomo_guasto=sintomo_guasto,
                        gravita=gravita,
                        operatore=operatore
                    )
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    # ==========================================
    # TAB 2: SCHEDA RIPARAZIONE & RICAMBI
    # ==========================================
    with tab2:
        st.subheader("Riparazioni e Gestione Scheda Tecnico")
        
        # Includiamo sia gli aperti che i recenti per permettere la stampa rapida post-chiusura
        storico_tutti = db.get_storico_completo_rma()
        
        if not storico_tutti:
            st.info("🎉 Nessun RMA presente nel sistema.")
        else:
            # Filtro visivo per scegliere se lavorare sugli aperti o consultare i chiusi
            f_stato_tab2 = st.radio("Filtra schede visibili:", ["🛠️ In Lavorazione / Aperti", "✅ Tutti (Inclusi Riparati/Chiusi)"], horizontal=True)
            
            if "Aperti" in f_stato_tab2:
                lista_gestione = [r for r in storico_tutti if r['stato'] in ['In Attesa', 'In Lavorazione']]
            else:
                lista_gestione = storico_tutti

            if not lista_gestione:
                st.info("Nessuna scheda RMA trovata per il filtro selezionato.")
            else:
                opzioni_rma = {
                    f"{r['codice_rma']} | {r['origine']} | SN: {r['serial_centralina'] or 'N/A'} | [{r['stato']}]": r 
                    for r in lista_gestione
                }
                rma_sel_key = st.selectbox("Seleziona RMA da gestire o stampare:", list(opzioni_rma.keys()))
                rma_attivo = opzioni_rma[rma_sel_key]

                st.divider()

                col_info1, col_info2, col_info3 = st.columns(3)
                with col_info1:
                    st.write(f"**Codice RMA:** `{rma_attivo['codice_rma']}`")
                    st.write(f"**Origine:** {rma_attivo['origine']}")
                with col_info2:
                    st.write(f"**Seriale:** `{rma_attivo['serial_centralina'] or 'N/D'}`")
                    st.write(f"**Cliente:** {rma_attivo.get('ragione_sociale') or 'N/D'}")
                with col_info3:
                    st.write(f"**Gravità:** `{rma_attivo['gravita']}`")
                    st.write(f"**Stato attuale:** `{rma_attivo['stato']}`")
                
                st.info(f"🔍 **Sintomo Segnalato:** {rma_attivo['sintomo_guasto']}")

                # --- SUGGERITORE AUTOMATICO RIPARAZIONI PASSATE ---
                sintomo_txt = rma_attivo['sintomo_guasto'].strip()
                if sintomo_txt:
                    conn = db.get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT p.diagnosi, p.azioni_eseguite, r.sintomo_guasto
                            FROM rma_riparazioni p
                            JOIN rma_segnalazioni r ON p.rma_id = r.id
                            WHERE p.esito = 'Riparato' 
                            AND UPPER(r.sintomo_guasto) LIKE UPPER(?)
                            AND r.id != ?
                            ORDER BY p.data_intervento DESC LIMIT 3
                        """, (f"%{sintomo_txt[:10]}%", rma_attivo['id']))
                        suggerimenti = cursor.fetchall()
                        conn.close()

                        if suggerimenti:
                            with st.expander("💡 **Suggeritore Qualità: Trovate riparazioni passate per problemi simili!**", expanded=False):
                                for idx, sug in enumerate(suggerimenti, 1):
                                    st.markdown(f"**Caso #{idx}:** {sug['azioni_eseguite']} *(Diagnosi: {sug['diagnosi']})*")

                st.divider()

                col_left, col_right = st.columns([1, 1])

                with col_left:
                    st.markdown("### 📦 Scarico Ricambio da Magazzino")
                    conn = db.get_db_connection()
                    ricambi = []
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT p.pn_codice, p.descrizione, COALESCE(m.quantita_disponibile, 0) as quantita_disponibile 
                            FROM part_numbers p
                            LEFT JOIN magazzino_quantita m ON p.pn_codice = m.pn_codice
                            ORDER BY p.pn_codice ASC
                        """)
                        ricambi = cursor.fetchall()
                        conn.close()

                    mappa_pn = {f"{r['pn_codice']} - {r['descrizione'] or ''} (Giacenza: {r['quantita_disponibile']})": r['pn_codice'] for r in ricambi}

                    with st.form("form_ricambi"):
                        pn_ricambio_sel = st.selectbox("Seleziona Componente da Scaricare:", options=list(mappa_pn.keys()))
                        pn_codice = mappa_pn[pn_ricambio_sel] if pn_ricambio_sel else None
                        qta_ricambio = st.number_input("Quantità usata", min_value=1, value=1, step=1)
                        
                        btn_scarica_ricambio = st.form_submit_button("📉 Scarica Ricambio da Magazzino", type="primary")

                        if btn_scarica_ricambio:
                            if pn_codice:
                                tecnico = utente_attuale.get('nome_completo', utente_attuale.get('username', 'Tecnico'))
                                ok, msg = db.scarica_ricambio_rma(rma_attivo['id'], pn_codice, qta_ricambio, tecnico)
                                if ok:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)

                with col_right:
                    st.markdown("### 🛠️ Registra Intervento e Chiusura")
                    with st.form("form_intervento"):
                        diagnosi = st.text_area("Diagnosi Tecnica", placeholder="Dettaglio della causa riscontrata...")
                        azioni = st.text_area("Azioni Eseguite", placeholder="Es. Sostituito integrato U1, rifatte saldature...")
                        
                        esito = st.selectbox("Esito Intervento / Cambio Stato *", ["In Lavorazione", "Riparato", "Scartato"])
                        
                        btn_salva_intervento = st.form_submit_button("💾 Salva Intervento", type="primary")

                        if btn_salva_intervento:
                            if not diagnosi.strip() or not azioni.strip():
                                st.warning("⚠️ Compila sia la diagnosi che le azioni eseguite per storicizzare l'intervento.")
                            else:
                                tecnico = utente_attuale.get('nome_completo', utente_attuale.get('username', 'Tecnico'))
                                ok, msg = db.registra_intervento_rma(rma_attivo['id'], tecnico, diagnosi, azioni, esito)
                                if ok:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)

                st.divider()
                st.markdown("### 📄 Documentazione Ufficiale Cliente")

                interventi, ricambi_usati = db.get_dettagli_rma(rma_attivo['id'])

                pdf_bytes = pdf_gen.genera_pdf_report_rma(
                    rma_info=rma_attivo,
                    interventi=interventi,
                    ricambi=ricambi_usati,
                    nome_azienda="MY COMPANY SRL"
                )

                st.download_button(
                    label=f"🖨️ Scarica Report PDF ({rma_attivo['codice_rma']})",
                    data=pdf_bytes,
                    file_name=f"Report_{rma_attivo['codice_rma']}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    type="secondary"
                )

                st.divider()
                st.markdown("### 📜 Storico Lavorazioni su questo RMA")

                c_hist1, c_hist2 = st.columns(2)
                with c_hist1:
                    st.markdown("**Componenti Utilizzati:**")
                    if ricambi_usati:
                        df_ric = pd.DataFrame(ricambi_usati)[['pn_componente', 'quantita', 'tecnico', 'data_utilizzo']]
                        st.dataframe(df_ric, use_container_width=True, hide_index=True)
                    else:
                        st.caption("Nessun ricambio scaricato finora per questo RMA.")

                with c_hist2:
                    st.markdown("**Log Interventi Tecnico:**")
                    if interventi:
                        df_int = pd.DataFrame(interventi)[['tecnico', 'diagnosi', 'azioni_eseguite', 'esito', 'data_intervento']]
                        st.dataframe(df_int, use_container_width=True, hide_index=True)
                    else:
                        st.caption("Nessun intervento ancora registrato.")

    # ==========================================
    # TAB 3: REGISTRO & STATISTICHE QUALITÀ
    # ==========================================
    with tab3:
        st.subheader("Storico Completo RMA & Knowledge Base Guasti")
        
        storico = db.get_storico_completo_rma()
        
        if not storico:
            st.info("Nessun dato RMA presente nel sistema.")
        else:
            df_storico = pd.DataFrame(storico)

            df_storico['stato'] = df_storico['stato'].fillna('Inconoscibile')
            df_storico['origine'] = df_storico['origine'].fillna('Non Specificato')
            df_storico['gravita'] = df_storico['gravita'].fillna('Media')

            # --- MOTORE DI RICERCA KNOWLEDGE BASE ---
            st.markdown("### 💡 Knowledge Base Riparazioni (Ricerca Guasti Ricorrenti)")
            
            query_ricerca = st.text_input("🔍 Cerca per Sintomo, Diagnosi o Componente:", placeholder="Es. VCC, LED, corto, display, U2...")
            
            if query_ricerca.strip():
                risultati_kb = db.cerca_kb_soluzioni(query_ricerca)
                
                if not risultati_kb:
                    st.warning("⚠️ Nessuna riparazione passata registrata con questa chiave di ricerca.")
                else:
                    st.success(f"🎯 Trovati **{len(risultati_kb)}** interventi risolutivi nei record storici!")
                    
                    for idx, res in enumerate(risultati_kb, 1):
                        with st.expander(f"📌 #{idx} | Codice RMA: {res['codice_rma']} | SN: {res['serial_centralina'] or 'N/D'} ({res['data_intervento'][:10]})"):
                            st.markdown(f"**Sintomo segnalato:** {res['sintomo_guasto']}")
                            st.markdown(f"**Diagnosi:** {res['diagnosi']}")
                            st.markdown(f"**Azione Risolutiva:** `{res['azioni_eseguite']}`")
                            st.caption(f"Riparato da: {res['tecnico']}")

            st.divider()

            # --- SEZIONE STAMPA RAPIDA DA REGISTRO ---
            st.markdown("### 🖨️ Stampa Report PDF da Storico")
            col_sel_p, col_btn_p = st.columns([3, 1])
            with col_sel_p:
                mappa_storico = {f"{r['codice_rma']} | {r['ragione_sociale'] or 'Interno'} | SN: {r['serial_centralina'] or 'N/D'} | [{r['stato']}]": r for r in storico}
                rma_stampa_sel = st.selectbox("Seleziona RMA da Esportare in PDF:", list(mappa_storico.keys()), key="sb_stampa_tab3")
                rma_to_print = mappa_storico[rma_stampa_sel]
            
            with col_btn_p:
                st.write("") # Spaziatore verticale
                st.write("")
                ints_p, rics_p = db.get_dettagli_rma(rma_to_print['id'])
                pdf_p_bytes = pdf_gen.genera_pdf_report_rma(
                    rma_info=rma_to_print,
                    interventi=ints_p,
                    ricambi=rics_p,
                    nome_azienda="MY COMPANY SRL"
                )
                st.download_button(
                    label="📄 Scarica PDF",
                    data=pdf_p_bytes,
                    file_name=f"Report_{rma_to_print['codice_rma']}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            st.divider()

            st.markdown("#### 🔍 Filtri di Ricerca Registro")
            f_col1, f_col2, f_col3 = st.columns(3)
            
            with f_col1:
                filtro_stato = st.multiselect("Stato", options=sorted(df_storico['stato'].unique()), default=list(df_storico['stato'].unique()))
            with f_col2:
                filtro_origine = st.multiselect("Origine", options=sorted(df_storico['origine'].unique()), default=list(df_storico['origine'].unique()))
            with f_col3:
                filtro_gravita = st.multiselect("Gravità", options=sorted(df_storico['gravita'].unique()), default=list(df_storico['gravita'].unique()))

            df_filtrato = df_storico[
                (df_storico['stato'].isin(filtro_stato)) &
                (df_storico['origine'].isin(filtro_origine)) &
                (df_storico['gravita'].isin(filtro_gravita))
            ]

            st.divider()
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("Totale Segnalazioni", len(df_filtrato))
            kpi2.metric("Riparati con Successo", len(df_filtrato[df_filtrato['stato'] == 'Riparato']))
            kpi3.metric("Scartati", len(df_filtrato[df_filtrato['stato'] == 'Scartato']))
            
            tot_chiusi = len(df_filtrato[df_filtrato['stato'].isin(['Riparato', 'Scartato'])])
            tasso = (len(df_filtrato[df_filtrato['stato'] == 'Riparato']) / tot_chiusi * 100) if tot_chiusi > 0 else 0
            kpi4.metric("Tasso Riparabilità", f"{tasso:.1f}%")

            st.divider()
            st.markdown("### 📊 Tabella Registro Storico")
            
            colonne_visibili = [
                'codice_rma', 'data_segnalazione', 'origine', 'serial_centralina', 
                'ragione_sociale', 'gravita', 'stato', 'sintomo_guasto', 'operatore_segnalatore'
            ]
            
            colonne_presenti = [c for c in colonne_visibili if c in df_filtrato.columns]
            
            st.dataframe(
                df_filtrato[colonne_presenti].rename(columns={
                    'codice_rma': 'Codice RMA',
                    'data_segnalazione': 'Data',
                    'origine': 'Origine',
                    'serial_centralina': 'Seriale',
                    'ragione_sociale': 'Cliente',
                    'gravita': 'Gravità',
                    'stato': 'Stato',
                    'sintomo_guasto': 'Sintomo',
                    'operatore_segnalatore': 'Segnalato da'
                }),
                use_container_width=True,
                hide_index=True
            )

            st.divider()
            st.markdown("### 📈 Grafici Analisi Difettosità")
            
            chart_col1, chart_col2 = st.columns(2)
            
            with chart_col1:
                st.markdown("**Distribuzione per Stato**")
                st.bar_chart(df_filtrato['stato'].value_counts())
                
            with chart_col2:
                st.markdown("**Distribuzione per Gravità**")
                st.bar_chart(df_filtrato['gravita'].value_counts())
