import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_db_connection
from modules.pdf_generator import genera_pdf_etichetta

FASE_LISTA = [
    "Assemblaggio",
    "Collaudo Elettrico",
    "Programmazione Firmware",
    "Controllo Qualità",
    "Imballaggio",
    "Spedita"
]

def mappa_colore_fase(fase):
    colors = {
        "Assemblaggio": "🔵",
        "Collaudo Elettrico": "🟡",
        "Programmazione Firmware": "🟣",
        "Controllo Qualità": "🟠",
        "Imballaggio": "📦",
        "Spedita": "🟢"
    }
    return f"{colors.get(fase, '⚪')} {fase}"

def render_tabella_centraline(df_dati):
    """Funzione di supporto per formattare uniformemente le tabelle nei vari Tab."""
    if df_dati.empty:
        st.info("Nessuna centralina presente in questa fase.")
        return

    df_display = df_dati.copy()
    df_display['fase_attuale'] = df_display['fase_attuale'].apply(mappa_colore_fase)
    df_display.columns = ["Seriale", "Commessa", "Modello", "Stato / Fase", "Note", "Data Creazione"]

    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Seriale": st.column_config.TextColumn("Seriale Pezzo"),
            "Stato / Fase": st.column_config.TextColumn("Fase Attuale"),
            "Data Creazione": st.column_config.DatetimeColumn("Data Creazione", format="DD/MM/YYYY HH:mm")
        }
    )

