import streamlit as st
import pandas as pd
import io
import database
import modules.pdf_generator as pdf_generator

def get_excel_download_button(df: pd.DataFrame, sheet_name: str = "Report") -> bytes:
    """Helper per convertire un DataFrame in un file Excel in memoria (BytesIO)."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    output.seek(0)
    return output.getvalue()

def render():
    st.title("📊 Modulo Reportistica & Export Dati")

    tab_magazzino, tab_avanzamento, tab_qualita, tab_pdf = st.tabs([
        "📦 Giacenze Magazzino",
        "⚙️ Avanzamento & Tempi Lavorazione",
        "🛡️ Registro Qualità & RMA",
        "📄 Certificato di Collaudo PDF"
    ])

    # ---------------------------------------------------------
    # TAB 1: GIACENZE MAGAZZINO & SOTTO-SCORTE
    # ---------------------------------------------------------
    with tab_magazzino:
        st.subheader("📦 Report Giacenze Magazzino")
        st.markdown("Monitoraggio giacenze con evidenza automatica delle sotto-scorte.")

        conn = database.get_db_connection()
        df_magazzino = pd.DataFrame()
        if conn:
            query_magazzino = """
                SELECT 
                    m.pn_codice AS 'Part Number',
                    p.descrizione AS 'Descrizione',
                    m.quantita_disponibile AS 'Giacenza Attuale',
                    m.ubicazione AS 'Ubicazione',
                    m.operatore AS 'Ultimo Operatore',
                    m.data_ultimo_carico AS 'Ultimo Carico'
                FROM magazzino_quantita m
                LEFT JOIN part_numbers p ON m.pn_codice = p.pn_codice
                ORDER BY m.quantita_disponibile ASC
            """
            df_magazzino = pd.read_sql_query(query_magazzino, conn)
            conn.close()

        if not df_magazzino.empty:
            soglia = st.number_input("Definisci Soglia Sotto-Scorta (pz):", min_value=0, value=5, step=1)
            df_magazzino['Sotto Scorta'] = df_magazzino['Giacenza Attuale'].apply(lambda x: "⚠️ Sotto Scorta" if x <= soglia else "OK")

            st.dataframe(df_magazzino, use_container_width=True, hide_index=True)

            col1, col2 = st.columns(2)
            with col1:
                csv_data = df_magazzino.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Scarica Report Magazzino (CSV)",
                    data=csv_data,
                    file_name="report_giacenze_magazzino.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with col2:
                excel_data = get_excel_download_button(df_magazzino, "Magazzino")
                st.download_button(
                    label="📗 Scarica Report Magazzino (Excel)",
                    data=excel_data,
                    file_name="report_giacenze_magazzino.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        else:
            st.info("Nessun dato presente in magazzino.")

    # ---------------------------------------------------------
    # TAB 2: STORICO AVANZAMENTO COMMESSE & TEMPI
    # ---------------------------------------------------------
    with tab_avanzamento:
        st.subheader("⚙️ Storico Avanzamento Commesse & Tempi Lavorazione")
        st.markdown("Tracciamento completo dei passaggi di fase, operatore e stime dei tempi di lavoro.")

        conn = database.get_db_connection()
        df_avanzamento = pd.DataFrame()
        if conn:
            query_avanzamento = """
                SELECT 
                    sf.id AS 'ID Registro',
                    sf.serial_centralina AS 'Seriale Centralina',
                    c.commessa_padre AS 'Commessa',
                    c.tipologia AS 'Modello',
                    sf.fase_destinazione AS 'Fase Avanzamento',
                    sf.operatore AS 'Operatore',
                    sf.data_ora AS 'Data e Ora'
                FROM storico_fasi sf
                LEFT JOIN centraline c ON sf.serial_centralina = c.serial_centralina
                ORDER BY sf.data_ora DESC
            """
            df_avanzamento = pd.read_sql_query(query_avanzamento, conn)
            conn.close()

        if not df_avanzamento.empty:
            st.dataframe(df_avanzamento, use_container_width=True, hide_index=True)

            col1, col2 = st.columns(2)
            with col1:
                csv_av = df_avanzamento.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Scarica Avanzamento Commesse (CSV)",
                    data=csv_av,
                    file_name="storico_avanzamento_commesse.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with col2:
                excel_av = get_excel_download_button(df_avanzamento, "Avanzamento")
                st.download_button(
                    label="📗 Scarica Avanzamento Commesse (Excel)",
                    data=excel_av,
                    file_name="storico_avanzamento_commesse.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        else:
            st.info("Nessun dato relativo all'avanzamento delle commesse.")

    # ---------------------------------------------------------
    # TAB 3: REGISTRO QUALITÀ & RMA
    # ---------------------------------------------------------
    with tab_qualita:
        st.subheader("🛡️ Registro Qualità & RMA")
        st.markdown("Analisi tassi di scarto, guasti e tracciabilità interventi di riparazione.")

        conn = database.get_db_connection()
        df_rma = pd.DataFrame()
        if conn:
            query_rma = """
                SELECT 
                    r.codice_rma AS 'Codice RMA',
                    r.data_segnalazione AS 'Data Segnalazione',
                    r.origine AS 'Origine',
                    r.serial_centralina AS 'Seriale Centralina',
                    cl.ragione_sociale AS 'Cliente',
                    r.sintomo_guasto AS 'Sintomo Guasto',
                    r.gravita AS 'Gravità',
                    r.stato AS 'Stato Finale',
                    r.operatore_segnalatore AS 'Operatore Segnalatore'
                FROM rma_segnalazioni r
                LEFT JOIN clienti cl ON r.codice_cliente = cl.codice_cliente
                ORDER BY r.data_segnalazione DESC
            """
            df_rma = pd.read_sql_query(query_rma, conn)
            conn.close()

        if not df_rma.empty:
            tot_rma = len(df_rma)
            scartati = len(df_rma[df_rma['Stato Finale'] == 'Scartato'])
            riparati = len(df_rma[df_rma['Stato Finale'] == 'Riparato'])

            c1, c2, c3 = st.columns(3)
            c1.metric("Totale RMA / Segnalazioni", tot_rma)
            c2.metric("Unità Riparate", riparati)
            c3.metric("Unità Scartate", scartati)

            st.dataframe(df_rma, use_container_width=True, hide_index=True)

            col1, col2 = st.columns(2)
            with col1:
                csv_rma = df_rma.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Scarica Registro Qualità (CSV)",
                    data=csv_rma,
                    file_name="registro_qualita_rma.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with col2:
                excel_rma = get_excel_download_button(df_rma, "Qualità RMA")
                st.download_button(
                    label="📗 Scarica Registro Qualità (Excel)",
                    data=excel_rma,
                    file_name="registro_qualita_rma.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        else:
            st.info("Nessuna segnalazione RMA o scarto registrata.")

    # ---------------------------------------------------------
    # TAB 4: SCHEDA / CERTIFICATO DI COLLAUDO PDF
    # ---------------------------------------------------------
    with tab_pdf:
        st.subheader("📄 Generazione Certificato di Collaudo PDF")
        st.markdown("Seleziona una centralina prodotta per scaricare il documento ufficiale di spedizione.")

        conn = database.get_db_connection()
        centraline = []
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.serial_centralina, c.commessa_padre, c.tipologia, c.fase_attuale, c.data_creazione, co.codice_cliente, cl.ragione_sociale
                FROM centraline c
                LEFT JOIN commesse co ON c.commessa_padre = co.codice_commessa
                LEFT JOIN clienti cl ON co.codice_cliente = cl.codice_cliente
                ORDER BY c.data_creazione DESC
            """)
            centraline = [dict(r) for r in cursor.fetchall()]
            conn.close()

        if centraline:
            opzioni_seriale = [f"{c['serial_centralina']} (Commessa: {c['commessa_padre']})" for c in centraline]
            scelta_seriale = st.selectbox("Seleziona Centralina per Seriale:", opzioni_seriale)
            
            seriale_selezionato = scelta_seriale.split(" ")[0]
            info_c = next((item for item in centraline if item["serial_centralina"] == seriale_selezionato), None)

            if info_c:
                st.info(f"**Modello:** {info_c['tipologia']} | **Cliente:** {info_c['ragione_sociale'] or 'N/D'} | **Fase Attuale:** {info_c['fase_attuale']}")

                if st.button("🛠️ Genera Certificato PDF", type="primary"):
                    conn = database.get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        
                        cursor.execute("SELECT * FROM componenti_centralina WHERE serial_centralina = ?", (seriale_selezionato,))
                        componenti = [dict(r) for r in cursor.fetchall()]

                        cursor.execute("SELECT * FROM storico_fasi WHERE serial_centralina = ? ORDER BY data_ora ASC", (seriale_selezionato,))
                        storico_fasi = [dict(r) for r in cursor.fetchall()]

                        cursor.execute("SELECT * FROM rma_segnalazioni WHERE serial_centralina = ?", (seriale_selezionato,))
                        rma_list = [dict(r) for r in cursor.fetchall()]

                        conn.close()

                        st.session_state["pdf_certificati"] = {
                            "seriale": seriale_selezionato,
                            "bytes": pdf_generator.genera_pdf_certificato_collaudo(
                                seriale=info_c['serial_centralina'],
                                commessa=info_c['commessa_padre'],
                                modello=info_c['tipologia'],
                                cliente=info_c['ragione_sociale'] or 'N/D',
                                data_creazione=str(info_c['data_creazione']),
                                fase_attuale=info_c['fase_attuale'],
                                componenti=componenti,
                                storico_fasi=storico_fasi,
                                segnalazioni_rma=rma_list
                            )
                        }

                if "pdf_certificati" in st.session_state and st.session_state["pdf_certificati"]["seriale"] == seriale_selezionato:
                    st.download_button(
                        label=f"💾 Scarica PDF Certificato Collaudo ({seriale_selezionato})",
                        data=st.session_state["pdf_certificati"]["bytes"],
                        file_name=f"Certificato_Collaudo_{seriale_selezionato}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
        else:
            st.warning("Nessuna centralina disponibile nel database per generare il certificato.")
