-- BE-M1-D (YU-56): video sources table for MySQLSourceRepo (API_REPO=mysql).
-- Columns mirror app/api/repository.py::MySQLSourceRepo and app/api/models.py::Source.

CREATE TABLE IF NOT EXISTS sources (
    id          CHAR(12)     NOT NULL,
    name        VARCHAR(128) NOT NULL DEFAULT '',
    protocol    VARCHAR(32)  NOT NULL DEFAULT '',
    address     VARCHAR(512) NOT NULL DEFAULT '',
    enabled     TINYINT(1)   NOT NULL DEFAULT 1,
    note        VARCHAR(512) NOT NULL DEFAULT '',
    created_at  VARCHAR(32)  NOT NULL DEFAULT '',
    updated_at  VARCHAR(32)  NOT NULL DEFAULT '',
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
