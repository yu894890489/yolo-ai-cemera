-- BE-M1-B (YU-46) / YU-58 (二期 Stage1): alarms table for the small_crop chain.
--
-- event_id is the 3s-window dedup key (hash(task_id+roi+class+floor(ts/3s)));
-- the UNIQUE constraint makes a duplicate INSERT raise IntegrityError, which
-- MySQLAlarmRepo.create() treats as "already recorded" and returns None.
--
-- business_line segments rows by tenant (phase1 / phase2); defaults to phase1
-- so existing one-tenant deployments keep working without backfill.

CREATE TABLE IF NOT EXISTS alarms (
    id                CHAR(32)     NOT NULL,
    event_id          VARCHAR(64)  NOT NULL,
    task_id           VARCHAR(64)  NOT NULL,
    rule_id           VARCHAR(64)  NOT NULL DEFAULT 'demo',
    class             VARCHAR(64)  NOT NULL DEFAULT '',
    score             DOUBLE       NOT NULL DEFAULT 0,
    bbox              VARCHAR(128) NOT NULL DEFAULT '',
    roi               VARCHAR(128) NOT NULL DEFAULT '',
    mode              VARCHAR(32)  NOT NULL DEFAULT 'default',
    vlm_status        VARCHAR(32)  NOT NULL DEFAULT '',
    vlm_reason        TEXT         NULL,
    vlm_confidence    DOUBLE       NOT NULL DEFAULT 0,
    screenshot_object VARCHAR(255) NULL,
    ts_ms             BIGINT       NOT NULL DEFAULT 0,
    business_line     VARCHAR(64)  NOT NULL DEFAULT 'phase1',
    created_at        VARCHAR(32)  NOT NULL DEFAULT '',
    PRIMARY KEY (id),
    UNIQUE KEY uq_event_id (event_id),
    KEY idx_task_ts (task_id, ts_ms),
    KEY idx_ts (ts_ms),
    KEY idx_business_line (business_line)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
