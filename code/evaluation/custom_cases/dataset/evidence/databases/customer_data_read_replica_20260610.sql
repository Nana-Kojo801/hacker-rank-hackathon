-- Captured at: 2026-06-10T08:00:00Z
-- Database topology: read_replica
BEGIN TRANSACTION;
CREATE TABLE customer_data_primary (resource_id TEXT PRIMARY KEY, data_store TEXT, collection TEXT, payload TEXT);
CREATE TABLE customer_data_read_replica (resource_id TEXT PRIMARY KEY, data_store TEXT, collection TEXT, payload TEXT);
INSERT INTO "customer_data_primary" VALUES('audit_record_9101','security_service','security_audit_events','{"resource_id":"audit_record_9101","subject_reference":"user_901","event_name":"account_deletion_reviewed","retention_until":"2033-12-31T23:59:59Z"}');
INSERT INTO "customer_data_read_replica" VALUES('audit_record_9101','security_service','security_audit_events','{"resource_id":"audit_record_9101","subject_reference":"user_901","event_name":"account_deletion_reviewed","retention_until":"2033-12-31T23:59:59Z"}');
INSERT INTO "customer_data_read_replica" VALUES('account_9001','account_service','customer_profiles','{"resource_id":"account_9001","customer_reference":"user_901","full_name":"Ada Quartz","email":"ada.quartz@example.test","phone":"+1 555 0101","account_status":"ACTIVE"}');
INSERT INTO "customer_data_primary" VALUES('account_9999','account_service','customer_profiles','{"resource_id":"account_9999","customer_reference":"user_999","full_name":"Other Person","email":"other@example.test","phone":null,"account_status":"ACTIVE"}');
COMMIT;