def render():
    st.header("🔄 Avanzamento Fasi & Stato Centraline")
    st.markdown("---")

    utente_loggato = st.session_state.get("utente_loggato", {})
    nome_operatore = utente_loggato.get("nome_completo", "OPERATORE SCONOSCIUTO").upper()

    if "barcode_key_version" not in st.session_state:
        st.session_state["barcode_key_version"] = 0

    tab_cambio_fase, tab_riepilogo, tab_dettaglio = st.tabs([
        "⚡ Registrazione Cambio Fase", 
        "📊 Matrice & Riepilogo Fasi", 
        "📋 Dettaglio Produzione per Reparto"
    ])

    # ==========================================
    # TAB 1: REGISTRAZIONE RAPIDA CAMBIO FASE
    # ==========================================
    with tab_cambio_fase:
        st.subheader("⚡ Avanzamento Seriale in Lavorazione")

        conn = get_db_connection()
        centraline_wip = []
        map_dettagli = {}
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    TRIM(serial_centralina) as seriale_effettivo, 
                    fase_attuale, 
                    commessa_padre, 
                    tipologia, 
                    data_creazione 
                FROM centraline 
                WHERE fase_attuale != 'Spedita' OR fase_attuale IS NULL
                ORDER BY seriale_effettivo ASC
            """)
            rows = cursor.fetchall()
            
            for r in rows:
                ser_code = str(r['seriale_effettivo']).strip() if r['seriale_effettivo'] else ""
                if ser_code:
                    centraline_wip.append(ser_code)
                    map_dettagli[ser_code] = {
                        'fase': r['fase_attuale'] if r['fase_attuale'] else "Assemblaggio", 
                        'commessa': r['commessa_padre'],
                        'modello': r['tipologia'],
                        'data': r['data_creazione']
                    }
            conn.close()

        if not centraline_wip:
            st.info("ℹ️ Nessuna centralina attualmente in lavorazione (WIP). Tutte le centraline risultano spedite o non ne sono ancora state assemblate.")
        else:
            modalita_input = st.radio("Metodo Selezione Centralina:", ["📸 Scansione Barcode / Input Diretto", "📋 Selezione Manuale da Lista"], horizontal=True)

            seriale_selezionato = ""

            if modalita_input == "📸 Scansione Barcode / Input Diretto":
                input_key = f"input_barcode_scanner_{st.session_state['barcode_key_version']}"
                
                scanned_val = st.text_input(
                    "Incolla o Scansiona Barcode Seriale qui e premi INVIO:", 
                    key=input_key,
                    help="Posiziona il cursore qui e spara con il lettore barcode"
                ).strip()
                
                if scanned_val:
                    trovato = False
                    for key_seriale in map_dettagli.keys():
                        if key_seriale.upper() == scanned_val.upper():
                            seriale_selezionato = key_seriale
                            st.session_state["seriale_corrente_scansionato"] = key_seriale
                            trovato = True
                            break
                    
                    if not trovato and not st.session_state.get("stato_aggiornato_successo", False):
                        st.error(f"⚠️ Seriale **'{scanned_val}'** non trovato tra i pezzi attualmente in lavorazione (WIP). Verifica che la centralina sia stata assemblata.")
                elif "seriale_corrente_scansionato" in st.session_state:
                    if st.session_state["seriale_corrente_scansionato"] in map_dettagli:
                        seriale_selezionato = st.session_state["seriale_corrente_scansionato"]
            else:
                seriale_selezionato = st.selectbox(
                    "Seleziona Centralina (WIP)", 
                    options=[""] + centraline_wip,
                    help="Mostra solo le centraline non ancora spedite"
                )

            # Notifiche salvate in sessione
            if "stato_aggiornato_successo" in st.session_state:
                st.success(st.session_state["stato_aggiornato_successo"])
                del st.session_state["stato_aggiornato_successo"]
            
            if "commessa_chiusa_notifica" in st.session_state:
                st.balloons()
                st.warning(st.session_state["commessa_chiusa_notifica"])
                del st.session_state["commessa_chiusa_notifica"]

            if seriale_selezionato and seriale_selezionato in map_dettagli:
                info_s = map_dettagli[seriale_selezionato]
                fase_curr = info_s['fase']
                comm_curr = info_s['commessa']
                mod_curr = info_s['modello']

                st.info(f"📌 Centralina Selezionata: **{seriale_selezionato}** | Stato Attuale: **{fase_curr}** | Commessa: **{comm_curr}** | Modello: **{mod_curr}**")

                with st.form("form_avanzamento_fase", clear_on_submit=True):
                    col_fase, col_op = st.columns(2)

                    with col_fase:
                        idx_attuale = FASE_LISTA.index(fase_curr) if fase_curr in FASE_LISTA else 0
                        idx_default = min(idx_attuale + 1, len(FASE_LISTA) - 1)
                        
                        nuova_fase = st.selectbox("Nuova Fase Destinazione", options=FASE_LISTA, index=idx_default)
                    with col_op:
                        operatore_fase = st.text_input("Operatore", value=nome_operatore, disabled=True)

                    note_fase = st.text_input("Note / Esito Operazione (opzionale)", placeholder="Es. Superato test collaudo ok")

                    btn_submit = st.form_submit_button("🚀 Aggiorna Stato Centralina", type="primary", use_container_width=True)

                    if btn_submit:
                        conn = get_db_connection()
                        if conn:
                            try:
                                cursor = conn.cursor()
                                cursor.execute("BEGIN TRANSACTION;")

                                cursor.execute("SELECT * FROM centraline WHERE UPPER(TRIM(serial_centralina)) = UPPER(TRIM(?))", (seriale_selezionato,))
                                cent = cursor.fetchone()

                                if not cent:
                                    st.error(f"Centralina **{seriale_selezionato}** non trovata nel database.")
                                else:
                                    note_finali = note_fase if note_fase else cent['note']
                                    
                                    cursor.execute("""
                                        UPDATE centraline 
                                        SET fase_attuale = ?, note = ? 
                                        WHERE UPPER(TRIM(serial_centralina)) = UPPER(TRIM(?))
                                    """, (nuova_fase, note_finali, seriale_selezionato))

                                    cursor.execute("""
                                        INSERT INTO storico_fasi (serial_centralina, fase_destinazione, operatore)
                                        VALUES (?, ?, ?)
                                    """, (seriale_selezionato, nuova_fase, operatore_fase))

                                    # -------------------------------------------------------------
                                    # 🔒 CONTROLLO E CHIUSURA AUTOMATICA COMMESSA (SE SPEDITA)
                                    # -------------------------------------------------------------
                                    if nuova_fase == "Spedita" and comm_curr:
                                        # 1. Recupera la quantità totale richiesta dalla commessa
                                        cursor.execute("SELECT quantita_totale FROM commesse WHERE codice_commessa = ?", (comm_curr,))
                                        res_c = cursor.fetchone()
                                        qta_totale_richiesta = res_c['quantita_totale'] if res_c else 0

                                        # 2. Conta quante centraline risultano SPEDITE per questa commessa
                                        cursor.execute("""
                                            SELECT COUNT(*) as tot_spedite 
                                            FROM centraline 
                                            WHERE commessa_padre = ? AND fase_attuale = 'Spedita'
                                        """, (comm_curr,))
                                        res_s = cursor.fetchone()
                                        tot_spedite = res_s['tot_spedite'] if res_s else 0

                                        # 3. Se tutte le unità sono state spedite, imposta lo stato su 'Chiusa'
                                        if tot_spedite >= qta_totale_richiesta and qta_totale_richiesta > 0:
                                            cursor.execute("""
                                                UPDATE commesse 
                                                SET stato = 'Chiusa' 
                                                WHERE codice_commessa = ?
                                            """, (comm_curr,))
                                            
                                            st.session_state["commessa_chiusa_notifica"] = (
                                                f"🎉 **COMMESSA COMPLETATA & CHIUSA**: La commessa **{comm_curr}** "
                                                f"ha raggiunto il 100% delle spedizioni ({tot_spedite}/{qta_totale_richiesta} pz) "
                                                f"ed è stata archiviata automaticamente!"
                                            )

                                    conn.commit()

                                    # Salviamo il messaggio di successo in sessione prima del reset
                                    st.session_state["stato_aggiornato_successo"] = f"Centralina **{seriale_selezionato}** avanzata a **{nuova_fase}** da **{operatore_fase}**!"
                                    
                                    if "seriale_corrente_scansionato" in st.session_state:
                                        del st.session_state["seriale_corrente_scansionato"]
                                    
                                    st.session_state["barcode_key_version"] += 1

                                    st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"Errore durante l'aggiornamento (Rollback eseguito): {e}")
                            finally:
                                conn.close()

                # --- RISTAMPA RAPIDA ETICHETTA TERMICA ---
                with st.expander("🖨️ Ristampa Etichetta Termica per questo Seriale"):
                    raw_date = info_s.get('data', '')
                    d_str = raw_date[:10] if raw_date else datetime.now().strftime("%d/%m/%Y")
                    
                    pdf_bytes_ristampa = genera_pdf_etichetta(
                        seriale=seriale_selezionato,
                        commessa=comm_curr,
                        modello=mod_curr,
                        data_str=d_str
                    )
                    st.download_button(
                        label=f"🖨️ Scarica PDF Etichetta Ristampa [{seriale_selezionato}]",
                        data=pdf_bytes_ristampa,
                        file_name=f"ristampa_{seriale_selezionato}.pdf",
                        mime="application/pdf"
                    )

    # ==========================================
    # TAB 2: MATRICE & RIEPILOGO PIVOT
    # ==========================================
    with tab_riepilogo:
        st.subheader("📊 Riepilogo Pezzi per Fase e Tipologia")
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fase_attuale, tipologia, COUNT(*) as totale 
                FROM centraline 
                GROUP BY fase_attuale, tipologia
            """)
            dati_grezzi = cursor.fetchall()

            if dati_grezzi:
                df = pd.DataFrame([dict(d) for d in dati_grezzi])
                df_pivot = df.pivot(index='fase_attuale', columns='tipologia', values='totale').fillna(0).astype(int)
                df_pivot['TOTALE PEZZI'] = df_pivot.sum(axis=1)
                df_pivot.index.name = "Fase Operativa"
                st.dataframe(df_pivot, use_container_width=True)
            else:
                st.info("Nessuna centralina attualmente a sistema.")
            conn.close()

    # ==========================================
    # TAB 3: DETTAGLIO PRODUZIONE E REPARTI
    # ==========================================
    with tab_dettaglio:
        st.subheader("📋 Monitoraggio Dettagliato Produzione")

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT serial_centralina, commessa_padre, tipologia, fase_attuale, note, data_creazione 
                FROM centraline 
                ORDER BY data_creazione DESC
            """)
            tutte = cursor.fetchall()
            conn.close()

            if tutte:
                df_tutte = pd.DataFrame([dict(t) for t in tutte])

                st.markdown("##### 📈 Quantità Totali per Reparto")
                conteggi = df_tutte['fase_attuale'].value_counts().to_dict()
                
                col_m1, col_m2, col_m3, col_m4, col_m5, col_m6 = st.columns(6)
                col_m1.metric("🔵 Assemblaggio", conteggi.get("Assemblaggio", 0))
                col_m2.metric("🟡 Collaudo", conteggi.get("Collaudo Elettrico", 0))
                col_m3.metric("🟣 Firmware", conteggi.get("Programmazione Firmware", 0))
                col_m4.metric("🟠 Qualità", conteggi.get("Controllo Qualità", 0))
                col_m5.metric("📦 Imballaggio", conteggi.get("Imballaggio", 0))
                col_m6.metric("🟢 Spedite", conteggi.get("Spedita", 0))

                st.write("")

                tab_all, tab_ass, tab_coll, tab_prog, tab_qual, tab_imb, tab_sped = st.tabs([
                    "🌐 Tutte", 
                    "🔵 Assemblaggio", 
                    "🟡 Collaudo", 
                    "🟣 Firmware", 
                    "🟠 Qualità", 
                    "📦 Imballaggio", 
                    "🟢 Spedite"
                ])

                with tab_all:
                    render_tabella_centraline(df_tutte)

                with tab_ass:
                    df_f = df_tutte[df_tutte['fase_attuale'] == "Assemblaggio"]
                    render_tabella_centraline(df_f)

                with tab_coll:
                    df_f = df_tutte[df_tutte['fase_attuale'] == "Collaudo Elettrico"]
                    render_tabella_centraline(df_f)

                with tab_prog:
                    df_f = df_tutte[df_tutte['fase_attuale'] == "Programmazione Firmware"]
                    render_tabella_centraline(df_f)

                with tab_qual:
                    df_f = df_tutte[df_tutte['fase_attuale'] == "Controllo Qualità"]
                    render_tabella_centraline(df_f)

                with tab_imb:
                    df_f = df_tutte[df_tutte['fase_attuale'] == "Imballaggio"]
                    render_tabella_centraline(df_f)

                with tab_sped:
                    df_f = df_tutte[df_tutte['fase_attuale'] == "Spedita"]
                    render_tabella_centraline(df_f)

            else:
                st.info("Nessuna centralina registrata nel sistema.")
