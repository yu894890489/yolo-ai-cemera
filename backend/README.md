# Backend — M0-S3 三进程骨架 (YU-38)

YOLO + VLM 协同视频分析系统的后端骨架。本仓库交付 M0 阶段的最小可运行链路：

```
Producer ──► Redis Stream frame:{task_id} ──► Consumer (YOLO) ──► Redis Stream alarm:raw ──► Saver (MySQL + MinIO + WebSocket)
```

三个 worker 独立进程，崩溃互不影响；Flask 主进程提供 HTTP + WebSocket。

## 必交付状态

| 必交付 | 状态 |
| --- | --- |
| 三进程骨架（Producer / Consumer / Saver 独立可重启） | OK |
| Redis Stream + Consumer Group + XACK（零丢失） | OK |
| Prometheus `/metrics` 三端点 + 关键指标 | OK |
| 配置加载（MySQL `system_configs` + SIGHUP 热更） | OK（loader 接口就位，等 S2 schema 接表） |
| Docker Compose 一键启动 | OK |

## 目录

```
backend/
├── app/
│   ├── api/                 # Flask 主进程 (HTTP + WebSocket 广播)
│   ├── common/              # 公共组件：config / metrics / redis client / streams
│   ├── workers/             # 三个独立 worker 入口
│   │   ├── producer.py
│   │   ├── consumer.py
│   │   └── saver.py
│   └── __init__.py
├── tests/                   # pytest 单元 + 集成
├── docker/
│   ├── Dockerfile
│   └── prometheus.yml
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## Redis Stream 约定

| Stream | Producer | Consumer Group | 字段 |
| --- | --- | --- | --- |
| `frame:{task_id}` | Producer | `g:consumer` | `task_id`, `seq`, `ts_ms`, `frame_jpeg_b64` |
| `alarm:raw` | Consumer | `g:saver` | `task_id`, `rule_id`, `class`, `score`, `bbox`, `roi`, `ts_ms`, `mode`, `event_id`, `crop_jpeg_b64`, `vlm_status`, `vlm_reason`, `vlm_confidence` |
| `alarm:pushed` | Saver | (Push worker, M2) | `alarm_id`, `ts_ms` |

Consumer Group + `XACK`，重启 worker 不丢消息。

## M1 单路 `small_crop` 推理链 (YU-46)

```
Consumer: YOLO → 置信度/类别/ROI 过滤 → 裁剪 bbox → 云端 VLM 判定 → alarm:raw(crop_jpeg_b64)
Saver:    event_id 去重 → 裁剪图上传 MinIO → 写入 alarms 表 → ws:alarm 推送
```

- **检测过滤**：`task.confidence` 阈值 + `task.classes` 目标类别 + `task.roi` 区域三重过滤。
- **裁剪上传**：命中后只裁剪 bbox 区域，整帧不在 Saver 长驻；MinIO 对象键 `YYYY/MM/DD/{event_id}.jpg`，可追溯。
- **云端 VLM**：crop + prompt 送 VLM 层，返回结构化判定 `{is_alarm, reason, confidence, summary}`；`is_alarm=False` 不出告警。VLM 失败/队列高水位降级为 `small_only`。
- **去重落库**：`event_id = sha1(task_id|roi|class|floor(ts_ms/1000/3))`；Redis 短路 + `alarms.event_id` UNIQUE 双重保障 3 秒窗口去重。
- **推送**：WebSocket `/ws` 为主，SSE `/api/alarms/stream` 为兜底，二者共用 Redis `ws:alarm` 频道。

### 告警 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/alarms?limit=N` | 最近告警列表（按 `ts_ms` 倒序，`limit` 默认 50、上限 500） |
| GET | `/api/alarms/stream` | SSE 兜底推送（`text/event-stream`） |
| GET | `/ws` | WebSocket 主推送 |

`alarms` 表结构见 `sql/alarms.sql`（`API_REPO=mysql` 时启用 MySQL 持久化，否则用内存仓储）。


## Prometheus 指标

三个 worker 各暴露 `/metrics`：

| 指标 | 类型 | 来源 |
| --- | --- | --- |
| `frame_in_total{task_id}` | Counter | Producer / Consumer |
| `frame_drop_total{reason}` | Counter | Producer / Consumer |
| `yolo_latency_ms` | Histogram | Consumer |
| `alarm_emit_total{rule_id}` | Counter | Consumer / Saver |
| `stream_lag{stream}` | Gauge | Consumer / Saver |
| `process_up{worker}` | Gauge | 全部 |

Grafana dashboard 占位，M3 正式做面板。

## 配置加载

- 启动期从 MySQL `system_configs` 表加载键值对（schema 等待 S2 交付，loader 已留口）。
- SIGHUP 信号触发热更：`kill -HUP <pid>`，规则级热更放 M1。
- 凭据走环境变量，不进 issue/长描述。

## 启动

部署主机参见父 issue `YU-33` metadata：`docker_host`。

```bash
cp .env.example .env   # 在部署主机上编辑真实凭据
docker compose up -d --build
docker compose ps
```

验证：

```bash
curl http://<host>:9101/metrics  # producer
curl http://<host>:9102/metrics  # consumer
curl http://<host>:9103/metrics  # saver
```

杀任一 worker，Stream 数据不丢，重启后继续从最后 `XACK` 点消费。

## 跨端依赖

- **YU-39 / BE-M0-S5**：共享环境（Redis/MinIO/MediaMTX/Chroma），06-28 联调通。
- **S2 MySQL schema**：06-26 前交付，数据访问层等表落地后接通；本里程碑新增 `sql/alarms.sql`。
- **M1**：单路 `small_crop` 已接入此骨架（YU-46）。
