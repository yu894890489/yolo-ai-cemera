#!/usr/bin/env bash
#
# 把 frontend/ 的构建产物部署到 Flask 项目的 static/ 目录。
#
# 默认假设：构建产物已经位于 app/static/frontend/（Vite 配置直接输出到这里），
# 此脚本负责：
#   1) 校验产物完整性（manifest.json + 至少一个 entry bundle）
#   2) 写入 app/static/frontend/BUILD_INFO（commit / 构建时间）
#   3) 可选：把产物 rsync 到部署主机（通过环境变量 DEPLOY_HOST / DEPLOY_PATH 启用）
#
# 在 CI 中由 .github/workflows/frontend-ci.yml 的 deploy-static job 调用。

set -euo pipefail

# 切到 repo root（脚本可能从任意位置调用）
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

DIST_DIR="app/static/frontend"
MANIFEST="${DIST_DIR}/manifest.json"

echo "[deploy-to-flask] repo root: ${REPO_ROOT}"
echo "[deploy-to-flask] dist dir : ${DIST_DIR}"

if [[ ! -d "${DIST_DIR}" ]]; then
  echo "[deploy-to-flask] FATAL: dist dir not found. Run 'pnpm build' in frontend/ first." >&2
  exit 1
fi

if [[ ! -f "${MANIFEST}" ]]; then
  echo "[deploy-to-flask] FATAL: manifest.json missing in ${DIST_DIR}." >&2
  exit 1
fi

entry_count=$(grep -c '"file":' "${MANIFEST}" || true)
if [[ "${entry_count}" -lt 1 ]]; then
  echo "[deploy-to-flask] FATAL: manifest.json has no entries." >&2
  exit 1
fi
echo "[deploy-to-flask] manifest OK (${entry_count} entries)"

GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
BUILD_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
cat > "${DIST_DIR}/BUILD_INFO" <<EOF
commit=${GIT_SHA}
built_at=${BUILD_TS}
EOF
echo "[deploy-to-flask] BUILD_INFO written (commit=${GIT_SHA}, built_at=${BUILD_TS})"

# 可选 rsync 到部署主机（v1 demo 主机由父 issue metadata 提供）
if [[ -n "${DEPLOY_HOST:-}" && -n "${DEPLOY_PATH:-}" ]]; then
  echo "[deploy-to-flask] rsync to ${DEPLOY_HOST}:${DEPLOY_PATH}"
  rsync -avz --delete \
    "${DIST_DIR}/" \
    "${DEPLOY_HOST}:${DEPLOY_PATH}/"
else
  echo "[deploy-to-flask] DEPLOY_HOST / DEPLOY_PATH 未设置，跳过远端推送（仅本地校验）"
fi

echo "[deploy-to-flask] done."
