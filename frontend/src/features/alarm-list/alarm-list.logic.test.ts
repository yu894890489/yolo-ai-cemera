import { describe, it, expect } from 'vitest';
import { toAlarmRow, formatTs } from './alarm-list.logic';
import type { AlarmEvent } from '@/api/types';

const base: AlarmEvent = {
  alarm_id: 'a1',
  event_id: 'e1',
  task_id: 't1',
  rule_id: 'demo',
  class: 'person',
  score: 0.81,
  ts_ms: 1719300000000,
  mode: 'small_only',
  vlm_status: 'disabled',
  vlm_reason: null,
  vlm_confidence: null,
  screenshot_object: '2026/06/26/a1.jpg',
};

describe('formatTs', () => {
  it('formats epoch ms to a readable local time string', () => {
    expect(formatTs(1719300000000)).toMatch(/\d{4}/);
  });
  it('returns a dash for null/invalid timestamps', () => {
    expect(formatTs(null)).toBe('—');
    expect(formatTs(undefined)).toBe('—');
  });
});

describe('toAlarmRow', () => {
  it('uses VLM reason and confidence when vlm_status is ok', () => {
    const row = toAlarmRow({
      ...base,
      vlm_status: 'ok',
      vlm_reason: '有人闯入',
      vlm_confidence: 0.95,
    });
    expect(row.reason).toBe('有人闯入');
    expect(row.confidence).toBe('0.95');
  });

  it('uses YOLO score for confidence when vlm_status is not ok', () => {
    expect(toAlarmRow(base).confidence).toBe('0.81');
  });

  it('shows a status label as reason when VLM did not judge', () => {
    expect(toAlarmRow({ ...base, vlm_status: 'disabled' }).reason).toBe('未启用 VLM');
    expect(toAlarmRow({ ...base, vlm_status: 'failed' }).reason).toBe('VLM 调用失败');
    expect(toAlarmRow({ ...base, vlm_status: 'skipped' }).reason).toBe('VLM 已跳过（降级）');
  });

  it('uses task_id as the task name (no task_name field in payload)', () => {
    expect(toAlarmRow(base).taskName).toBe('t1');
  });

  it('resolves screenshot_object against the MinIO base + bucket', () => {
    const row = toAlarmRow(base, { minioBase: 'http://192.168.10.83:19000', bucket: 'alarms' });
    expect(row.screenshotUrl).toBe('http://192.168.10.83:19000/alarms/2026/06/26/a1.jpg');
  });

  it('defaults the bucket to alarms when not provided', () => {
    const row = toAlarmRow(base, { minioBase: 'http://192.168.10.83:19000' });
    expect(row.screenshotUrl).toBe('http://192.168.10.83:19000/alarms/2026/06/26/a1.jpg');
  });

  it('yields null screenshot when no minio base available', () => {
    expect(toAlarmRow(base).screenshotUrl).toBeNull();
  });

  it('shows a dash for an unknown class', () => {
    expect(toAlarmRow({ ...base, class: null }).className).toBe('—');
  });
});
