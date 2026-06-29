-- YU-58 (二期 Stage1): users table for shared-user + business_line isolation.
--
-- One user may own rows in sources/tasks/alarms; business_line segments the
-- data so phase1 (一期) and phase2 (二期) tenants share code but not rows.
-- password_hash is a bcrypt-style string; the API layer verifies via
-- app.api.auth. The first user + business_line convention is documented in
-- backend/docs/business_line.md.

CREATE TABLE IF NOT EXISTS users (
    id            CHAR(32)     NOT NULL,
    username      VARCHAR(128) NOT NULL,
    password_hash VARCHAR(255) NOT NULL DEFAULT '',
    business_line VARCHAR(64)  NOT NULL DEFAULT 'phase1',
    enabled       TINYINT(1)   NOT NULL DEFAULT 1,
    created_at    VARCHAR(32)  NOT NULL DEFAULT '',
    PRIMARY KEY (id),
    UNIQUE KEY uq_username (username),
    KEY idx_business_line (business_line)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
