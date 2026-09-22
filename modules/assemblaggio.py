import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_db_connection
from modules.pdf_generator import genera_pdf_etichetta

def render():
    st.header("🛠️ Banco Assemblaggio & Produzione")
    st.markdown("---")

    # Recupera le info dell'utente loggato dalla sessione
    utente_loggato = st.session_state.get("utente_loggato", {})
    nome_operatore = utente_loggato.get("nome_completo", utente_loggato.get("username", "OPERATORE SCONOSCIUTO")).upper()

    tab_padre, tab_figlio = st.tabs([
        "📱 Assemblaggio Centralina Finale", 
        "🧩 Produzione Sotto-Schede (Sub-Assemblati)"
    ])

    # ==========================================
    # TAB 1: ASSEMBLAGGIO CENTRALINA FINALE
    # ==========================================
    with tab_padre:
        st.subheader("Assemblaggio Centralina Finale & Scarico BOM")

        conn = get_db_connection()
        commesse_aperte = []
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT codice_commessa, modello_centralina FROM commesse WHERE stato = 'Aperta'")
                commesse_aperte = cursor.fetchall()
            except Exception as e:
                st.error(f"Errore caricamento commesse: {e}")
            finally:
                conn.close()

        if not commesse_aperte:
            st.warning("⚠️ Nessuna commessa attualmente 'Aperta'. Apri una commessa prima di procedere con l'assemblaggio.")
        else:
            opts_commessa = [c['codice_commessa'] for c in commesse_aperte]
            commessa_sel = st.selectbox("Seleziona Commessa Padre", options=opts_commessa)

            # Sincronizza automaticamente il modello centralina abbinato alla commessa nel DB
            commessa_info = next((c for c in commesse_aperte if c['codice_commessa'] == commessa_sel), None)
            modello_sel = commessa_info['modello_centralina'] if commessa_info else "STD"

            with st.form("form_assemblaggio_padre", clear_on_submit=False):
                col_c, col_m, col_op = st.columns(3)

                with col_c:
                    st.text_input("Commessa Selezionata", value=commessa_sel, disabled=True)
                with col_m:
                    st.text_input("Modello Abbinato da Commessa", value=modello_sel, disabled=True)
                with col_op:
                    operatore_input = st.text_input("Operatore Banco", value=nome_operatore, disabled=True)

                # --- VERIFICA LIMITE PRODUZIONE COMMESSA PADRE ---
                conn = get_db_connection()
                qta_max = 0
                qta_prodotta = 0
                if conn:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("SELECT quantita_totale FROM commesse WHERE codice_commessa = ?", (commessa_sel,))
                        res_c = cursor.fetchone()
                        qta_max = res_c['quantita_totale'] if res_c else 0

                        cursor.execute("SELECT COUNT(*) as tot FROM centraline WHERE commessa_padre = ?", (commessa_sel,))
                        res_p = cursor.fetchone()
                        qta_prodotta = res_p['tot'] if res_p else 0
                    except Exception as e:
                        st.error(f"Errore lettura limiti commessa: {e}")
                    finally:
                        conn.close()

                st.markdown("##### 📊 Avanzamento Commessa Selezionata")
                if qta_prodotta >= qta_max:
                    st.error(f"🚫 **COMMESSA COMPLETATA / SATURA**: Prodotti **{qta_prodotta} / {qta_max} pz**. Impossibile produrre ulteriori unità.")
                else:
                    st.info(f"📈 **Stato Produzione**: **{qta_prodotta} / {qta_max} pz** prodotti per la commessa **{commessa_sel}** (Rimanenti: **{qta_max - qta_prodotta} pz**).")

                    # --- VERIFICA COMPONENTI BOM ---
                    st.markdown("##### 🔍 Componenti Richiesti da BOM (Magazzino)")
                    conn = get_db_connection()
                    bom_items = []
                    mancanti = []
                    if conn:
                        try:
                            cursor = conn.cursor()
                            # Uso UPPER(TRIM(...)) per evitare fallimenti dovuti a Maiuscole/Minuscole o spazi
                            cursor.execute("""
                                SELECT d.pn_componente, d.quantita_richiesta, COALESCE(m.quantita_disponibile, 0) as giacenza
                                FROM distinte_basi d
                                LEFT JOIN magazzino_quantita m ON d.pn_componente = m.pn_codice
                                WHERE UPPER(TRIM(d.modello)) = UPPER(TRIM(?))
                            """, (modello_sel,))
                            bom_items = cursor.fetchall()
                        except Exception as e:
                            st.error(f"Errore lettura distinta base: {e}")
                        finally:
                            conn.close()

                if bom_items:
                    df_bom = pd.DataFrame([dict(b) for b in bom_items])
                    df_bom.columns = ["Part Number (Componente / Sotto-scheda)", "Q.tà Richiesta", "Giacenza Attuale"]
                    st.dataframe(df_bom, use_container_width=True, hide_index=True)

                    for item in bom_items:
                        if item['giacenza'] < item['quantita_richiesta']:
                            mancanti.append(f"{item['pn_componente']} (Disponibili: {item['giacenza']} / Req: {item['quantita_richiesta']})")
                else:
                    st.warning(f"⚠️ Nessuna distinta base trovata per il modello {modello_sel}.")

                btn_assembla = st.form_submit_button("⚙️ Conferma Assemblaggio & Genera Seriale", type="primary", use_container_width=True)

                if btn_assembla:
                    if qta_prodotta >= qta_max:
                        st.error(f"⛔ **OPERAZIONE BLOCCATA**: La commessa {commessa_sel} ha già raggiunto il limite di {qta_max} pz!")
                    elif not operatore_input:
                        st.error("Errore sessione: Operatore non identificato.")
                    elif not bom_items:
                        st.error(f"❌ Impossibile procedere: Manca la distinta base per il modello {modello_sel}.")
                    elif mancanti:
                        st.error(f"❌ Impossibile completare l'assemblaggio. Materiali insufficienti a magazzino:\n" + "\n".join(mancanti))
                    else:
                        conn = get_db_connection()
                        if conn:
                            try:
                                cursor = conn.cursor()
                                cursor.execute("BEGIN TRANSACTION;")

                                num_prog = qta_prodotta + 1
                                seriale_nuovo = f"{commessa_sel}-{modello_sel}-{num_prog:03d}"

                                # Usa 'tipologia' allineato allo schema del database
                                cursor.execute("""
                                    INSERT INTO centraline (serial_centralina, commessa_padre, tipologia, fase_attuale, note)
                                    VALUES (?, ?, ?, 'Assemblaggio', ?)
                                """, (seriale_nuovo, commessa_sel, modello_sel, f"Assemblato da {operatore_input}"))

                                cursor.execute("""
                                    INSERT INTO storico_fasi (serial_centralina, fase_destinazione, operatore)
                                    VALUES (?, 'Assemblaggio', ?)
                                """, (seriale_nuovo, operatore_input))

                                for item in bom_items:
                                    pn = item['pn_componente']
                                    qta = item['quantita_richiesta']

                                    cursor.execute("""
                                        UPDATE magazzino_quantita 
                                        SET quantita_disponibile = quantita_disponibile - ? 
                                        WHERE pn_codice = ?
                                    """, (qta, pn))

                                    cursor.execute("""
                                        INSERT INTO componenti_centralina (serial_centralina, pn_codice, quantita_usata)
                                        VALUES (?, ?, ?)
                                    """, (seriale_nuovo, pn, qta))

                                conn.commit()

                                st.session_state["ultima_etichetta"] = {
                                    "seriale": seriale_nuovo,
                                    "commessa": commessa_sel,
                                    "modello": modello_sel,
                                    "data": datetime.now().strftime("%d/%m/%Y")
                                }

                                st.success(f"🎉 Centralina assemblata con successo! Seriale Generato: **{seriale_nuovo}** ({num_prog}/{qta_max} pz)")
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"Errore durante l'assemblaggio (Rollback eseguito): {e}")
                            finally:
                                conn.close()

        # Blocco Stampa Etichetta Termica
        if "ultima_etichetta" in st.session_state and st.session_state["ultima_etichetta"]:
            eti = st.session_state["ultima_etichetta"]
            try:
                pdf_bytes = genera_pdf_etichetta(
                    seriale=eti["seriale"],
                    commessa=eti["commessa"],
                    modello=eti["modello"],
                    data_str=eti["data"]
                )

                st.markdown("---")
                st.subheader("🖨️ Stampa Etichetta Termica Centralina Inserita")
                col_d1, col_d2 = st.columns([3, 1])
                with col_d1:
                    st.info(f"Etichetta pronta per il seriale: **{eti['seriale']}** (Modello: {eti['modello']} | Commessa: {eti['commessa']})")
                with col_d2:
                    st.download_button(
                        label=f"🖨️ Scarica / Stampa Etichetta",
                        data=pdf_bytes,
                        file_name=f"etichetta_{eti['seriale']}.pdf",
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True
                    )
            except Exception as e:
                st.error(f"Errore generazione PDF etichetta: {e}")

    # ==========================================
    # TAB 2: PRODUZIONE SOTTO-SCHEDE CON VINCOLO COMMESSA
    # ==========================================
    with tab_figlio:
        st.subheader("Produzione Sotto-Schede (Sub-Assemblati)")
        st.caption("Consuma i componenti di base per creare sotto-schede rientrando nei limiti previsti dalle commesse.")

        conn = get_db_connection()
        lista_sotto_schede = []
        commesse_aperte_ss = []
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT pn_sotto_scheda FROM distinte_sotto_schede")
                lista_sotto_schede = [r['pn_sotto_scheda'] for r in cursor.fetchall()]

                cursor.execute("SELECT codice_commessa, modello_centralina, quantita_totale FROM commesse WHERE stato = 'Aperta'")
                commesse_aperte_ss = cursor.fetchall()
            except Exception as e:
                st.error(f"Errore recupero sotto-schede: {e}")
            finally:
                conn.close()

        if not lista_sotto_schede:
            st.info("ℹ️ Nessuna distinta per sotto-schede attualmente salvata a sistema.")
        else:
            with st.form("form_sotto_scheda", clear_on_submit=True):
                col_comm, col_ss, col_q, col_op_s = st.columns(4)

                with col_comm:
                    opts_comm = ["PRODUZIONE LIBERA / STOCK"] + [f"{c['codice_commessa']} ({c['modello_centralina']})" for c in commesse_aperte_ss]
                    commessa_ref = st.selectbox("Commessa di Riferimento", options=opts_comm)

                with col_ss:
                    ss_selezionata = st.selectbox("Codice Sotto-Scheda", options=lista_sotto_schede)

                with col_q:
                    qta_produrre = st.number_input("Quantità da Produrre (pz)", min_value=1, value=1, step=1)

                with col_op_s:
                    operatore_ss = st.text_input("Operatore Produzione", value=nome_operatore, disabled=True)

                # --- CALCOLO VINCOLO FABBISOGNO ---
                max_sotto_schede_consentite = 999999
                giacenza_attuale_ss = 0

                conn = get_db_connection()
                if conn:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("SELECT quantita_disponibile FROM magazzino_quantita WHERE pn_codice = ?", (ss_selezionata,))
                        res_g = cursor.fetchone()
                        giacenza_attuale_ss = res_g['quantita_disponibile'] if res_g else 0

                        if commessa_ref != "PRODUZIONE LIBERA / STOCK":
                            cod_c_clean = commessa_ref.split(" (")[0]
                            
                            cursor.execute("SELECT modello_centralina, quantita_totale FROM commesse WHERE codice_commessa = ?", (cod_c_clean,))
                            info_c = cursor.fetchone()
                            
                            if info_c:
                                modello_padre = info_c['modello_centralina']
                                qta_commessa = info_c['quantita_totale']

                                cursor.execute("SELECT quantita_richiesta FROM distinte_basi WHERE modello = ? AND pn_componente = ?", (modello_padre, ss_selezionata))
                                res_bom_p = cursor.fetchone()
                                qta_req_per_padre = res_bom_p['quantita_richiesta'] if res_bom_p else 1

                                fabbisogno_totale_commessa = qta_commessa * qta_req_per_padre
                                max_sotto_schede_consentite = max(0, fabbisogno_totale_commessa - giacenza_attuale_ss)

                                st.info(
                                    f"🎯 **Vincolo Commessa {cod_c_clean}**: "
                                    f"Fabbisogno totale = **{fabbisogno_totale_commessa} pz** | "
                                    f"Giacenza attuale = **{giacenza_attuale_ss} pz** | "
                                    f"Limite massimo producibile ora = **{max_sotto_schede_consentite} pz**"
                                )
                    except Exception as e:
                        st.error(f"Errore calcolo vincoli: {e}")
                    finally:
                        conn.close()

                # --- VERIFICA COMPONENTI DI BASE ---
                conn = get_db_connection()
                bom_ss = []
                mancanti_ss = []
                if conn:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT d.pn_componente, (d.quantita_richiesta * ?) as totale_req, COALESCE(m.quantita_disponibile, 0) as giacenza
                            FROM distinte_sotto_schede d
                            LEFT JOIN magazzino_quantita m ON d.pn_componente = m.pn_codice
                            WHERE d.pn_sotto_scheda = ?
                        """, (qta_produrre, ss_selezionata))
                        bom_ss = cursor.fetchall()
                    except Exception as e:
                        st.error(f"Errore verifica componenti sotto-schede: {e}")
                    finally:
                        conn.close()

                if bom_ss:
                    st.markdown(f"##### 📦 Fabbisogno Componenti per **{qta_produrre} pz** di **{ss_selezionata}**")
                    df_bom_ss = pd.DataFrame([dict(b) for b in bom_ss])
                    df_bom_ss.columns = ["Componente Base", "Q.tà Totale Richiesta", "Giacenza Magazzino"]
                    st.dataframe(df_bom_ss, use_container_width=True, hide_index=True)

                    for item in bom_ss:
                        if item['giacenza'] < item['totale_req']:
                            mancanti_ss.append(f"{item['pn_componente']} (Disponibili: {item['giacenza']} / Req: {item['totale_req']})")

                btn_produciss = st.form_submit_button("🧩 Produci e Carica Sotto-Schede a Magazzino", type="primary", use_container_width=True)

                if btn_produciss:
                    if qta_produrre > max_sotto_schede_consentite:
                        st.error(f"⛔ **PRODUZIONE BLOCCATA**: La quantità richiesta ({qta_produrre} pz) supera il limite consentito per la commessa ({max_sotto_schede_consentite} pz)!")
                    elif not operatore_ss:
                        st.error("Errore sessione: Operatore non identificato.")
                    elif mancanti_ss:
                        st.error(f"❌ Componenti insufficienti per produrre le sotto-schede:\n" + "\n".join(mancanti_ss))
                    else:
                        conn = get_db_connection()
                        if conn:
                            try:
                                cursor = conn.cursor()
                                cursor.execute("BEGIN TRANSACTION;")

                                for item in bom_ss:
                                    pn = item['pn_componente']
                                    qta_tot = item['totale_req']

                                    cursor.execute("""
                                        UPDATE magazzino_quantita 
                                        SET quantita_disponibile = quantita_disponibile - ? 
                                        WHERE pn_codice = ?
                                    """, (qta_tot, pn))

                                nuova_qta_ss = giacenza_attuale_ss + qta_produrre

                                # Usa UPDATE o INSERT separati per evitare incongruenze
                                cursor.execute("SELECT pn_codice FROM magazzino_quantita WHERE pn_codice = ?", (ss_selezionata,))
                                if cursor.fetchone():
                                    cursor.execute("""
                                        UPDATE magazzino_quantita 
                                        SET quantita_disponibile = ?, ubicazione = 'REPARTO-SOTTO-SCHEDE', operatore = ?, data_ultimo_carico = CURRENT_TIMESTAMP
                                        WHERE pn_codice = ?
                                    """, (nuova_qta_ss, operatore_ss, ss_selezionata))
                                else:
                                    cursor.execute("""
                                        INSERT INTO magazzino_quantita (pn_codice, quantita_disponibile, ubicazione, operatore, data_ultimo_carico)
                                        VALUES (?, ?, 'REPARTO-SOTTO-SCHEDE', ?, CURRENT_TIMESTAMP)
                                    """, (ss_selezionata, nuova_qta_ss, operatore_ss))

                                cursor.execute("""
                                    INSERT INTO storico_carichi_magazzino (pn_codice, quantita_caricata, ubicazione, operatore)
                                    VALUES (?, ?, 'PRODUZIONE-INTERNA', ?)
                                """, (ss_selezionata, qta_produrre, operatore_ss))

                                conn.commit()
                                st.success(f"✅ Prodotte con successo **+{qta_produrre} pz** di **{ss_selezionata}**! Nuova giacenza: **{nuova_qta_ss} pz**")
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"Errore durante la produzione sotto-schede (Rollback eseguito): {e}")
                            finally:
                                conn.close()
