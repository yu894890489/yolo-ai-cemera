# 部署脚本

## `deploy-to-flask.sh`

CI 在 `main` 合并后调用，把 `app/static/frontend/` 的 Vite 构建产物校验完整性后，
（可选）rsync 到 demo 主机的 Flask `static/` 目录。

### 校验项

1. 产物目录存在
2. `manifest.json` 存在且至少有一个 entry
3. 写入 `BUILD_INFO`：commit 短 hash + 构建时间（ISO-8601 UTC）

### 远端推送（可选）

通过环境变量启用：

```sh
DEPLOY_HOST=user@192.168.10.83 \
DEPLOY_PATH=/srv/yolo-vlm/app/static/frontend \
bash scripts/deploy-to-flask.sh
```

不设置任何 `DEPLOY_*` 时只做本地校验，CI 默认行为即如此。

### 凭据

SSH 凭据通过 GitHub Actions Secrets 注入（v1 demo 仅限内网，禁止外网暴露）。
设置示例：

- `DEPLOY_HOST`：`root@192.168.10.83`
- `DEPLOY_PATH`：`/srv/yolo-vlm/app/static/frontend`
- SSH key 走 `webfactory/ssh-agent` action 注入

> 真实凭据按父 issue (YU-33) metadata.docker_host 流转，**不要**写入仓库。
