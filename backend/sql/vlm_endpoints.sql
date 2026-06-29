-- BE-M1-D (YU-56): cloud VLM provider endpoints.
--
-- Read by app/common/config.py::fetch_vlm_endpoints with this exact column
-- contract (ORDER BY priority ASC):
--   provider, endpoint_url, enabled, priority, timeout_ms, max_tokens
--
-- The bearer token is NOT stored here — it is injected via the VLM_API_KEY env
-- var at runtime. An empty/disabled table simply keeps the small_only path
-- (VLM judgment disabled), which is a valid default.

CREATE TABLE IF NOT EXISTS vlm_endpoints (
    id           INT          NOT NULL AUTO_INCREMENT,
    provider     VARCHAR(64)  NOT NULL,
    endpoint_url VARCHAR(512) NOT NULL,
    enabled      TINYINT(1)   NOT NULL DEFAULT 1,
    priority     INT          NOT NULL DEFAULT 100,
    timeout_ms   INT          NOT NULL DEFAULT 10000,
    max_tokens   INT          NOT NULL DEFAULT 512,
    PRIMARY KEY (id),
    KEY idx_priority (priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Example: enable an OpenAI-compatible vision endpoint (token via VLM_API_KEY env).
-- INSERT INTO vlm_endpoints (provider, endpoint_url, enabled, priority, timeout_ms, max_tokens)
-- VALUES ('qwen-vl', 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions', 1, 10, 30000, 512);
