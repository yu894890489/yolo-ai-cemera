-- YU-58 (二期 Stage1): idempotent ALTER for deployments that already have the
-- phase1 schema in place. Fresh installs already get business_line via the
-- CREATE TABLE statements in sources.sql / tasks.sql / alarms.sql; this file
-- is a no-op there because apply_migrations() skips duplicate-column /
-- duplicate-key errors (pymysql codes 1060 / 1061).
--
-- Existing rows pick up DEFAULT 'phase1', which is the documented convention
-- for the one-tenant phase1 deployment (see backend/docs/business_line.md).

ALTER TABLE sources ADD COLUMN business_line VARCHAR(64) NOT NULL DEFAULT 'phase1';
ALTER TABLE sources ADD INDEX idx_business_line (business_line);
ALTER TABLE tasks ADD COLUMN business_line VARCHAR(64) NOT NULL DEFAULT 'phase1';
ALTER TABLE tasks ADD INDEX idx_business_line (business_line);
ALTER TABLE alarms ADD COLUMN business_line VARCHAR(64) NOT NULL DEFAULT 'phase1';
ALTER TABLE alarms ADD INDEX idx_business_line (business_line);
