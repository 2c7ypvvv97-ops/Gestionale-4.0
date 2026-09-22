import io
from datetime import datetime
import qrcode
from barcode import Code128
from barcode.writer import ImageWriter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

def genera_qr_code_image(testo: str) -> io.BytesIO:
    """Genera l'immagine PNG del QR Code in memoria."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=0
    )
    qr.add_data(testo)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

def genera_barcode_image(testo: str) -> io.BytesIO:
    """Genera l'immagine PNG del Barcode Code128 in memoria."""
    buffer = io.BytesIO()
    code = Code128(testo, writer=ImageWriter())
    code.write(buffer, options={"write_text": False, "quiet_zone": 1.0, "module_height": 8.0})
    buffer.seek(0)
    return buffer

def genera_pdf_etichetta(seriale: str, commessa: str, modello: str, data_str: str = "", nome_azienda: str = "MY COMPANY SRL") -> bytes:
    """
    Genera un PDF con formato esatto 70x36 mm contenente layout termico:
    - Intestazione Azienda
    - Modello e Commessa (con tronco di sicurezza per evitare sovrapposizioni al QR)
    - QR Code e Barcode Code128
    - Seriale visualizzato in chiaro
    """
    larghezza_pt = 70 * mm
    altezza_pt = 36 * mm

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(larghezza_pt, altezza_pt))

    # Marginazioni operative
    m_left = 2 * mm
    m_top = altezza_pt - (3 * mm)

    # 1. Intestazione Azienda
    c.setFont("Helvetica-Bold", 8)
    c.drawString(m_left, m_top, nome_azienda.upper()[:22])

    # Linea divisoria superiore
    c.setLineWidth(0.5)
    c.line(m_left, m_top - (2 * mm), larghezza_pt - m_left, m_top - (2 * mm))

    # Tronco stringhe lunghe per prevenire sovrapposizione con QR Code
    modello_txt = f"MOD: {modello}"
    commessa_txt = f"COMM: {commessa}"
    if len(modello_txt) > 16:
        modello_txt = modello_txt[:14] + ".."
    if len(commessa_txt) > 16:
        commessa_txt = commessa_txt[:14] + ".."

    # 2. Informazioni Prodotto & Commessa
    c.setFont("Helvetica-Bold", 7)
    c.drawString(m_left, m_top - (5.5 * mm), modello_txt)
    c.setFont("Helvetica", 6.5)
    c.drawString(m_left, m_top - (8.5 * mm), commessa_txt)
    if data_str:
        c.drawString(m_left, m_top - (11.5 * mm), f"DATE: {data_str}")

    # 3. QR Code (Convertito con ImageReader)
    qr_buf = genera_qr_code_image(seriale)
    qr_image = ImageReader(qr_buf)
    qr_size = 14 * mm
    qr_x = larghezza_pt - qr_size - (2 * mm)
    qr_y = altezza_pt - qr_size - (3 * mm)
    c.drawImage(qr_image, qr_x, qr_y, width=qr_size, height=qr_size)

    # 4. Barcode Code128 (Convertito con ImageReader)
    barcode_buf = genera_barcode_image(seriale)
    barcode_image = ImageReader(barcode_buf)
    bc_w = 64 * mm
    bc_h = 10 * mm
    bc_x = (larghezza_pt - bc_w) / 2
    bc_y = 6 * mm
    c.drawImage(barcode_image, bc_x, bc_y, width=bc_w, height=bc_h)

    # 5. Seriale Testuale (Centrato sotto il Barcode)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(larghezza_pt / 2, 2 * mm, f"S/N: {seriale}")

    c.showPage()
    c.save()
    
    buffer.seek(0)
    return buffer.getvalue()

