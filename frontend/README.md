# FE-M0-D 通用组件库 + CI/部署占位

本目录由 FE-M0-A 创建（脚手架），FE-M0-D 在此基础上交付：

- 8 个高频通用组件，统一从 `@components/index` 导出
- 单页 `components-demo` 入口（独立 Vite bundle）+ Jinja2 模板，供后端挂到任意路由
- GitHub Actions CI（`.github/workflows/frontend-ci.yml`）：install + lint + typecheck + build
- `scripts/deploy-to-flask.sh`：CI 在 main 合并后，把构建产物校验完整性并（可选）rsync 到 demo 主机

## 关键路径

- 组件源码：`src/components/<name>/<name>.ts` + `<name>.scss`
- 组件库导出：`src/components/index.ts`
- Demo 页：`src/index.html` + `src/entries/components-demo.ts`
- Flask 模板：`templates/components_demo.html`
- 构建产物：`../app/static/frontend/`（由 `vite.config.ts` 控制）
- CI：`../.github/workflows/frontend-ci.yml`
- 部署脚本：`../scripts/deploy-to-flask.sh`

## 本地开发

```sh
cd frontend
pnpm install
pnpm dev          # 启动 vite dev server (HMR)
pnpm build        # 生产构建，产物到 ../app/static/frontend/
pnpm typecheck    # tsc --noEmit
pnpm lint         # eslint
pnpm lint:style   # stylelint
```

## Flask 引用

```py
from frontend.vite_helper import register_vite
register_vite(app, 'app/static/frontend/manifest.json')

# 在路由里渲染：
return render_template('components_demo.html')
```

模板中已经通过 `{{ vite_asset('components-demo') | safe }}` 注入带 hash 的 `<link>` / `<script type=module>`。
