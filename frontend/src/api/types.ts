/**
 * API 类型 — 严格对齐后端 BE-M1-A / BE-M1-C 的 dataclass 与响应。
 *
 * 字段来源（backend/app/api）：
 *   - Source / Task: app/api/models.py
 *   - sources / tasks 路由: app/api/sources.py, app/api/tasks.py
 *   - runtime/status: app/api/__init__.py
 *   - 告警 ws 载荷: app/workers/saver.py（M0 stub 形态，BE-M1-B 会扩展）
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

/**
 * 告警事件 — ws:alarm 推送的标准化形态。
 *
 * M0 saver 当前推送字段：alarm_id / task_id / rule_id / class / score / ts_ms / object_name。
 * BE-M1-B 会补充 VLM 判定原因、置信度、截图直链、任务名等；这里把后续字段标为可选，
 * 由 normalizeAlarm() 做向后兼容映射，避免前后端字段漂移导致前端崩溃。
 */
export interface AlarmEvent {
  alarm_id: string;
  task_id: string;
  /** 命中规则 id（M0）。 */
  rule_id?: string | null;
  /** 目标类别。 */
  class?: string | null;
  /** YOLO 置信度 / 综合分值。 */
  score?: number | null;
  /** 毫秒时间戳。 */
  ts_ms?: number | null;
  /** MinIO 对象 key（M0），需拼接 endpoint 才能展示。 */
  object_name?: string | null;
  /** 截图直链（BE-M1-B 期望补充）。 */
  screenshot_url?: string | null;
  /** VLM 判定原因（BE-M1-B 期望补充）。 */
  vlm_reason?: string | null;
  /** VLM 置信度（BE-M1-B 期望补充，0-1）。 */
  vlm_confidence?: number | null;
  /** 任务名（BE-M1-B 期望补充；否则前端用 task_id 兜底）。 */
  task_name?: string | null;
}