def genera_pdf_certificato_collaudo(
    seriale: str,
    commessa: str,
    modello: str,
    cliente: str,
    data_creazione: str,
    fase_attuale: str,
    componenti: list,
    storico_fasi: list,
    segnalazioni_rma: list,
    nome_azienda: str = "MY COMPANY SRL"
) -> bytes:
    """
    Genera un Certificato di Collaudo & Scheda Tecnica in formato A4 (PDF).
    """
    from reportlab.lib.pagesizes import A4
    
    larghezza_pt, altezza_pt = A4
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    m_left = 15 * mm
    m_right = larghezza_pt - (15 * mm)
    m_top = altezza_pt - (15 * mm)

    # 1. Intestazione & Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(m_left, m_top, nome_azienda.upper())
    
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(m_right, m_top, "CERTIFICATO DI COLLAUDO")

    c.setFont("Helvetica", 9)
    c.drawString(m_left, m_top - (5 * mm), "Documento Tecnico di Accompagnamento e Controllo Qualità")

    c.setLineWidth(1)
    c.line(m_left, m_top - (8 * mm), m_right, m_top - (8 * mm))

    # 2. Informazioni Unità & Commessa
    y = m_top - (18 * mm)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(m_left, y, "INFORMAZIONI PRODOTTO")

    c.setFont("Helvetica", 9)
    y -= 5 * mm
    c.drawString(m_left, y, f"Seriale Centralina (S/N): {seriale}")
    c.drawString(m_left + (80 * mm), y, f"Codice Commessa: {commessa}")

    y -= 5 * mm
    c.drawString(m_left, y, f"Modello / Tipologia: {modello}")
    c.drawString(m_left + (80 * mm), y, f"Cliente: {cliente if cliente else 'N/D'}")

    y -= 5 * mm
    c.drawString(m_left, y, f"Data Creazione: {data_creazione}")
    c.drawString(m_left + (80 * mm), y, f"Stato/Fase Attuale: {fase_attuale}")

    # Integrazione QR Code
    try:
        qr_buf = genera_qr_code_image(seriale)
        qr_image = ImageReader(qr_buf)
        c.drawImage(qr_image, m_right - (25 * mm), m_top - (35 * mm), width=25 * mm, height=25 * mm)
    except Exception:
        pass

    # Linea separatrice
    y -= 5 * mm
    c.setLineWidth(0.5)
    c.line(m_left, y, m_right, y)

    # 3. Componenti Installati
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(m_left, y, "DISTINTA COMPONENTI INSTALLATI")

    y -= 6 * mm
    c.setFont("Helvetica-Bold", 8)
    c.drawString(m_left, y, "Part Number / Codice")
    c.drawString(m_left + (60 * mm), y, "Quantità Usata")
    c.drawString(m_left + (100 * mm), y, "Data Associazione")

    c.line(m_left, y - 2, m_right, y - 2)

    c.setFont("Helvetica", 8)
    if componenti:
        for comp in componenti:
            y -= 5 * mm
            if y < 35 * mm:
                c.showPage()
                y = altezza_pt - 20 * mm
                c.setFont("Helvetica", 8)
            pn = str(comp.get('pn_codice', 'N/D'))
            qta = str(comp.get('quantita_usata', '1'))
            dt = str(comp.get('data_associazione', 'N/D'))
            c.drawString(m_left, y, pn)
            c.drawString(m_left + (60 * mm), y, qta)
            c.drawString(m_left + (100 * mm), y, dt)
    else:
        y -= 5 * mm
        c.drawString(m_left, y, "Nessun componente tracciato direttamente.")

    # 4. Tracciabilità Storico Fasi Produzione
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(m_left, y, "STORICO AVANZAMENTO E CONTROLLI")

    y -= 6 * mm
    c.setFont("Helvetica-Bold", 8)
    c.drawString(m_left, y, "Fase Destinazione")
    c.drawString(m_left + (60 * mm), y, "Operatore")
    c.drawString(m_left + (110 * mm), y, "Data / Ora")

    c.line(m_left, y - 2, m_right, y - 2)

    c.setFont("Helvetica", 8)
    if storico_fasi:
        for fase in storico_fasi:
            y -= 5 * mm
            if y < 35 * mm:
                c.showPage()
                y = altezza_pt - 20 * mm
                c.setFont("Helvetica", 8)
            c.drawString(m_left, y, str(fase.get('fase_destinazione', 'N/D')))
            c.drawString(m_left + (60 * mm), y, str(fase.get('operatore', 'N/D')))
            c.drawString(m_left + (110 * mm), y, str(fase.get('data_ora', 'N/D')))
    else:
        y -= 5 * mm
        c.drawString(m_left, y, "Nessun passaggio di fase registrato.")

    # 5. Esito Collaudo & Firma
    y -= 15 * mm
    if y < 40 * mm:
        c.showPage()
        y = altezza_pt - 35 * mm

    c.setLineWidth(0.5)
    c.line(m_left, y, m_right, y)

    y -= 6 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(m_left, y, "ESITO COLLAUDO:")
    
    has_critical_rma = any(r.get('stato') == 'Scartato' for r in segnalazioni_rma)
    if has_critical_rma:
        c.setFillColorRGB(0.8, 0, 0)
        c.drawString(m_left + (35 * mm), y, "NON CONFORME / SCARTATO")
    else:
        c.setFillColorRGB(0, 0.5, 0)
        c.drawString(m_left + (35 * mm), y, "CONFORME / APPROVATO")

    c.setFillColorRGB(0, 0, 0)

    # Firma
    y -= 12 * mm
    c.setFont("Helvetica", 8)
    c.drawString(m_left, y, "Firma Operatore / Collaudatore: _______________________")
    c.drawString(m_right - (60 * mm), y, "Timbro Controllo Qualità: _______________________")

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.getvalue()

