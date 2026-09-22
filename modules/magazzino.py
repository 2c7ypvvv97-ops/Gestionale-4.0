import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import get_db_connection
from modules.pdf_generator import genera_pdf_mancanti


# ==========================================
# FUNZIONE DI SUPPORTO PER LA FATTIBILITÀ
# ==========================================
def calcola_fattibilita_dettagliata(modello_selezionato, qta_da_produrre):
    """
    Calcola la fattibilità di produzione e restituisce:
    - min_pezzi: quanti pezzi totali si possono produrre subito
    - tabella_dettagli: lista con il calcolo dei mancanti per ciascun componente
    """
    conn = get_db_connection()
    dettagli = []
    min_pezzi = 0
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    d.modello,
                    d.pn_componente,
                    d.quantita_richiesta,
                    COALESCE(mq.quantita_disponibile, 0) AS giacenza
                FROM distinte_basi d
                LEFT JOIN magazzino_quantita mq ON d.pn_componente = mq.pn_codice
                WHERE d.modello = ?
                ORDER BY d.pn_componente ASC
            """, (modello_selezionato,))
            rows = cursor.fetchall()
            
            if rows:
                costruibili = []
                for r in rows:
                    req = r['quantita_richiesta']
                    disp = r['giacenza']
                    fab_totale = req * qta_da_produrre
                    mancanti = max(0, fab_totale - disp)
                    
                    posso_fare = disp // req if req > 0 else 0
                    costruibili.append(posso_fare)
                    
                    dettagli.append({
                        "pn_componente": r['pn_componente'],
                        "quantita_richiesta": req,
                        "giacenza": disp,
                        "fabbisogno_totale": fab_totale,
                        "mancanti": mancanti
                    })
                min_pezzi = min(costruibili) if costruibili else 0
        except Exception as e:
            st.error(f"Errore calcolo fattibilità: {e}")
        finally:
            conn.close()

    return min_pezzi, dettagli


def get_lista_modelli():
    """Recupera la lista dei modelli presenti nelle Distinte Base."""
    conn = get_db_connection()
    modelli = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT modello FROM distinte_basi ORDER BY modello ASC")
            rows = cursor.fetchall()
            modelli = [r['modello'] for r in rows]
        except Exception as e:
            st.error(f"Errore recupero modelli: {e}")
        finally:
            conn.close()
    return modelli


def render():
    st.header("📥 Ingressi Magazzino & Gestione Giacenze")
    st.markdown("---")

    utente_loggato = st.session_state.get("utente_loggato", {})
    es_admin = utente_loggato.get("ruolo") == "Admin"
    nome_operatore = utente_loggato.get("nome_completo", utente_loggato.get("username", "OPERATORE")).upper()

    tab_stock, tab_carico, tab_ricerca = st.tabs([
        "📋 Stock Attuale & Fattibilità", 
        "➕ Carico Merci in Ingresso", 
        "🔍 Analisi Movimenti & Scheda Articolo"
    ])

    # ==========================================
    # TAB 1: STOCK ATTUALE E FATTIBILITÀ
    # ==========================================
    with tab_stock:
        st.subheader("🔮 Stima Fattibilità Produzione (Stock Generale)")
        
        lista_modelli = get_lista_modelli()
        if lista_modelli:
            col_mod, col_qta = st.columns([2, 1])
            with col_mod:
                modello_sel = st.selectbox("Seleziona Modello Centralina per la Stima:", lista_modelli)
            with col_qta:
                qta_prod = st.number_input("Quantità da Produrre (Pz):", min_value=1, value=10, step=1)
                
            pezzi_costruibili, dettagli_componenti = calcola_fattibilita_dettagliata(modello_sel, qta_prod)
            
            if dettagli_componenti:
                # Creazione dataframe per la visualizzazione a schermo
                df_fatt = pd.DataFrame(dettagli_componenti)
                df_fatt_display = df_fatt.rename(columns={
                    "pn_componente": "Part Number Componente",
                    "quantita_richiesta": "Req. Unità",
                    "giacenza": "Giacenza Attuale",
                    "fabbisogno_totale": "Fabbisogno Totale",
                    "mancanti": "Pezzi Mancanti"
                })
                
                st.dataframe(df_fatt_display, use_container_width=True, hide_index=True)
                
                # Estrazione componenti con carenza di stock
                solo_mancanti = [d for d in dettagli_componenti if d["mancanti"] > 0]
                
                col_res1, col_res2 = st.columns([2, 1])
                with col_res1:
                    if pezzi_costruibili >= qta_prod:
                        st.success(f"✅ **Fattibile!** Con lo stock attuale puoi produrre l'intero lotto di **{qta_prod} pz** (Max costruibili: {pezzi_costruibili} pz).")
                    else:
                        st.error(f"⚠️ **Stock Insufficiente!** Con la giacenza attuale puoi produrre al massimo **{pezzi_costruibili} pz** su {qta_prod} richiesti.")
                
                with col_res2:
                    if solo_mancanti:
                        pdf_bytes = genera_pdf_mancanti(modello_sel, qta_prod, solo_mancanti)
                        st.download_button(
                            label="📄 Stampa Lista Mancanti (PDF)",
                            data=pdf_bytes,
                            file_name=f"Lista_Mancanti_{modello_sel}_{qta_prod}pz.pdf",
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True
                        )
                    else:
                        st.info("Nessun pezzo mancante per questo lotto.")
        else:
            st.info("Nessuna Distinta Base (BOM) presente nel database per calcolare la fattibilità.")

        st.markdown("---")
        st.subheader("📦 Giacenze Magazzino Attuali")
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        pn_codice AS 'Part Number',
                        quantita_disponibile AS 'Giacenza Disponibile',
                        ubicazione AS 'Ubicazione',
                        operatore AS 'Ultimo Operatore',
                        data_ultimo_carico AS 'Ultimo Aggiornamento'
                    FROM magazzino_quantita
                    ORDER BY pn_codice ASC
                """)
                rows = cursor.fetchall()

                if rows:
                    df_stock = pd.DataFrame([dict(r) for r in rows])
                    st.dataframe(df_stock, use_container_width=True, hide_index=True)
                else:
                    st.info("Il magazzino è attualmente vuoto.")
            except Exception as e:
                st.error(f"Errore caricamento giacenze: {e}")
            finally:
                conn.close()

    # ==========================================
    # TAB 2: CARICO MERCI IN INGRESSO
    # ==========================================
    with tab_carico:
        st.subheader("➕ Registrazione Carico Merci")

        with st.form("form_carico_merci", clear_on_submit=True):
            col_pn, col_op = st.columns(2)
            with col_pn:
                pn_input = st.text_input("Part Number (PN Componente) *", placeholder="Es. RES_10K...").strip().upper()
            with col_op:
                st.text_input("Operatore", value=nome_operatore, disabled=True)

            col_qta, col_ubi = st.columns(2)
            with col_qta:
                qta_input = st.number_input("Quantità in Ingresso", min_value=1, value=1, step=1)
            with col_ubi:
                ubicazione_input = st.text_input("Ubicazione Magazzino *", value="SCAFFALE-A1").strip().upper()

            if st.form_submit_button("📦 Registra Ingressi Merci", type="primary", use_container_width=True):
                if not pn_input or not ubicazione_input:
                    st.error("I campi Part Number e Ubicazione sono obbligatori.")
                else:
                    conn = get_db_connection()
                    if conn:
                        try:
                            cursor = conn.cursor()
                            
                            # 1. Anagrafica PN (Se non esiste)
                            cursor.execute("INSERT OR IGNORE INTO part_numbers (pn_codice, descrizione, ubicazione) VALUES (?, ?, ?)",
                                           (pn_input, f"Componente {pn_input}", ubicazione_input))

                            # 2. Controllo Giacenza Preesistente
                            cursor.execute("SELECT quantita_disponibile FROM magazzino_quantita WHERE pn_codice = ?", (pn_input,))
                            res_qta = cursor.fetchone()
                            
                            if res_qta:
                                nuova_qta = res_qta['quantita_disponibile'] + qta_input
                                cursor.execute("""
                                    UPDATE magazzino_quantita 
                                    SET quantita_disponibile = ?, ubicazione = ?, operatore = ?, data_ultimo_carico = CURRENT_TIMESTAMP
                                    WHERE pn_codice = ?
                                """, (nuova_qta, ubicazione_input, nome_operatore, pn_input))
                            else:
                                nuova_qta = qta_input
                                cursor.execute("""
                                    INSERT INTO magazzino_quantita (pn_codice, quantita_disponibile, ubicazione, operatore, data_ultimo_carico)
                                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                                """, (pn_input, nuova_qta, ubicazione_input, nome_operatore))

                            # 3. Registrazione nello Storico Carichi
                            cursor.execute("""
                                INSERT INTO storico_carichi_magazzino (pn_codice, quantita_caricata, ubicazione, operatore)
                                VALUES (?, ?, ?, ?)
                            """, (pn_input, qta_input, ubicazione_input, nome_operatore))

                            conn.commit()
                            st.success(f"Registrati **+{qta_input} pz** per **{pn_input}** [Giacenza Totale: {nuova_qta} pz].")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore durante la registrazione nel Database: {e}")
                        finally:
                            conn.close()

    # ==========================================
    # TAB 3: RICERCA E STORICO
    # ==========================================
    with tab_ricerca:
        st.subheader("🔍 Analisi Movimenti & Scheda Articolo")

        col_search, col_d1, col_d2 = st.columns([2, 1.5, 1.5])
        with col_search:
            pn_ricerca = st.text_input("Inserisci Codice Articolo (PN)", placeholder="Es. RES_10K...").strip().upper()
        with col_d1:
            data_inizio = st.date_input("Data Inizio", value=datetime.now() - timedelta(days=30))
        with col_d2:
            data_fine = st.date_input("Data Fine", value=datetime.now())

        if pn_ricerca:
            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()

                    cursor.execute("SELECT quantita_disponibile, ubicazione, operatore, data_ultimo_carico FROM magazzino_quantita WHERE pn_codice = ?", (pn_ricerca,))
                    info_stock = cursor.fetchone()

                    if not info_stock:
                        st.warning(f"⚠️ Nessun articolo trovato a magazzino con il codice **{pn_ricerca}**.")
                    else:
                        cursor.execute("""
                            SELECT quantita_caricata, ubicazione, operatore, data_ora 
                            FROM storico_carichi_magazzino 
                            WHERE pn_codice = ? 
                            AND DATE(data_ora) BETWEEN ? AND ?
                        """, (pn_ricerca, data_inizio.strftime('%Y-%m-%d'), data_fine.strftime('%Y-%m-%d')))
                        carichi_db = cursor.fetchall()

                        try:
                            cursor.execute("""
                                SELECT serial_centralina, quantita_usata, data_associazione 
                                FROM componenti_centralina 
                                WHERE pn_codice = ? 
                                AND DATE(data_associazione) BETWEEN ? AND ?
                            """, (pn_ricerca, data_inizio.strftime('%Y-%m-%d'), data_fine.strftime('%Y-%m-%d')))
                            scarichi_db = cursor.fetchall()
                        except Exception:
                            scarichi_db = []

                        col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
                        col_kpi1.metric("📦 Giacenza Attuale", f"{info_stock['quantita_disponibile']} pz")
                        col_kpi2.metric("📍 Ubicazione", info_stock['ubicazione'])
                        
                        tot_caricato = sum([c['quantita_caricata'] for c in carichi_db]) if carichi_db else 0
                        tot_consumato = sum([s['quantita_usata'] for s in scarichi_db]) if scarichi_db else 0
                        
                        col_kpi3.metric("📈 Tot. Caricato", f"+{tot_caricato} pz")
                        col_kpi4.metric("📉 Tot. Scaricato", f"-{tot_consumato} pz")

                        movimenti_unificati = []
                        for c in carichi_db:
                            movimenti_unificati.append({
                                "Data / Ora": c['data_ora'],
                                "Tipo Movimento": "📥 CARICO INGRESSO",
                                "Quantità": f"+{c['quantita_caricata']}",
                                "Dettaglio": f"Ubicazione: {c['ubicazione']}",
                                "Operatore": c['operatore']
                            })
                        
                        for s in scarichi_db:
                            movimenti_unificati.append({
                                "Data / Ora": s.get('data_associazione', 'N/D'),
                                "Tipo Movimento": "📤 SCARICO ASSEMBLAGGIO",
                                "Quantità": f"-{s['quantita_usata']}",
                                "Dettaglio": f"Centralina: {s['serial_centralina']}",
                                "Operatore": "SISTEMA"
                            })

                        if movimenti_unificati:
                            st.dataframe(pd.DataFrame(movimenti_unificati), use_container_width=True, hide_index=True)
                        else:
                            st.info("Nessun movimento trovato per questo periodo.")

                except Exception as e:
                    st.error(f"Errore durante l'analisi dati: {e}")
                finally:
                    conn.close()
