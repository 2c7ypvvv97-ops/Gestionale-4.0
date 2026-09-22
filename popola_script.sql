-- ==========================================
-- PULIZIA TABELLE (In ordine per evitare FK errors)
-- ==========================================
DELETE FROM storico_fasi;
DELETE FROM schede;
DELETE FROM schede_magazzino;
DELETE FROM centraline;
DELETE FROM commesse;
DELETE FROM config_tipologie;
DELETE FROM distinte_basi;
DELETE FROM magazzino_quantita;
DELETE FROM part_numbers;
DELETE FROM clienti;

-- ==========================================
-- 1. POPOLAMENTO CONFIGURAZIONE TIPOLOGIE
-- ==========================================
INSERT INTO config_tipologie (tipologia, numero_partenza) VALUES 
('MOD_PWR_2026', 100),
('CENTRALINA_SLIM', 500),
('BOX_SENSOR_PRO', 1000);

-- ==========================================
-- 2. POPOLAMENTO CLIENTE & PART NUMBERS
-- ==========================================
INSERT INTO clienti (codice_cliente, ragione_sociale, referente, note) VALUES
('CLI-001', 'ACME Industries S.r.l.', 'Ing. Mario Rossi', 'Contatti: ordini@acme.it | Note: Consegna Cancello B'),
('CLI-002', 'TechPro Automotive Gmbh', 'Klaus Weber', 'Contatti: k.weber@techpro.de | Note: Spedizione Express'),
('CLI-003', 'Elettronica Veneta SpA', 'Dott.ssa Elena Bianchi', 'Contatti: acquisti@elven.it | Note: Imballo Pallet');

INSERT INTO part_numbers (pn_codice, descrizione, ubicazione) VALUES
('CPU_K', 'Processore di Controllo Principale', 'SCAFFALE-A1'),
('ALIM_K', 'Modulo Alimentazione 12V/24V', 'SCAFFALE-A2'),
('SENS_K', 'Sensore Termico Integrato', 'SCAFFALE-B1'),
('DISP_LCD_01', 'Display LCD TFT 4.3 Pollici', 'SCAFFALE-B2'),
('REL_DRV_02', 'Driver Relè Industriale High Power', 'SCAFFALE-C1');

-- ==========================================
-- 3. POPOLAMENTO DISTINTE BASI (BOM)
-- ==========================================
-- BOM per MOD_PWR_2026
INSERT INTO distinte_basi (modello, pn_componente, quantita_richiesta) VALUES
('MOD_PWR_2026', 'CPU_K', 1),
('MOD_PWR_2026', 'ALIM_K', 1),
('MOD_PWR_2026', 'SENS_K', 2);

-- BOM per CENTRALINA_SLIM
INSERT INTO distinte_basi (modello, pn_componente, quantita_richiesta) VALUES
('CENTRALINA_SLIM', 'CPU_K', 1),
('CENTRALINA_SLIM', 'ALIM_K', 1),
('CENTRALINA_SLIM', 'DISP_LCD_01', 1);

-- BOM per BOX_SENSOR_PRO
INSERT INTO distinte_basi (modello, pn_componente, quantita_richiesta) VALUES
('BOX_SENSOR_PRO', 'CPU_K', 1),
('BOX_SENSOR_PRO', 'SENS_K', 4),
('BOX_SENSOR_PRO', 'REL_DRV_02', 2);

-- ==========================================
-- 4. POPOLAMENTO MAGAZZINO GIACENZE
-- ==========================================
INSERT INTO magazzino_quantita (pn_codice, quantita_disponibile, ubicazione, operatore, data_ultimo_carico) VALUES
('CPU_K', 45, 'SCAFFALE-A1', 'LUIGI_M', '2026-09-01 08:30:00'),
('ALIM_K', 30, 'SCAFFALE-A2', 'LUIGI_M', '2026-09-01 08:35:00'),
('SENS_K', 18, 'SCAFFALE-B1', 'MARCO_B', '2026-09-02 09:15:00'), -- Collo di bottiglia per MOD_PWR_2026 (max 9 pz)
('DISP_LCD_01', 12, 'SCAFFALE-B2', 'MARCO_B', '2026-09-03 11:20:00'),
('REL_DRV_02', 50, 'SCAFFALE-C1', 'LUIGI_M', '2026-09-04 14:00:00');

-- ==========================================
-- 5. POPOLAMENTO COMMESSE
-- ==========================================
INSERT INTO commesse (codice_commessa, codice_cliente, modello_centralina, quantita_totale, stato, data_creazione) VALUES
('C2026-001', 'CLI-001', 'MOD_PWR_2026', 10, 'In Produzione', '2026-09-05 09:00:00'),
('C2026-002', 'CLI-002', 'CENTRALINA_SLIM', 5, 'Aperta', '2026-09-06 10:30:00'),
('C2026-003', 'CLI-003', 'BOX_SENSOR_PRO', 20, 'Aperta', '2026-09-07 08:00:00');

-- ==========================================
-- 6. POPOLAMENTO CENTRALINE E STORICO FASI
-- ==========================================
-- Centraline della commessa C2026-001
INSERT INTO centraline (serial_centralina, tipologia, serial_num, commessa_padre, fase_attuale, note, data_creazione) VALUES
('MOD_PWR_2026-100', 'MOD_PWR_2026', 100, 'C2026-001', 'Collaudo Superato', 'Assemblaggio ok', '2026-09-05 10:00:00'),
('MOD_PWR_2026-101', 'MOD_PWR_2026', 101, 'C2026-001', 'Assemblaggio Componenti', 'In lavorazione banco 2', '2026-09-05 11:30:00'),
('MOD_PWR_2026-102', 'MOD_PWR_2026', 102, 'C2026-001', 'In attesa componenti', 'Falta sensori', '2026-09-06 14:20:00');

-- Audit Trail (Storico Fasi)
INSERT INTO storico_fasi (serial_centralina, fase_destinazione, operatore, data_ora) VALUES
('MOD_PWR_2026-100', 'Registrazione Seriale', 'SYSTEM', '2026-09-05 10:00:00'),
('MOD_PWR_2026-100', 'Assemblaggio Componenti', 'GIOVANNI_V', '2026-09-05 10:45:00'),
('MOD_PWR_2026-100', 'Collaudo Superato', 'ALBERTO_T', '2026-09-05 14:10:00'),

('MOD_PWR_2026-101', 'Registrazione Seriale', 'SYSTEM', '2026-09-05 11:30:00'),
('MOD_PWR_2026-101', 'Assemblaggio Componenti', 'GIOVANNI_V', '2026-09-05 12:00:00'),

('MOD_PWR_2026-102', 'Registrazione Seriale', 'SYSTEM', '2026-09-06 14:20:00');

-- ==========================================
-- 7. SCHEDE E SCHEDE MAGAZZINO (QR & Sotto-schede)
-- ==========================================
INSERT INTO schede_magazzino (qr_scheda, codice_commessa, data_carico) VALUES
('QR-BOARD-9001', 'C2026-001', '2026-09-05 08:00:00'),
('QR-BOARD-9002', 'C2026-001', '2026-09-05 08:00:00'),
('QR-BOARD-9003', 'C2026-001', '2026-09-05 08:00:00');

INSERT INTO schede (qr_scheda, serial_centralina, data_association) VALUES
('QR-BOARD-9001', 'MOD_PWR_2026-100', '2026-09-05 10:15:00'),
('QR-BOARD-9002', 'MOD_PWR_2026-101', '2026-09-05 11:45:00');