def genera_pdf_report_rma(
    rma_info: dict,
    interventi: list,
    ricambi: list,
    nome_azienda: str = "MY COMPANY SRL"
) -> bytes:
    """
    Genera un Report Ufficiale di Intervento / Riparazione RMA in formato A4 (PDF)
    da consegnare al cliente.
    """
    from reportlab.lib.pagesizes import A4
    
    larghezza_pt, altezza_pt = A4
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    m_left = 15 * mm
    m_right = larghezza_pt - (15 * mm)
    m_top = altezza_pt - (15 * mm)

    # 1. Intestazione & Header Documento
    c.setFont("Helvetica-Bold", 16)
    c.drawString(m_left, m_top, nome_azienda.upper())
    
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(m_right, m_top, "RAPPORTO DI INTERVENTO RMA")

    c.setFont("Helvetica", 9)
    c.drawString(m_left, m_top - (5 * mm), "Scheda Tecnica di Riparazione e Assistenza")

    c.setLineWidth(1)
    c.line(m_left, m_top - (8 * mm), m_right, m_top - (8 * mm))

    # 2. Dettagli RMA & Prodotto
    y = m_top - (18 * mm)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(m_left, y, "INFORMAZIONI GENERALI")

    c.setFont("Helvetica", 9)
    y -= 5 * mm
    c.drawString(m_left, y, f"Codice RMA: {rma_info.get('codice_rma', 'N/D')}")
    c.drawString(m_left + (80 * mm), y, f"Data Segnalazione: {rma_info.get('data_segnalazione', 'N/D')}")

    y -= 5 * mm
    c.drawString(m_left, y, f"Seriale Centralina: {rma_info.get('serial_centralina') or 'N/D'}")
    c.drawString(m_left + (80 * mm), y, f"Cliente: {rma_info.get('ragione_sociale') or 'N/D'}")

    y -= 5 * mm
    c.drawString(m_left, y, f"Origine: {rma_info.get('origine', 'N/D')}")
    c.drawString(m_left + (80 * mm), y, f"Stato Finale: {rma_info.get('stato', 'N/D')}")

    # Integrazione QR Code per tracciabilità
    try:
        qr_buf = genera_qr_code_image(str(rma_info.get('codice_rma', 'RMA')))
        qr_image = ImageReader(qr_buf)
        c.drawImage(qr_image, m_right - (25 * mm), m_top - (35 * mm), width=25 * mm, height=25 * mm)
    except Exception:
        pass

    # Linea separatrice
    y -= 5 * mm
    c.setLineWidth(0.5)
    c.line(m_left, y, m_right, y)

    # 3. Anomalia Segnalata
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(m_left, y, "SINTOMO RISCONTRATO / ANOMALIA SEGNALATA")
    
    y -= 5 * mm
    c.setFont("Helvetica", 9)
    sintomo_txt = rma_info.get('sintomo_guasto', 'Nessuna descrizione inserita.')
    c.drawString(m_left, y, sintomo_txt[:90])

    y -= 5 * mm
    c.line(m_left, y, m_right, y)

    # 4. Diagnosi Tecnica & Azioni Eseguite
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(m_left, y, "LOG INTERVENTI TECNICI & DIAGNOSI")

    y -= 6 * mm
    c.setFont("Helvetica-Bold", 8)
    c.drawString(m_left, y, "Tecnico")
    c.drawString(m_left + (30 * mm), y, "Diagnosi Riscontrata")
    c.drawString(m_left + (90 * mm), y, "Azioni Correttive")
    c.drawString(m_left + (150 * mm), y, "Data")

    c.line(m_left, y - 2, m_right, y - 2)

    c.setFont("Helvetica", 8)
    if interventi:
        for it in interventi:
            y -= 5 * mm
            if y < 40 * mm:
                c.showPage()
                y = altezza_pt - 20 * mm
                c.setFont("Helvetica", 8)
            
            tec = str(it.get('tecnico', 'N/D'))[:15]
            diag = str(it.get('diagnosi', 'N/D'))[:35]
            az = str(it.get('azioni_eseguite', 'N/D'))[:35]
            dt = str(it.get('data_intervento', 'N/D'))[:10]

            c.drawString(m_left, y, tec)
            c.drawString(m_left + (30 * mm), y, diag)
            c.drawString(m_left + (90 * mm), y, az)
            c.drawString(m_left + (150 * mm), y, dt)
    else:
        y -= 5 * mm
        c.drawString(m_left, y, "Nessun intervento registrato.")

    y -= 5 * mm
    c.line(m_left, y, m_right, y)

    # 5. Componenti e Ricambi Sostituiti
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(m_left, y, "COMPONENTI / RICAMBI SOSTITUITI")

    y -= 6 * mm
    c.setFont("Helvetica-Bold", 8)
    c.drawString(m_left, y, "Part Number / Codice Componente")
    c.drawString(m_left + (80 * mm), y, "Quantità")
    c.drawString(m_left + (120 * mm), y, "Data Sostituzione")

    c.line(m_left, y - 2, m_right, y - 2)

    c.setFont("Helvetica", 8)
    if ricambi:
        for rc in ricambi:
            y -= 5 * mm
            if y < 40 * mm:
                c.showPage()
                y = altezza_pt - 20 * mm
                c.setFont("Helvetica", 8)
            
            pn = str(rc.get('pn_componente', 'N/D'))
            qta = str(rc.get('quantita', '1'))
            dt = str(rc.get('data_utilizzo', 'N/D'))[:10]

            c.drawString(m_left, y, pn)
            c.drawString(m_left + (80 * mm), y, qta)
            c.drawString(m_left + (120 * mm), y, dt)
    else:
        y -= 5 * mm
        c.drawString(m_left, y, "Nessun ricambio materiale sostituito.")

    # 6. Esito Finale & Firma
    y -= 15 * mm
    if y < 45 * mm:
        c.showPage()
        y = altezza_pt - 35 * mm

    c.setLineWidth(0.5)
    c.line(m_left, y, m_right, y)

    y -= 6 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(m_left, y, "ESITO RIPARAZIONE:")
    
    stato_final = rma_info.get('stato', 'In Lavorazione')
    if stato_final == 'Riparato':
        c.setFillColorRGB(0, 0.5, 0)
        c.drawString(m_left + (40 * mm), y, "RIPARATO E VERIFICATO")
    elif stato_final == 'Scartato':
        c.setFillColorRGB(0.8, 0, 0)
        c.drawString(m_left + (40 * mm), y, "NON RIPARABILE / SCARTATO")
    else:
        c.setFillColorRGB(0.8, 0.5, 0)
        c.drawString(m_left + (40 * mm), y, "IN LAVORAZIONE")

    c.setFillColorRGB(0, 0, 0)

    # Firma
    y -= 15 * mm
    c.setFont("Helvetica", 8)
    c.drawString(m_left, y, "Firma Tecnico Riparatore: _______________________")
    c.drawString(m_right - (65 * mm), y, "Timbro Controllo Qualità: _______________________")

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.getvalue()

