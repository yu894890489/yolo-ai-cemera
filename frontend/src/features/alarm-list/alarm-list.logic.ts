/**
 * 告警列表展示映射（纯逻辑，便于单测）。
 *
 * 把标准化后的 AlarmEvent 投影成一行可直接渲染的字符串字段，并处理 VLM/YOLO 字段缺失时的兜底，
 * 兼容 M0 saver 当前载荷与 BE-M1-B 后续扩展。
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
  /** MinIO endpoint（如 http://192.168.10.83:19000），用于把 object_name 拼成可访问 URL。 */
  minioBase?: string;
  /** 告警截图所在 bucket，默认 alarms（见 BE-M0-S5）。 */
  bucket?: string;
}

const DASH = '—';

export function formatTs(ts: number | null | undefined): string {
  if (ts === null || ts === undefined || !Number.isFinite(ts)) return DASH;
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return DASH;
  return d.toLocaleString('zh-CN', { hour12: false });
}

export function toAlarmRow(alarm: AlarmEvent, opts: AlarmRowOptions = {}): AlarmRow {
  const confidence =
    alarm.vlm_confidence ?? alarm.score ?? null;
  return {
    alarmId: alarm.alarm_id,
    time: formatTs(alarm.ts_ms),
    className: alarm.class ?? DASH,
    reason: alarm.vlm_reason ?? DASH,
    confidence: confidence === null ? DASH : String(confidence),
    taskName: alarm.task_name ?? alarm.task_id ?? DASH,
    screenshotUrl: resolveScreenshot(alarm, opts),
  };
}

function resolveScreenshot(alarm: AlarmEvent, opts: AlarmRowOptions): string | null {
  if (alarm.screenshot_url) return alarm.screenshot_url;
  if (alarm.object_name && opts.minioBase) {
    const bucket = opts.bucket ?? 'alarms';
    return `${opts.minioBase.replace(/\/+$/, '')}/${bucket}/${alarm.object_name}`;
  }
  return null;
}
