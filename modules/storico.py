import streamlit as st
import pandas as pd
from database import get_db_connection

def render():
    st.header("📜 Storico Audit Trail & Tracciabilità")
    st.markdown("Consulta l'albero di tracciabilità dei componenti, la cronologia delle lavorazioni e i collaudi per ciascun seriale.")
    st.markdown("---")

    seriale_ricerca = st.text_input("🔍 Cerca Tracciabilità per Seriale Centralina", placeholder="Es. K-00001").strip().upper()

    if seriale_ricerca:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            # 1. Dati Anagrafici Centralina
            cursor.execute("SELECT * FROM centraline WHERE serial_centralina = ?", (seriale_ricerca,))
            cent = cursor.fetchone()

            if cent:
                st.success(f"Trovato Seriale: **{cent['serial_centralina']}**")
                
                # KPI Anagrafici
                k1, k2, k3 = st.columns(3)
                k1.metric("Commessa Padre", cent['commessa_padre'] if cent['commessa_padre'] else "N/D")
                k2.metric("Fase Attuale", cent['fase_attuale'])
                k3.metric("Data Registrazione", cent['data_creazione'] if 'data_creazione' in cent.keys() else "N/D")

                st.markdown("---")
                col_comp, col_fasi = st.columns(2)

                # 2. Componenti Associati
                with col_comp:
                    st.subheader("🧩 Componenti Utilizzati")
                    cursor.execute("""
                        SELECT pn_codice, quantita_usata, data_associazione 
                        FROM componenti_centralina 
                        WHERE serial_centralina = ?
                        ORDER BY data_associazione ASC
                    """, (seriale_ricerca,))
                    comp = cursor.fetchall()
                    if comp:
                        df_comp = pd.DataFrame([dict(c) for c in comp])
                        df_comp.columns = ["Part Number", "Quantità Usata", "Data Assegnazione"]
                        st.dataframe(df_comp, use_container_width=True, hide_index=True)
                    else:
                        st.info("Nessun componente registrato per questo seriale.")

                # 3. Cronologia Fasi (Audit Trail)
                with col_fasi:
                    st.subheader("⏱️ Passaggi di Fase (Audit Trail)")
                    cursor.execute("""
                        SELECT fase_destinazione, operatore, data_ora 
                        FROM storico_fasi 
                        WHERE serial_centralina = ? 
                        ORDER BY data_ora ASC
                    """, (seriale_ricerca,))
                    fasi = cursor.fetchall()
                    if fasi:
                        df_fasi = pd.DataFrame([dict(f) for f in fasi])
                        df_fasi.columns = ["Fase Raggiunta", "Operatore", "Data / Ora"]
                        st.dataframe(df_fasi, use_container_width=True, hide_index=True)
                    else:
                        st.info("Nessuno storico fasi trovato.")

                # 4. Esito Collaudi (Se presenti)
                st.markdown("---")
                st.subheader("🧪 Registro Collaudi & Test")
                cursor.execute("""
                    SELECT esito, note, operatore, data_ora 
                    FROM storico_collaudi 
                    WHERE serial_centralina = ?
                    ORDER BY data_ora DESC
                """, (seriale_ricerca,))
                collaudi = cursor.fetchall()
                
                if collaudi:
                    df_coll = pd.DataFrame([dict(c) for c in collaudi])
                    df_coll.columns = ["Esito Test", "Note Collaudo", "Operatore", "Data / Ora"]
                    st.dataframe(df_coll, use_container_width=True, hide_index=True)
                else:
                    st.info("Nessun test di collaudo registrato per questa centralina.")

                # Export CSV Report
                if comp or fasi:
                    st.markdown("---")
                    combined_data = {
                        "Seriale": seriale_ricerca,
                        "Commessa": cent['commessa_padre'],
                        "Fase Attuale": cent['fase_attuale']
                    }
                    csv_export = pd.DataFrame([combined_data]).to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Scarica Scheda Tracciabilità (CSV)",
                        data=csv_export,
                        file_name=f"Tracciabilita_{seriale_ricerca}.csv",
                        mime="text/csv"
                    )

            else:
                st.warning(f"Nessun record trovato per il seriale **{seriale_ricerca}**.")
            conn.close()

    else:
        st.subheader("📜 Ultimi 20 Movimenti Registrati nel Sistema")
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT serial_centralina, fase_destinazione, operatore, data_ora 
                FROM storico_fasi 
                ORDER BY data_ora DESC 
                LIMIT 20
            """)
            ultimi = cursor.fetchall()
            if ultimi:
                df_ultimi = pd.DataFrame([dict(u) for u in ultimi])
                df_ultimi.columns = ["Seriale", "Fase / Azione", "Operatore", "Data / Ora"]
                st.dataframe(df_ultimi, use_container_width=True, hide_index=True)
            else:
                st.info("Nessun movimento recente registrato.")
            conn.close()
