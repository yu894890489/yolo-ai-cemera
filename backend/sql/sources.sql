-- BE-M1-D (YU-56) / YU-58 (二期 Stage1): video sources table for MySQLSourceRepo.
-- Columns mirror app/api/repository.py::MySQLSourceRepo and app/api/models.py::Source.
-- business_line segments rows by tenant (phase1 / phase2); defaults to phase1
-- so existing one-tenant deployments keep working without backfill.

CREATE TABLE IF NOT EXISTS sources (
    id             CHAR(12)     NOT NULL,
    name           VARCHAR(128) NOT NULL DEFAULT '',
    protocol       VARCHAR(32)  NOT NULL DEFAULT '',
    address        VARCHAR(512) NOT NULL DEFAULT '',
    enabled        TINYINT(1)   NOT NULL DEFAULT 1,
    note           VARCHAR(512) NOT NULL DEFAULT '',
    business_line  VARCHAR(64)  NOT NULL DEFAULT 'phase1',
    created_at     VARCHAR(32)  NOT NULL DEFAULT '',
    updated_at     VARCHAR(32)  NOT NULL DEFAULT '',
    PRIMARY KEY (id),
    KEY idx_business_line (business_line)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
