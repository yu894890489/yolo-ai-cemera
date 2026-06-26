/**
 * API 类型 — 严格对齐后端 BE-M1-A / BE-M1-C 的 dataclass 与响应。
 *
 * 字段来源（backend/app/api）：
 *   - Source / Task: app/api/models.py
 *   - sources / tasks 路由: app/api/sources.py, app/api/tasks.py
 *   - runtime/status: app/api/__init__.py
 *   - 告警 ws 载荷: app/workers/saver.py（SaverWorker._persist_entry 的推送字典，BE-M1-B 已合入）
 */

/** 任务状态枚举，对齐后端 Task.status。 */
export type TaskStatus = 'created' | 'running' | 'stopped' | 'error';

/** v1 仅支持 small_crop。 */
export type AlgorithmId = 'small_crop';

/** 视频源，对齐后端 Source dataclass。 */
export interface Source {
  id: string;
  name: string;
  protocol: string;
  address: string;
  enabled: boolean;
  note: string;
  created_at: string;
  updated_at: string;
}

/** 新建视频源入参（POST /api/sources）。 */
export interface SourceCreate {
  name: string;
  protocol: string;
  address: string;
  enabled?: boolean;
  note?: string;
}

/** 任务，对齐后端 Task dataclass；running 时附带 preview_url。 */
export interface Task {
  id: string;
  source_id: string;
  algorithm_id: string;
  roi: string;
  prompt: string;
  confidence: number;
  status: TaskStatus;
  error_message: string;
  created_at: string;
  updated_at: string;
  /** 仅当 status === 'running' 时后端返回（HLS index.m3u8）。 */
  preview_url?: string;
}

/** 新建 small_crop 任务入参（POST /api/tasks）。 */
export interface TaskCreate {
  source_id: string;
  algorithm_id: AlgorithmId;
  roi?: string;
  prompt?: string;
  confidence?: number;
}

/** GET /api/tasks/:id/status 的精简响应。 */
export interface TaskStatusResult {
  id: string;
  status: TaskStatus;
  error_message: string;
  preview_url?: string;
}

/** GET /api/runtime/status（BE-M1-C 配置版本 + VLM 治理状态）。 */
export interface RuntimeStatus {
  config_version: number;
  task: {
    confidence: number;
    roi: string;
    prompt: string;
    vlm_enabled: boolean;
  };
  vlm: {
    enabled: boolean;
    active_provider: string | null;
    last_error: string | null;
    last_failure_reason: string | null;
    degraded_mode: boolean;
    queue_high_watermark: number;
    queue_timeout_ms: number;
    disable_thinking: boolean;
    max_retries: number;
  };
}

/** VLM 判定状态，对齐 consumer：ok=已判定告警，failed=调用失败，skipped=降级跳过，disabled=未启用。 */
export type VlmStatus = 'ok' | 'failed' | 'skipped' | 'disabled' | '';

/**
 * 告警事件 — ws:alarm 推送的标准化形态。
 *
 * 后端 SaverWorker 把这些字段原样发布到 Redis `ws:alarm`，Flask `/ws` 直接透传：
 *   alarm_id / event_id / task_id / rule_id / class / score / mode /
 *   vlm_status / vlm_reason / vlm_confidence / screenshot_object / ts_ms
 *
 * 注意：
 *   - 截图是 MinIO 对象 key（screenshot_object），需拼 endpoint+bucket 才能展示，后端不给直链；
 *   - 没有 task_name 字段，前端用 task_id 兜底；
 *   - 目标类别即 YOLO 命中类别 class；
 *   - score / vlm_confidence 在 Redis 里是字符串，normalizeAlarm 统一转数字。
 */
export interface AlarmEvent {
  alarm_id: string;
  /** 3s 窗口去重 id（前端据此去重）。 */
  event_id?: string | null;
  task_id: string;
  /** 命中规则 id。 */
  rule_id?: string | null;
  /** 目标类别（YOLO 命中类别）。 */
  class?: string | null;
  /** YOLO 置信度分值。 */
  score?: number | null;
  /** 毫秒时间戳。 */
  ts_ms?: number | null;
  /** 协同模式：vlm / small_only / default。 */
  mode?: string | null;
  /** VLM 判定状态。 */
  vlm_status?: VlmStatus;
  /** VLM 判定原因（仅 vlm_status='ok' 时有意义）。 */
  vlm_reason?: string | null;
  /** VLM 置信度（仅 vlm_status='ok' 时有意义，0-1；其余为 0）。 */
  vlm_confidence?: number | null;
  /** 告警截图的 MinIO 对象 key，需拼接 endpoint+bucket 展示。 */
  screenshot_object?: string | null;
}
