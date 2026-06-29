-- BE-M1-D (YU-56) / YU-58 (二期 Stage1): analysis tasks table for MySQLTaskRepo.
-- Columns mirror app/api/repository.py::MySQLTaskRepo and app/api/models.py::Task.
-- business_line segments rows by tenant (phase1 / phase2); defaults to phase1
-- so existing one-tenant deployments keep working without backfill.

CREATE TABLE IF NOT EXISTS tasks (
    id             CHAR(12)     NOT NULL,
    source_id      CHAR(12)     NOT NULL DEFAULT '',
    algorithm_id   VARCHAR(64)  NOT NULL DEFAULT '',
    roi            TEXT         NULL,
    prompt         TEXT         NULL,
    confidence     DOUBLE       NOT NULL DEFAULT 0.5,
    status         VARCHAR(32)  NOT NULL DEFAULT 'created',
    error_message  TEXT         NULL,
    business_line  VARCHAR(64)  NOT NULL DEFAULT 'phase1',
    created_at     VARCHAR(32)  NOT NULL DEFAULT '',
    updated_at     VARCHAR(32)  NOT NULL DEFAULT '',
    PRIMARY KEY (id),
    KEY idx_source (source_id),
    KEY idx_status (status),
    KEY idx_business_line (business_line)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
