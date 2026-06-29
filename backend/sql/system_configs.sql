-- BE-M1-D (YU-56): runtime-tunable config overlay (optional).
--
-- Read by app/common/config.py::fetch_mysql_overlay as a flat key/value bag.
-- Missing table is non-fatal (loader degrades to env-only), so this migration
-- is optional — created here only to make the overlay path explicit.

CREATE TABLE IF NOT EXISTS system_configs (
    `key`      VARCHAR(128) NOT NULL,
    `value`    TEXT         NOT NULL,
    updated_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
