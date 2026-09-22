from database import get_db_connection

def calcola_fattibilita_modelli():
    """
    Calcola quante centraline per ciascun modello sono costruibili 
    con le giacenze attuali di magazzino, identificando i colli di bottiglia.
    """
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()

    # 1. Recupera la giacenza attuale di tutti i componenti a magazzino
    cursor.execute("SELECT pn_codice, quantita_disponibile FROM magazzino_quantita")
    giacenze = {row['pn_codice']: row['quantita_disponibile'] for row in cursor.fetchall()}

    # 2. Recupera l'intera Distinta Base (BOM) in un'unica query (ottimizzazione N+1)
    cursor.execute("""
        SELECT modello, pn_componente, quantita_richiesta 
        FROM distinte_basi 
        ORDER BY modello ASC, pn_componente ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return []

    # Raggruppamento locale dei componenti per modello
    modelli_bom = {}
    for r in rows:
        mod = r['modello']
        if mod not in modelli_bom:
            modelli_bom[mod] = []
        modelli_bom[mod].append(r)

    risultati = []

    # 3. Calcolo fattibilità e colli di bottiglia per modello
    for modello, componenti in modelli_bom.items():
        limiti_produzione = []
        dettagli_string = []

        for item in componenti:
            pn = item['pn_componente']
            qta_req = item['quantita_richiesta']
            qta_disp = giacenze.get(pn, 0)

            if qta_req > 0:
                pezzi_fattibili = qta_disp // qta_req
                limiti_produzione.append(pezzi_fattibili)
            else:
                limiti_produzione.append(0)

            dettagli_string.append(f"{pn} ({qta_disp}/{qta_req})")

        min_pezzi = min(limiti_produzione) if limiti_produzione else 0

        risultati.append({
            "Modello Centralina": modello,
            "Pezzi Costruibili": min_pezzi,
            "Dettaglio Componenti (Disp / Req)": " | ".join(dettagli_string)
        })

    return risultati
