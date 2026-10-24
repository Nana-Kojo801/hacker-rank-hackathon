-- Captured at: 2026-06-20T08:00:00Z
-- Database topology: primary_only
BEGIN TRANSACTION;
CREATE TABLE customer_profiles_primary (resource_id TEXT PRIMARY KEY, user_id TEXT, full_name TEXT, email TEXT, phone TEXT, account_status TEXT, updated_at TEXT);
INSERT INTO "customer_profiles_primary" VALUES('account_9100','user_999','Other Person','other@example.test','+1','ACTIVE','2026-06-19T00:00:00Z');
COMMIT;
