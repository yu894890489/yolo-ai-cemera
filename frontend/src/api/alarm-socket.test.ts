import { describe, it, expect, vi } from 'vitest';
import { normalizeAlarm, AlarmSocket, type AlarmSocketLike } from './alarm-socket';

describe('normalizeAlarm', () => {
  it('maps the SaverWorker ws:alarm payload shape', () => {
    const raw = {
      alarm_id: 'a1',
      event_id: 'e1',
      task_id: 't1',
      rule_id: 'demo',
      class: 'person',
      score: 0.82,
      mode: 'small_only',
      vlm_status: 'disabled',
      ts_ms: 1719300000000,
      screenshot_object: '2026/06/26/a1.jpg',
    };
    const a = normalizeAlarm(raw);
    expect(a).not.toBeNull();
    expect(a!.alarm_id).toBe('a1');
    expect(a!.event_id).toBe('e1');
    expect(a!.task_id).toBe('t1');
    expect(a!.class).toBe('person');
    expect(a!.score).toBe(0.82);
    expect(a!.mode).toBe('small_only');
    expect(a!.vlm_status).toBe('disabled');
    expect(a!.screenshot_object).toBe('2026/06/26/a1.jpg');
  });

  it('coerces stringified score/ts_ms/vlm_confidence numbers (Redis fields arrive as strings)', () => {
    const a = normalizeAlarm({
      alarm_id: 'a2',
      task_id: 't1',
      score: '0.5',
      ts_ms: '1719300000000',
      vlm_confidence: '0.9',
    });
    expect(a!.score).toBe(0.5);
    expect(a!.ts_ms).toBe(1719300000000);
    expect(a!.vlm_confidence).toBe(0.9);
  });

  it('keeps VLM judgment fields when vlm_status is ok', () => {
    const a = normalizeAlarm({
      alarm_id: 'a3',
      task_id: 't1',
      vlm_status: 'ok',
      vlm_reason: '检测到未授权人员闯入',
      vlm_confidence: 0.93,
      screenshot_object: '2026/06/26/a3.jpg',
    });
    expect(a!.vlm_status).toBe('ok');
    expect(a!.vlm_reason).toBe('检测到未授权人员闯入');
    expect(a!.vlm_confidence).toBe(0.93);
    expect(a!.screenshot_object).toBe('2026/06/26/a3.jpg');
  });

  it('coerces an unknown vlm_status to empty string', () => {
    expect(normalizeAlarm({ alarm_id: 'a4', task_id: 't1', vlm_status: 'weird' })!.vlm_status).toBe('');
    expect(normalizeAlarm({ alarm_id: 'a5', task_id: 't1' })!.vlm_status).toBe('');
  });

  it('returns null for malformed payloads without alarm_id', () => {
    expect(normalizeAlarm({ task_id: 't1' })).toBeNull();
    expect(normalizeAlarm(null)).toBeNull();
    expect(normalizeAlarm('not-json')).toBeNull();
  });
});

// 受控的假 WebSocket，便于驱动 open/message/close/error。
class FakeSocket implements AlarmSocketLike {
  static last: FakeSocket | null = null;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  closed = false;
  readonly url: string;
  constructor(url: string) {
    this.url = url;
    FakeSocket.last = this;
  }
  close(): void {
    this.closed = true;
  }
  emitOpen(): void {
    this.onopen?.();
  }
  emitMessage(data: string): void {
    this.onmessage?.({ data });
  }
  emitClose(): void {
    this.onclose?.();
  }
  emitError(): void {
    this.onerror?.();
  }
}

describe('AlarmSocket', () => {
  it('connects to the configured url and reports open status', () => {
    const onStatus = vi.fn();
    const sock = new AlarmSocket({
      url: 'ws://api.test/ws',
      factory: (u) => new FakeSocket(u),
      onStatus,
    });
    sock.connect();
    expect(FakeSocket.last?.url).toBe('ws://api.test/ws');
    FakeSocket.last!.emitOpen();
    expect(onStatus).toHaveBeenCalledWith('open');
  });

  it('parses incoming alarm payloads and invokes onAlarm', () => {
    const onAlarm = vi.fn();
    const sock = new AlarmSocket({
      url: 'ws://api.test/ws',
      factory: (u) => new FakeSocket(u),
      onAlarm,
    });
    sock.connect();
    FakeSocket.last!.emitMessage(JSON.stringify({ alarm_id: 'a1', task_id: 't1', class: 'car' }));
    expect(onAlarm).toHaveBeenCalledOnce();
    expect(onAlarm.mock.calls[0][0].class).toBe('car');
  });

  it('ignores malformed messages without throwing', () => {
    const onAlarm = vi.fn();
    const sock = new AlarmSocket({
      url: 'ws://api.test/ws',
      factory: (u) => new FakeSocket(u),
      onAlarm,
    });
    sock.connect();
    expect(() => FakeSocket.last!.emitMessage('{bad json')).not.toThrow();
    expect(onAlarm).not.toHaveBeenCalled();
  });

  it('schedules a reconnect after an unexpected close', () => {
    vi.useFakeTimers();
    const onStatus = vi.fn();
    const sock = new AlarmSocket({
      url: 'ws://api.test/ws',
      factory: (u) => new FakeSocket(u),
      onStatus,
      reconnectDelayMs: 1000,
    });
    sock.connect();
    const first = FakeSocket.last;
    FakeSocket.last!.emitClose();
    expect(onStatus).toHaveBeenCalledWith('closed');
    vi.advanceTimersByTime(1000);
    expect(FakeSocket.last).not.toBe(first); // 新连接已建立
    vi.useRealTimers();
  });

  it('does not reconnect after an explicit close()', () => {
    vi.useFakeTimers();
    const sock = new AlarmSocket({
      url: 'ws://api.test/ws',
      factory: (u) => new FakeSocket(u),
      reconnectDelayMs: 1000,
    });
    sock.connect();
    const first = FakeSocket.last;
    sock.close();
    expect(first?.closed).toBe(true);
    FakeSocket.last!.emitClose();
    vi.advanceTimersByTime(5000);
    expect(FakeSocket.last).toBe(first); // 未重连
    vi.useRealTimers();
  });
});
