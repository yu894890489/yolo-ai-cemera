/**
 * 告警列表展示映射（纯逻辑，便于单测）。
 *
 * 把标准化后的 AlarmEvent 投影成一行可直接渲染的字符串字段，并按 vlm_status
 * 决定置信度/原因的取值与兜底，对齐 SaverWorker 实际推送（screenshot_object 为
 * MinIO 对象 key、无 task_name、vlm_* 仅在 vlm_status='ok' 时有意义）。
 */

import type { AlarmEvent } from '@/api/types';

export interface AlarmRow {
  alarmId: string;
  time: string;
  className: string;
  reason: string;
  confidence: string;
  taskName: string;
  screenshotUrl: string | null;
}

export interface AlarmRowOptions {
  /** MinIO endpoint（如 http://192.168.10.83:19000），用于把 screenshot_object 拼成可访问 URL。 */
  minioBase?: string;
  /** 告警截图所在 bucket，默认 alarms（对齐后端 MINIO_BUCKET_ALARMS）。 */
  bucket?: string;
}

const DASH = '—';

const VLM_STATUS_LABEL: Record<string, string> = {
  failed: 'VLM 调用失败',
  skipped: 'VLM 已跳过（降级）',
  disabled: '未启用 VLM',
};

export function formatTs(ts: number | null | undefined): string {
  if (ts === null || ts === undefined || !Number.isFinite(ts)) return DASH;
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return DASH;
  return d.toLocaleString('zh-CN', { hour12: false });
}

export function toAlarmRow(alarm: AlarmEvent, opts: AlarmRowOptions = {}): AlarmRow {
  const vlmOk = alarm.vlm_status === 'ok';
  // vlm_status='ok' 时用 VLM 置信度；否则回落到 YOLO score（VLM 未判定时 vlm_confidence 恒为 0）。
  const confidence = vlmOk ? alarm.vlm_confidence ?? alarm.score ?? null : alarm.score ?? null;
  return {
    alarmId: alarm.alarm_id,
    time: formatTs(alarm.ts_ms),
    className: alarm.class ?? DASH,
    reason: resolveReason(alarm),
    confidence: confidence === null ? DASH : String(confidence),
    taskName: alarm.task_id ?? DASH,
    screenshotUrl: resolveScreenshot(alarm, opts),
  };
}

function resolveReason(alarm: AlarmEvent): string {
  if (alarm.vlm_status === 'ok' && alarm.vlm_reason) return alarm.vlm_reason;
  const label = alarm.vlm_status ? VLM_STATUS_LABEL[alarm.vlm_status] : undefined;
  return label ?? alarm.vlm_reason ?? DASH;
}

function resolveScreenshot(alarm: AlarmEvent, opts: AlarmRowOptions): string | null {
  if (alarm.screenshot_object && opts.minioBase) {
    const bucket = opts.bucket ?? 'alarms';
    return `${opts.minioBase.replace(/\/+$/, '')}/${bucket}/${alarm.screenshot_object}`;
  }
  return null;
}
