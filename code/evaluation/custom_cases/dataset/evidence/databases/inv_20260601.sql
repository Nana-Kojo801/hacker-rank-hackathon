-- Captured at: 2026-06-01T08:00:00Z
BEGIN TRANSACTION;
CREATE TABLE snapshot_scope (origin_system TEXT PRIMARY KEY, captured_at TEXT NOT NULL);
CREATE TABLE customer_profiles (resource_id TEXT PRIMARY KEY, customer_reference TEXT, full_name TEXT, email TEXT, phone TEXT, email_hash TEXT, account_status TEXT NOT NULL, updated_at TEXT NOT NULL);
INSERT INTO snapshot_scope VALUES ('account_service', '2026-06-01T08:00:00Z');
INSERT INTO customer_profiles VALUES ('account_9005', 'user_905', 'Esi Fig', 'esi.fig@example.test', NULL, NULL, 'ACTIVE', '2026-05-30T00:00:00Z');
COMMIT;
