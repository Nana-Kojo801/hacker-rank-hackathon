-- Captured at: 2026-07-02T08:00:00Z
-- Database topology: primary_only
BEGIN TRANSACTION;
CREATE TABLE customer_profiles_primary (resource_id TEXT PRIMARY KEY, user_id TEXT, full_name TEXT, email TEXT, phone TEXT, account_status TEXT, updated_at TEXT);
INSERT INTO "customer_profiles_primary" VALUES('account_9003','user_903','Chika Moss','chika.moss@example.test','+1 555 0103','ACTIVE','2026-07-01T00:00:00Z');
COMMIT;
