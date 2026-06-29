# business_line 数据隔离约定 (YU-58 二期 Stage1)

## 背景

二期需求：共用用户体系、隔离光伏/电表业务数据。`business_line` 字段是
所有业务表 (`sources` / `tasks` / `alarms`) 的租户隔离键。

## 命名约定

| business_line | 含义 |
| --- | --- |
| `phase1` | 一期（默认值，所有现存数据自动归属 phase1） |
| `phase2` | 二期（新建用户/数据可分配到 phase2） |

新增业务线时使用小写 ASCII `snake_case`，避免在 URL / header / SQL 中转义。

## 列与索引

每张业务表新增：

```sql
business_line VARCHAR(64) NOT NULL DEFAULT 'phase1',
KEY idx_business_line (business_line)
```

`users` 表也带 `business_line`，决定该用户的查询可见范围。

## 迁移策略

- 全新部署：`CREATE TABLE IF NOT EXISTS` 直接带 `business_line` 列。
- 已部署 phase1 的环境：`add_business_line.sql` 通过 `ALTER TABLE ADD COLUMN`
  补列，存量行由 `DEFAULT 'phase1'` 自动回填。
- `apply_migrations()` 容忍 MySQL `1060 (Duplicate column)` / `1061 (Duplicate
  key name)`，因此 `add_business_line.sql` 在新环境上是幂等 no-op。

## 鉴权与查询过滤

API 入口由 `app/api/auth.py::init_auth` 注入 `before_request` 钩子：

1. `Authorization: Bearer <user_id>` —— 通过 `UserRepo.get_by_id` 解析用户，
   `g.business_line = user.business_line`。
2. `X-Business-Line: <name>` —— 仅当 `AUTH_TRUST_BUSINESS_LINE_HEADER=1` 时
   信任（用于内部脚本 / 测试）。
3. 都没有 —— 当 `AUTH_REQUIRE_AUTH=0`（默认）时降级到默认 `phase1`，保证
   phase1 现有 curl/worker 流程零改动；`AUTH_REQUIRE_AUTH=1` 时返回 401。

业务路由 (`sources` / `tasks` / `alarms`) 通过 `current_business_line()`
读取 `g.business_line`，并把它作为 `business_line` 过滤参数传给 Repo。
写入路径（如 `POST /sources`）会**强制把当前 `business_line` 盖到新行上**，
客户端无法跨租户写入。

## Worker 侧

`SaverWorker` 从 Redis 的 `task:{task_id}` 配置中读取 `business_line`（由
`/api/tasks/<id>/start` 经 `_config_value` 写入），并盖到 `Alarm` 行上。
找不到配置时（demo 任务或一期老 producer）退化为 `phase1`。

## 部署开关

| 环境变量 | 默认 | 含义 |
| --- | --- | --- |
| `AUTH_REQUIRE_AUTH` | `0` | `1` 时强制 token 鉴权，否则降级 phase1 |
| `AUTH_TRUST_BUSINESS_LINE_HEADER` | `0` | `1` 时接受 `X-Business-Line` 头覆盖 |

生产环境建议 `AUTH_REQUIRE_AUTH=1`，开发/测试可开启 header 信任以便快速切换租户。

## 登录

`POST /api/auth/login` body `{"username": "...", "password": "..."}`，
返回 `{"token": "<user_id>", "business_line": "phase1"}`。客户端把 `token`
作为后续请求的 `Authorization: Bearer <token>`。

> Stage1 的口令哈希使用盐化 SHA-256 (`hash_password` / `verify_password`)，
> 仅作骨架用途。生产上线前应替换为 bcrypt / argon2。
