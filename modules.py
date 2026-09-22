import streamlit as st
import pandas as pd
from database import get_db_connection

def render():
    st.header("📊 Monitor Produzione & Gestione Commesse")
    st.markdown("---")

    # SECTION 1: Attivazione Nuova Commessa
    with st.expander("➕ Attiva Nuova Commessa", expanded=True):
        conn = get_db_connection()
        tipologie_disponibili = []
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tipologia FROM config_tipologie")
            tipologie_disponibili = [r['tipologia'] for r in cursor.fetchall()]
            conn.close()

        with st.form("form_nuova_commessa", clear_on_submit=True):
            col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
            
            with col1:
                cod_commessa = st.text_input("Codice Commessa").strip().upper()
            with col2:
                tipo_sel = st.selectbox("Tipologia Centralina", options=tipologie_disponibili if tipologie_disponibili else ["K", "J"])
            with col3:
                qty_target = st.number_input("Quantità Target", min_value=1, value=10, step=1)
            with col4:
                num_start = st.number_input("Num. Partenza Seriale", min_value=1, value=1, step=1)

            submit = st.form_submit_button("🚀 Salva e Attiva Commessa", use_container_width=True)

            if submit:
                if not cod_commessa:
                    st.error("Il codice commessa è obbligatorio.")
                else:
                    conn = get_db_connection()
                    if conn:
                        try:
                            cursor = conn.cursor()
                            cursor.execute("INSERT OR IGNORE INTO config_tipologie (tipologia, numero_partenza) VALUES (?, ?)", (tipo_sel, num_start))
                            cursor.execute("INSERT INTO commesse (codice_commessa, tipologia, quantita_massima) VALUES (?, ?, ?)", (cod_commessa, tipo_sel, qty_target))
                            conn.commit()
                            st.success(f"Commessa **{cod_commessa}** attivata con successo!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore durante il salvataggio: {e}")
                        finally:
                            conn.close()

    # SECTION 2: Monitor Avanzamento Commesse
    st.subheader("📈 Stato Avanzamento Commesse")
    
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM commesse ORDER BY data_creazione DESC")
        commesse = cursor.fetchall()
        
        dati_monitor = []
        for c in commesse:
            cod = c['codice_commessa']
            tipo = c['tipologia']
            target = c['quantita_massima']

            cursor.execute("SELECT COUNT(*) FROM centraline WHERE commessa_padre = ? AND fase_attuale = 'Spedita'", (cod,))
            spedite = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM centraline WHERE commessa_padre = ? AND fase_attuale != 'Spedita'", (cod,))
            wip = cursor.fetchone()[0]

            mancanti = max(0, target - spedite)

            dati_monitor.append({
                "Cod. Commessa": cod,
                "Tipologia": tipo,
                "Target": target,
                "WIP (In Lavorazione)": wip,
                "Spedite": spedite,
                "Mancanti": mancanti
            })

        if dati_monitor:
            df_monitor = pd.DataFrame(dati_monitor)
            st.dataframe(df_monitor, use_container_width=True, hide_index=True)
            
            # Selezione Commessa per dettaglio pezzi o eliminazione
            commesse_lista = [d["Cod. Commessa"] for d in dati_monitor]
            commessa_selezionata = st.selectbox("Seleziona una Commessa per vederne i pezzi o gestirla:", options=["-- Seleziona --"] + commesse_lista)

            if commessa_selezionata != "-- Seleziona --":
                st.markdown(f"#### 🔍 Pezzi attivi associati alla commessa: **{commessa_selezionata}**")
                cursor.execute("""
                    SELECT serial_centralina, fase_attuale, note, data_creazione 
                    FROM centraline 
                    WHERE commessa_padre = ? 
                    ORDER BY data_creazione DESC
                """, (commessa_selezionata,))
                pezzi = cursor.fetchall()

                if pezzi:
                    df_pezzi = pd.DataFrame([dict(p) for p in pezzi])
                    st.dataframe(df_pezzi, use_container_width=True, hide_index=True)
                else:
                    st.info("Nessuna centralina ancora generata su questa commessa.")

                # Gestione eliminazione commessa
                col_del1, col_del2 = st.columns([3, 1])
                with col_del2:
                    if st.button(f"🗑️ Elimina Commessa {commessa_selezionata}", type="secondary", use_container_width=True):
                        try:
                            cursor.execute("DELETE FROM componenti_centralina WHERE serial_centralina IN (SELECT serial_centralina FROM centraline WHERE commessa_padre = ?)", (commessa_selezionata,))
                            cursor.execute("DELETE FROM storico_fasi WHERE serial_centralina IN (SELECT serial_centralina FROM centraline WHERE commessa_padre = ?)", (commessa_selezionata,))
                            cursor.execute("DELETE FROM centraline WHERE commessa_padre = ?", (commessa_selezionata,))
                            cursor.execute("DELETE FROM magazzino_quantita WHERE codice_commessa = ?", (commessa_selezionata,))
                            cursor.execute("DELETE FROM commesse WHERE codice_commessa = ?", (commessa_selezionata,))
                            conn.commit()
                            st.warning(f"Commessa {commessa_selezionata} e tutti i suoi dati correlati sono stati eliminati.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore durante l'eliminazione: {e}")
        else:
            st.info("Nessuna commessa attiva nel sistema.")
            
        conn.close()
