# 通用组件库 (FE-M0-04)

8 个高频组件，命令式 API，无外部框架依赖（除 Bootstrap 主题/token）。

## 组件清单

| 组件 | 入口 | 说明 |
| --- | --- | --- |
| `DataTable` | `data-table/data-table.ts` | 排序 / 筛选 / 分页 / 列宽拖拽 / 空态 |
| `FormField` | `form-field/form-field.ts` | label + 校验信息 + 帮助文本 |
| `ConfirmDialog` | `confirm-dialog/confirm-dialog.ts` | Promise 风格的确认弹窗 |
| `Toast` | `toast/toast.ts` | 成功 / 失败 / 警告 / 信息，可堆叠 |
| `StatusBadge` | `status-badge/status-badge.ts` | 任务状态、告警等级 |
| `EmptyState` | `empty-state/empty-state.ts` | 空数据 / 无权限 / 无结果 |
| `LoadingSkeleton` | `loading-skeleton/loading-skeleton.ts` | 加载占位（line/block/circle）|
| `PageHeader` | `page-header/page-header.ts` | 标题 + 面包屑 + 操作按钮槽 |

## 引用方式

```ts
import {
  DataTable,
  createFormField,
  confirmDialog,
  Toast,
  createStatusBadge,
  createEmptyState,
  createSkeleton,
  createPageHeader,
} from '@components/index';
```

## Demo 页

`pnpm dev` 后访问 `/`（Vite 默认 root），或 `pnpm build` 后在 Flask 中加载 manifest 入口 `components-demo`。

> Storybook 在工期吃紧时降级为单页 demo，等 M2 起按需引入。
