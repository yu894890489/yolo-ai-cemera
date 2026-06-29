# 最简部署步骤（M1 一键部署）

> 取代旧的多节手工流程。前提：部署主机能访问共享环境 `192.168.10.83`（YU-39：MySQL/MinIO/MediaMTX/Chroma 已就绪），并装有 Docker + Docker Compose v2。

## 1. 配置（只需填 2 组密钥）

```bash
cd backend
cp .env.example .env
```

编辑 `.env`，只需填这两组（其余已预填共享环境端点）：

- `VLM_API_KEY` — 云端 VLM 的 Bearer Token（留空则走 small_only，不做 VLM 判定）
- `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` — MinIO 凭据

如 MySQL 口令与默认不同，再改 `MYSQL_PASSWORD`。

## 2. 一键起栈

```bash
docker compose up -d --build
```

启动顺序自动编排：`redis` 起 → `migrate`（在共享 MySQL 建 `sources/tasks/alarms/vlm_endpoints` 表，幂等）跑完 → `flask` + `producer/consumer/saver` 起。`migrate` 跑完前应用不会启动，首个请求不会撞到缺表。

## 3. 验证

```bash
docker compose ps                                   # 全部 healthy/running，migrate 为 exited(0)
curl http://<host>:8010/healthz                     # {"status":"ok"}
curl http://<host>:9101/metrics                     # producer
curl http://<host>:9102/metrics                     # consumer
curl http://<host>:9103/metrics                     # saver
```

- 前端页面（Flask 同源托管，无需 `pnpm preview`）：
  - 创建任务 `http://<host>:8010/`
  - 监控预览 `http://<host>:8010/monitor`
  - 实时告警 `http://<host>:8010/alarms`
- 冒烟：建视频源 → 建 `small_crop` 任务 → 启停；`API_REPO=mysql`（默认）下 `GET /api/alarms` 能读到 Saver 写入。

## 4. 可选：GPU + 真实 YOLO

默认 consumer 走 CPU stub。挂主机 NVIDIA GPU（如 RTX 2060，需 NVIDIA Container Toolkit）跑真实 YOLO：

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

该 override 仅把 consumer 换成 CUDA + ultralytics 镜像并预留 1 张 GPU，并自动设 `YOLO_DEVICE=cuda`。

## 端口与开关速查

| 项 | 默认 | 说明 |
| --- | --- | --- |
| Flask | `8010` | 避开被占用的 8000，可改 `FLASK_PORT` |
| 三 worker metrics | `9101/9102/9103` | |
| `API_REPO` | `mysql` | Flask 与 Saver 共享持久化（改 `memory` 仅单机内存） |
| HLS 预览基址 | `MEDIAMTX_HLS_BASE_URL` | preview_url = `<base>/{task_id}/index.m3u8` |

## 安全说明（demo 范畴）

弱默认凭据、明文 env、无鉴权页面，仅适用于内网演示；商用加固不在本里程碑范围。密钥仅经 env 注入，不入库、不入仓。
