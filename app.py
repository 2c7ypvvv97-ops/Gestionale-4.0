import streamlit as st
import database
import backup
import import_export


# 1. Configurazione Pagina (deve essere la prima chiamata Streamlit)
st.set_page_config(
    page_title="Gestionale Fabbrica",
    page_icon="🏭",
    layout="wide"
)

# 2. Inizializzazione Database
database.init_db()

# 3. Controllo ed esecuzione Backup Automatico Cifrato (ogni 24h)
if "backup_auto_eseguito" not in st.session_state:
    ok_auto, msg_auto = backup.controlla_ed_esegui_backup_automatico(
        cartella_destinazione="./backups", 
        intervallo_ore=24
    )
    if ok_auto:
        st.toast(f"🔒 {msg_auto}", icon="🛡️")
    st.session_state["backup_auto_eseguito"] = True

# 4. Import dei Moduli
from modules import commesse, bom_manager, magazzino, assemblaggio, avanzamento, storico, clienti, scarti_rma, report

# --- MATRICE RUOLI & PERMESSI ---
MATRICE_PERMESSI = {
    "Admin": [
        "📝 Monitor Commesse",        
        "📋 Gestione BOM",
        "📦 Ingressi Magazzino",
        "👥 Anagrafica Clienti",
        "⚙️ Assemblaggio Centraline",
        "🔄 Avanzamento Fasi",
        "🛡️ Qualità & RMA",
        "📜 Storico Operazioni",
        "📊 Reportistica & Export",
        "📥 Importazione Massiva",        
        "👤 Utenti & Backup"
    ],
    "Magazziniere": [
        "📦 Ingressi Magazzino",
        "📋 Gestione BOM",
        "🛡️ Qualità & RMA",
        "📜 Storico Operazioni"
    ],
    "Operatore Produzione": [
        "⚙️ Assemblaggio Centraline",
        "📊 Reportistica & Export",
        "🔄 Avanzamento Fasi"
    ],
    "Controllo Qualità / Collaudatore": [
        "🔄 Avanzamento Fasi",
        "🛡️ Qualità & RMA",
        "📊 Reportistica & Export",
        "📜 Storico Operazioni"
    ]
}

# --- GESTIONE SESSION STATE ---
if "utente_loggato" not in st.session_state:
    st.session_state["utente_loggato"] = None

