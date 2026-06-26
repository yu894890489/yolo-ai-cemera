/**
 * 告警 WebSocket 客户端 + 载荷标准化。
 *
 * 后端：Flask `/ws` 把 Redis `ws:alarm` 频道的每条 JSON 原样下发。
 * SaverWorker 推送字段（app/workers/saver.py）：
 *   alarm_id / event_id / task_id / rule_id / class / score / mode /
 *   vlm_status / vlm_reason / vlm_confidence / screenshot_object / ts_ms
 * 其中 score / ts_ms / vlm_confidence 经 Redis Stream 往往是字符串。
 *
 * normalizeAlarm() 负责把上述差异收敛成稳定的 AlarmEvent，避免字段漂移击穿前端。
 */

import type { AlarmEvent, VlmStatus } from './types';

const VLM_STATUSES: readonly VlmStatus[] = ['ok', 'failed', 'skipped', 'disabled', ''];

function toVlmStatus(v: unknown): VlmStatus {
  const s = v === null || v === undefined ? '' : String(v);
  return (VLM_STATUSES as readonly string[]).includes(s) ? (s as VlmStatus) : '';
}

function toNumber(v: unknown): number | null {
  if (v === null || v === undefined || v === '') return null;
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

function toStr(v: unknown): string | null {
  if (v === null || v === undefined) return null;
  return String(v);
}

/** 把任意原始 ws 载荷标准化为 AlarmEvent；非法载荷返回 null。 */
export function normalizeAlarm(raw: unknown): AlarmEvent | null {
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Record<string, unknown>;
  const alarmId = toStr(r.alarm_id);
  const taskId = toStr(r.task_id);
  if (!alarmId) return null;
  return {
    alarm_id: alarmId,
    event_id: toStr(r.event_id),
    task_id: taskId ?? '',
    rule_id: toStr(r.rule_id),
    class: toStr(r.class),
    score: toNumber(r.score),
    ts_ms: toNumber(r.ts_ms),
    mode: toStr(r.mode),
    vlm_status: toVlmStatus(r.vlm_status),
    vlm_reason: toStr(r.vlm_reason),
    vlm_confidence: toNumber(r.vlm_confidence),
    screenshot_object: toStr(r.screenshot_object),
  };
}

export type AlarmSocketStatus = 'connecting' | 'open' | 'closed';

/** WebSocket 的最小子集，便于测试注入假实现。 */
export interface AlarmSocketLike {
  onopen: (() => void) | null;
  onclose: (() => void) | null;
  onerror: (() => void) | null;
  onmessage: ((ev: { data: string }) => void) | null;
  close(): void;
}

export interface AlarmSocketOptions {
  url: string;
  onAlarm?: (alarm: AlarmEvent) => void;
  onStatus?: (status: AlarmSocketStatus) => void;
  onError?: (err: unknown) => void;
  /** 断线重连间隔，默认 3s；<=0 关闭自动重连。 */
  reconnectDelayMs?: number;
  /** 可注入的 socket 工厂，默认使用浏览器 WebSocket。 */
  factory?: (url: string) => AlarmSocketLike;
}

export class AlarmSocket {
  private readonly opts: Required<Pick<AlarmSocketOptions, 'url' | 'reconnectDelayMs' | 'factory'>> &
    AlarmSocketOptions;
  private socket: AlarmSocketLike | null = null;
  private manualClose = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(options: AlarmSocketOptions) {
    this.opts = {
      reconnectDelayMs: 3000,
      factory: (url: string) => new WebSocket(url) as unknown as AlarmSocketLike,
      ...options,
    };
  }

  connect(): void {
    this.manualClose = false;
    this.clearTimer();
    this.opts.onStatus?.('connecting');
    const socket = this.opts.factory(this.opts.url);
    this.socket = socket;
    socket.onopen = () => this.opts.onStatus?.('open');
    socket.onmessage = (ev) => this.handleMessage(ev.data);
    socket.onerror = () => this.opts.onError?.(new Error('websocket error'));
    socket.onclose = () => {
      this.opts.onStatus?.('closed');
      if (!this.manualClose && this.opts.reconnectDelayMs > 0) {
        this.scheduleReconnect();
      }
    };
  }

  close(): void {
    this.manualClose = true;
    this.clearTimer();
    if (this.socket) {
      this.socket.close();
    }
  }

  private handleMessage(data: string): void {
    let parsed: unknown;
    try {
      parsed = JSON.parse(data);
    } catch {
      return; // 非 JSON 直接忽略，不触发回调。
    }
    const alarm = normalizeAlarm(parsed);
    if (alarm) this.opts.onAlarm?.(alarm);
  }

  private scheduleReconnect(): void {
    this.clearTimer();
    this.reconnectTimer = setTimeout(() => this.connect(), this.opts.reconnectDelayMs);
  }

  private clearTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}

/** 由当前页面地址推导 ws(s):// 的 /ws 地址；baseUrl 非空时覆盖。 */
export function resolveWsUrl(baseUrl = ''): string {
  if (baseUrl) {
    return baseUrl.replace(/^http/, 'ws').replace(/\/+$/, '') + '/ws';
  }
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${location.host}/ws`;
}
