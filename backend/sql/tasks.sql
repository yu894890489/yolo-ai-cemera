-- BE-M1-D (YU-56): analysis tasks table for MySQLTaskRepo (API_REPO=mysql).
-- Columns mirror app/api/repository.py::MySQLTaskRepo and app/api/models.py::Task.

CREATE TABLE IF NOT EXISTS tasks (
    id            CHAR(12)     NOT NULL,
    source_id     CHAR(12)     NOT NULL DEFAULT '',
    algorithm_id  VARCHAR(64)  NOT NULL DEFAULT '',
    roi           TEXT         NULL,
    prompt        TEXT         NULL,
    confidence    DOUBLE       NOT NULL DEFAULT 0.5,
    status        VARCHAR(32)  NOT NULL DEFAULT 'created',
    error_message TEXT         NULL,
    created_at    VARCHAR(32)  NOT NULL DEFAULT '',
    updated_at    VARCHAR(32)  NOT NULL DEFAULT '',
    PRIMARY KEY (id),
    KEY idx_source (source_id),
    KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