# --- SCHERMATA DI LOGIN ---
def render_login():
    st.markdown("<h1 style='text-align: center;'>🏭 Accesso Gestionale Fabbrica</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("Login Utente")
        username_input = st.text_input("Username").strip().lower()
        password_input = st.text_input("Password", type="password")
        
        if st.button("Accedi", use_container_width=True):
            user = database.autentica_utente(username_input, password_input)
            if user:
                st.session_state["utente_loggato"] = user
                st.success(f"Benvenuto {user['nome_completo']}!")
                st.rerun()
            else:
                st.error("Credenziali errate o utente non attivo.")

# --- MODULO ADMIN: GESTIONE BACKUP CIFRATI ---
def render_gestione_backup():
    st.subheader("🛡️ Backup & Ripristino Sicuro (AES-256)")
    
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📦 Esegui Backup Manuale")
        cartella_dest = st.text_input(
            "Cartella di destinazione:", 
            value="./backups", 
            help="Puoi inserire un percorso locale (es. ./backups) o di rete NAS (es. //NAS/Backup/Fabbrica)"
        )
        usar_cifratura = st.checkbox("Cifra il backup con algoritmo AES (Fernet)", value=True)

        if st.button("🚀 Avvia Backup Ora", type="primary"):
            with st.spinner("Creazione del backup in corso..."):
                esito, messaggio = backup.esegui_backup_cifrato(cartella_dest, cifrato=usar_cifratura)
                
            if esito:
                st.success(messaggio)
            else:
                st.error(messaggio)

    with col2:
        st.markdown("### 🔄 Ripristina Database")
        st.warning("⚠️ Il ripristino sovrascriverà il database attuale con i dati del backup caricato!")
        
        file_backup_upload = st.file_uploader("Carica file di backup (.enc)", type=["enc"])
        
        if file_backup_upload is not None:
            if st.button("🔴 Conferma Ripristino", type="secondary"):
                temp_path = f"temp_{file_backup_upload.name}"
                with open(temp_path, "wb") as f:
                    f.write(file_backup_upload.getbuffer())
                
                esito, messaggio = backup.ripristina_backup_cifrato(temp_path)
                
                import os
                if os.path.exists(temp_path):
                    os.remove(temp_path)

                if esito:
                    st.success(messaggio)
                    st.info("Ricarica la pagina per aggiornare la vista dei dati.")
                else:
                    st.error(messaggio)

# --- MODULO ADMIN: GESTIONE UTENTI & AMMINISTRAZIONE ---
def render_gestione_utenti():
    st.title("👤 Amministrazione Utenti e Backup")
    
    tab_lista, tab_modifica, tab_nuovo, tab_backup = st.tabs([
        "📋 Lista Utenti", 
        "⚙️ Modifica Stato & Ruolo", 
        "➕ Nuovo Utente",
        "🛡️ Backup & Ripristino"
    ])
    
    # TAB 1: LISTA UTENTI
    with tab_lista:
        st.subheader("Utenti Registrati")
        utenti = database.get_tutti_utenti()
        if utenti:
            for u in utenti:
                u['stato_visivo'] = "🟢 Attivo" if u.get('attivo', 1) == 1 else "🔴 Disabilitato"
            st.dataframe(utenti, use_container_width=True, hide_index=True)
        else:
            st.info("Nessun utente trovato.")

    # TAB 2: MODIFICA STATO / RUOLO & ELIMINAZIONE
    with tab_modifica:
        st.subheader("Gestione Stato ed Eliminazione Account")
        utenti_raw = database.get_tutti_utenti()
        current_admin = st.session_state["utente_loggato"]["username"]
        
        opzioni_utenti = [u['username'] for u in utenti_raw if u['username'] != current_admin]

        if not opzioni_utenti:
            st.info("Nessun altro utente disponibile per la modifica.")
        else:
            scelto = st.selectbox("Seleziona Utente da Gestire:", opzioni_utenti)
            u_info = next((u for u in utenti_raw if u['username'] == scelto), None)

            if u_info:
                with st.form("form_modifica_stato_utente"):
                    col1, col2 = st.columns(2)
                    
                    ruoli_disponibili = ["Admin", "Magazziniere", "Operatore Produzione", "Controllo Qualità / Collaudatore"]
                    idx_ruolo = ruoli_disponibili.index(u_info['ruolo']) if u_info['ruolo'] in ruoli_disponibili else 0
                    
                    with col1:
                        nuovo_ruolo = st.selectbox("Ruolo Assegnato", ruoli_disponibili, index=idx_ruolo)
                    with col2:
                        stato_attivo = st.toggle("Account Attivo", value=bool(u_info.get('attivo', 1)))

                    btn_salva = st.form_submit_button("💾 Salva Modifiche", type="primary")

                    if btn_salva:
                        ok, msg = database.aggiorna_stato_utente(scelto, nuovo_ruolo, 1 if stato_attivo else 0)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

                st.markdown("---")
                
                with st.expander("🗑️ Eliminazione Definitiva Account (Solo per Errori)"):
                    st.warning("⚠️ L'eliminazione definitiva va applicata solo per account errati senza storico operativo.")
                    if st.button(f"❌ Elimina Definitivamente {scelto}", type="secondary"):
                        ok_del, msg_del = database.elimina_utente_protetto(scelto)
                        if ok_del:
                            st.success(msg_del)
                            st.rerun()
                        else:
                            st.error(msg_del)

    # TAB 3: CREAZIONE NUOVO UTENTE
    with tab_nuovo:
        st.subheader("Crea Nuovo Utente")
        with st.form("form_nuovo_utente", clear_on_submit=True):
            nuovo_user = st.text_input("Username").strip().lower()
            nuovo_nome = st.text_input("Nome Completo").strip()
            nuova_pwd = st.text_input("Password", type="password")
            ruolo = st.selectbox("Ruolo", ["Admin", "Magazziniere", "Operatore Produzione", "Controllo Qualità / Collaudatore"])
            
            submit = st.form_submit_button("➕ Crea Utente", type="primary")
            if submit:
                if nuovo_user and nuova_pwd and nuovo_nome:
                    ok, msg = database.crea_utente(nuovo_user, nuova_pwd, nuovo_nome, ruolo)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("Compila tutti i campi obbligatori!")

    # TAB 4: GESTIONE BACKUP
    with tab_backup:
        render_gestione_backup()

# --- FLUSSO PRINCIPALE DELL'APPLICAZIONE ---
if st.session_state["utente_loggato"] is None:
    render_login()
else:
    utente = st.session_state["utente_loggato"]
    ruolo_utente = utente["ruolo"]
    
    st.sidebar.title("🏭 Fabbrica Gestionale")
    st.sidebar.markdown(f"**Utente:** {utente['nome_completo']}")
    st.sidebar.markdown(f"**Ruolo:** `{ruolo_utente}`")
    
    if st.sidebar.button("🔴 Logout", use_container_width=True):
        st.session_state["utente_loggato"] = None
        st.rerun()
        
    st.sidebar.divider()
    
    moduli_disponibili = MATRICE_PERMESSI.get(ruolo_utente, [])
    
    if not moduli_disponibili:
        st.error("Nessun modulo abilitato per questo ruolo. Contatta l'Amministratore.")
    else:
        scelta_modulo = st.sidebar.radio("Navigazione Moduli", moduli_disponibili)
        
        if scelta_modulo == "📦 Ingressi Magazzino":
            magazzino.render()
        elif scelta_modulo == "📋 Gestione BOM":
            bom_manager.render()
        elif scelta_modulo == "👥 Anagrafica Clienti":
            clienti.render()
        elif scelta_modulo == "📝 Monitor Commesse":
            commesse.render()
        elif scelta_modulo == "⚙️ Assemblaggio Centraline":    
            assemblaggio.render()
        elif scelta_modulo == "🔄 Avanzamento Fasi":
            avanzamento.render()
        elif scelta_modulo == "🛡️ Qualità & RMA":
            scarti_rma.render()
        elif scelta_modulo == "📜 Storico Operazioni":
            storico.render()
        elif scelta_modulo == "📊 Reportistica & Export":
            report.render()
        elif scelta_modulo == "📥 Importazione Massiva":
            import_export.render_importazione_ui()    
        elif scelta_modulo == "👤 Utenti & Backup" and ruolo_utente == "Admin":
            render_gestione_utenti()
