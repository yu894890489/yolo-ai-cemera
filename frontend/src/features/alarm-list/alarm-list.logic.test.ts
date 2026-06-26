import { describe, it, expect } from 'vitest';
import { toAlarmRow, formatTs } from './alarm-list.logic';
import type { AlarmEvent } from '@/api/types';

const base: AlarmEvent = {
  alarm_id: 'a1',
  task_id: 't1',
  rule_id: 'r1',
  class: 'person',
  score: 0.81,
  ts_ms: 1719300000000,
  object_name: '2026/06/26/a1.jpg',
  screenshot_url: null,
  vlm_reason: null,
  vlm_confidence: null,
  task_name: null,
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
  it('uses VLM reason and confidence when present', () => {
    const row = toAlarmRow({ ...base, vlm_reason: '有人闯入', vlm_confidence: 0.95 });
    expect(row.reason).toBe('有人闯入');
    expect(row.confidence).toBe('0.95');
  });

  it('falls back to YOLO score when vlm_confidence is missing', () => {
    const row = toAlarmRow(base);
    expect(row.confidence).toBe('0.81');
  });

  it('falls back to task_id when task_name is missing', () => {
    expect(toAlarmRow(base).taskName).toBe('t1');
    expect(toAlarmRow({ ...base, task_name: '东门监控' }).taskName).toBe('东门监控');
  });

  it('prefers an explicit screenshot_url over object_name', () => {
    const row = toAlarmRow({ ...base, screenshot_url: 'https://x/a.jpg' });
    expect(row.screenshotUrl).toBe('https://x/a.jpg');
  });

  it('resolves object_name against the MinIO base when no direct url', () => {
    const row = toAlarmRow(base, { minioBase: 'http://192.168.10.83:19000', bucket: 'alarms' });
    expect(row.screenshotUrl).toBe('http://192.168.10.83:19000/alarms/2026/06/26/a1.jpg');
  });

  it('yields null screenshot when neither url nor minio base available', () => {
    expect(toAlarmRow(base).screenshotUrl).toBeNull();
  });

  it('shows a dash for an unknown class', () => {
    expect(toAlarmRow({ ...base, class: null }).className).toBe('—');
  });
});
