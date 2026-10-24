-- Purchase orders for Lab 2. agentlab.procurement.create_database() loads this file.
CREATE TABLE suppliers (supplier_id TEXT PRIMARY KEY, name_th TEXT, name_en TEXT, tax_id TEXT);
CREATE TABLE purchase_orders (po_number TEXT PRIMARY KEY, supplier_id TEXT REFERENCES suppliers, po_date TEXT);
CREATE TABLE po_lines (po_number TEXT REFERENCES purchase_orders, item_code TEXT, description TEXT, qty INTEGER, unit_price REAL);
CREATE TABLE invoice_checks (invoice_no TEXT PRIMARY KEY, file TEXT, verdict TEXT, reason TEXT, checked_at TEXT);
INSERT INTO suppliers VALUES ('S001', 'บริษัท สยามเปเปอร์ จำกัด', 'Siam Paper Co., Ltd.', '0105551234567');
INSERT INTO suppliers VALUES ('S002', 'บริษัท บางกอกคลาวด์ จำกัด', 'Bangkok Cloud Co., Ltd.', '0105559876543');
INSERT INTO suppliers VALUES ('S003', 'บริษัท เน็ตแคร์ จำกัด', 'Netcare Co., Ltd.', '0105553344556');
INSERT INTO suppliers VALUES ('S004', 'บริษัท ออฟฟิศมาร์ท จำกัด', 'OfficeMart Co., Ltd.', '0105557788990');
INSERT INTO purchase_orders VALUES ('PO-2026-135', 'S001', '2026-09-25');
INSERT INTO po_lines VALUES ('PO-2026-135', 'P-A4-80', 'A4 paper 80 gsm (ream)', 50, 110.00);
INSERT INTO purchase_orders VALUES ('PO-2026-118', 'S001', '2026-10-07');
INSERT INTO po_lines VALUES ('PO-2026-118', 'T-85A', 'Laser toner 85A', 10, 1850.00);
INSERT INTO purchase_orders VALUES ('PO-7781', 'S002', '2026-10-03');
INSERT INTO po_lines VALUES ('PO-7781', 'GPU-M', 'GPU cloud credits (monthly)', 3, 12000.00);
INSERT INTO purchase_orders VALUES ('PO-2026-121', 'S004', '2026-10-12');
INSERT INTO po_lines VALUES ('PO-2026-121', 'CH-EC200', 'Ergonomic chair EC-200', 15, 3200.00);
INSERT INTO purchase_orders VALUES ('PO-2026-130', 'S003', '2026-10-01');
INSERT INTO po_lines VALUES ('PO-2026-130', 'NET-MNT', 'Network maintenance (monthly)', 1, 45000.00);