def genera_pdf_mancanti(
    modello_sel: str,
    qta_prod: int,
    lista_mancanti: list,
    nome_azienda: str = "MY COMPANY SRL"
) -> bytes:
    """
    Genera un Report Lista Mancanti per la Produzione in formato A4 (PDF) usando ReportLab.
    """
    from reportlab.lib.pagesizes import A4
    
    larghezza_pt, altezza_pt = A4
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    m_left = 15 * mm
    m_right = larghezza_pt - (15 * mm)
    m_top = altezza_pt - (15 * mm)

    # 1. Header Documento
    c.setFont("Helvetica-Bold", 16)
    c.drawString(m_left, m_top, nome_azienda.upper())
    
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(m_right, m_top, "LISTA MANCANTI PRODUZIONE")

    c.setFont("Helvetica", 9)
    c.drawString(m_left, m_top - (5 * mm), "Report Fabbisogno Componenti e Carenze Magazzino")

    c.setLineWidth(1)
    c.line(m_left, m_top - (8 * mm), m_right, m_top - (8 * mm))

    # 2. Dettagli Modello e Lotto
    y = m_top - (18 * mm)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(m_left, y, "PARAMETRI DI PRODUZIONE")

    c.setFont("Helvetica", 9)
    y -= 5 * mm
    c.drawString(m_left, y, f"Modello Centralina: {modello_sel}")
    c.drawString(m_left + (90 * mm), y, f"Quantità da Produrre: {qta_prod} pz")

    y -= 5 * mm
    c.drawString(m_left, y, f"Data Generazione: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    y -= 5 * mm
    c.setLineWidth(0.5)
    c.line(m_left, y, m_right, y)

    # 3. Tabella Mancanti
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(m_left, y, "ELENCO COMPONENTI DA REINTEGRARE / ORDINARE")

    y -= 6 * mm
    c.setFont("Helvetica-Bold", 8)
    c.drawString(m_left, y, "Part Number / Codice")
    c.drawString(m_left + (55 * mm), y, "Req. Unità")
    c.drawString(m_left + (85 * mm), y, "Giacenza")
    c.drawString(m_left + (115 * mm), y, "Fabbisogno")
    c.drawString(m_left + (150 * mm), y, "Pz Mancanti")

    c.line(m_left, y - 2, m_right, y - 2)

    c.setFont("Helvetica", 8)
    if lista_mancanti:
        for item in lista_mancanti:
            y -= 5 * mm
            if y < 25 * mm:
                c.showPage()
                y = altezza_pt - 20 * mm
                c.setFont("Helvetica", 8)

            pn = str(item.get('pn_componente', 'N/D'))
            req = str(item.get('quantita_richiesta', '0'))
            giac = str(item.get('giacenza', '0'))
            fab = str(item.get('fabbisogno_totale', '0'))
            manc = str(item.get('mancanti', '0'))

            c.drawString(m_left, y, pn)
            c.drawString(m_left + (55 * mm), y, req)
            c.drawString(m_left + (85 * mm), y, giac)
            c.drawString(m_left + (115 * mm), y, fab)
            
            # Evidenzia in grassetto i pezzi mancanti
            c.setFont("Helvetica-Bold", 8)
            c.drawString(m_left + (150 * mm), y, manc)
            c.setFont("Helvetica", 8)
    else:
        y -= 5 * mm
        c.drawString(m_left, y, "Nessun componente mancante.")

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.getvalue()
