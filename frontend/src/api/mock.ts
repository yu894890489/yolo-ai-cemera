/**
 * 离线 mock —— 实现与 ApiClient 相同的 Api 接口，配合一个内存版告警 socket，
 * 让前端在断网 / 后端未就绪时也能跑通「新建源 → 创建任务 → 启停 → 看告警」主流程。
 *
 * 这是 FE-M0-08「Mock 数据层」的等价物（M0 的 MSW 未落地，这里用更轻的内存实现替代，
 * 字段严格复用 src/api/types.ts，避免前后端字段漂移）。通过 URL `?mock=1` 启用。
 */

import type { Api } from './client';
import { ApiError } from './client';
import type {
  Source,
  SourceCreate,
  Task,
  TaskCreate,
  TaskStatusResult,
  RuntimeStatus,
} from './types';
import type { AlarmSocketLike } from './alarm-socket';

function ts(): string {
  return new Date().toISOString();
}

function rid(): string {
  return Math.random().toString(16).slice(2, 14);
}

export class MockApi implements Api {
  private sources = new Map<string, Source>();
  private tasks = new Map<string, Task>();
  private configVersion = 1;

  constructor(seed = true) {
    if (seed) {
      const s: Source = {
        id: rid(),
        name: '示例摄像头 · 东门',
        protocol: 'rtsp',
        address: 'rtsp://192.168.10.83:18554/demo',
        enabled: true,
        note: 'mock 内置示例源',
        created_at: ts(),
        updated_at: ts(),
      };
      this.sources.set(s.id, s);
    }
  }

  async listSources(): Promise<Source[]> {
    return [...this.sources.values()];
  }
  async getSource(id: string): Promise<Source> {
    const s = this.sources.get(id);
    if (!s) throw new ApiError(404, 'source not found', null);
    return s;
  }
  async createSource(payload: SourceCreate): Promise<Source> {
    const s: Source = {
      id: rid(),
      name: payload.name,
      protocol: payload.protocol,
      address: payload.address,
      enabled: payload.enabled ?? true,
      note: payload.note ?? '',
      created_at: ts(),
      updated_at: ts(),
    };
    this.sources.set(s.id, s);
    return s;
  }
  async updateSource(id: string, payload: SourceCreate): Promise<Source> {
    const existing = await this.getSource(id);
    const next: Source = {
      ...existing,
      ...payload,
      enabled: payload.enabled ?? existing.enabled,
      note: payload.note ?? existing.note,
      updated_at: ts(),
    };
    this.sources.set(id, next);
    return next;
  }
  async deleteSource(id: string): Promise<void> {
    if (!this.sources.delete(id)) throw new ApiError(404, 'source not found', null);
  }

  async listTasks(): Promise<Task[]> {
    return [...this.tasks.values()].map((t) => this.withPreview(t));
  }
  async getTask(id: string): Promise<Task> {
    const t = this.tasks.get(id);
    if (!t) throw new ApiError(404, 'task not found', null);
    return this.withPreview(t);
  }
  async createTask(payload: TaskCreate): Promise<Task> {
    if (!this.sources.has(payload.source_id)) {
      throw new ApiError(422, 'source_id does not exist', null);
    }
    const t: Task = {
      id: rid(),
      source_id: payload.source_id,
      algorithm_id: payload.algorithm_id,
      roi: payload.roi ?? '',
      prompt: payload.prompt ?? '',
      confidence: payload.confidence ?? 0.5,
      status: 'created',
      error_message: '',
      created_at: ts(),
      updated_at: ts(),
    };
    this.tasks.set(t.id, t);
    return t;
  }
  async startTask(id: string): Promise<Task> {
    const t = await this.rawTask(id);
    t.status = 'running';
    t.error_message = '';
    t.updated_at = ts();
    this.configVersion += 1;
    return this.withPreview(t);
  }
  async stopTask(id: string): Promise<Task> {
    const t = await this.rawTask(id);
    t.status = 'stopped';
    t.updated_at = ts();
    return this.withPreview(t);
  }
  async getTaskStatus(id: string): Promise<TaskStatusResult> {
    const t = await this.rawTask(id);
    return {
      id: t.id,
      status: t.status,
      error_message: t.error_message,
      ...(t.status === 'running' ? { preview_url: this.previewUrl(t.id) } : {}),
    };
  }

  async getRuntimeStatus(): Promise<RuntimeStatus> {
    return {
      config_version: this.configVersion,
      task: { confidence: 0.5, roi: '', prompt: '', vlm_enabled: true },
      vlm: {
        enabled: true,
        active_provider: 'qwen-vl-max',
        last_error: null,
        last_failure_reason: null,
        degraded_mode: false,
        queue_high_watermark: 100,
        queue_timeout_ms: 60000,
        disable_thinking: true,
        max_retries: 3,
      },
    };
  }

  /** 返回一个会周期性吐出 mock 告警的假 socket 工厂，供 AlarmSocket 注入。 */
  alarmSocketFactory(): (url: string) => AlarmSocketLike {
    const tasks = this.tasks;
    return () => {
      const socket = new MockAlarmSocket(tasks);
      return socket;
    };
  }

  private previewUrl(taskId: string): string {
    return `/hls/${taskId}/index.m3u8`;
  }
  private withPreview(t: Task): Task {
    return t.status === 'running' ? { ...t, preview_url: this.previewUrl(t.id) } : { ...t };
  }
  private async rawTask(id: string): Promise<Task> {
    const t = this.tasks.get(id);
    if (!t) throw new ApiError(404, 'task not found', null);
    return t;
  }
}

const MOCK_CLASSES = ['person', 'car', 'truck', 'bicycle'];
const MOCK_REASONS = [
  '检测到未授权人员进入警戒区域',
  '车辆在禁停区域长时间停留',
  '目标越过电子围栏边界',
];

class MockAlarmSocket implements AlarmSocketLike {
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;

  constructor(private readonly tasks: Map<string, Task>) {
    setTimeout(() => {
      this.onopen?.();
      this.timer = setInterval(() => this.emit(), 4000);
    }, 200);
  }

  close(): void {
    if (this.timer !== null) clearInterval(this.timer);
    this.timer = null;
    this.onclose?.();
  }

  private emit(): void {
    const running = [...this.tasks.values()].filter((t) => t.status === 'running');
    const task = running[Math.floor(Math.random() * running.length)];
    if (!task) return;
    const ms = Date.now();
    const eid = rid();
    const day = new Date(ms).toISOString().slice(0, 10).replace(/-/g, '/');
    const vlmOk = Math.random() > 0.25;
    const payload = {
      alarm_id: rid(),
      event_id: eid,
      task_id: task.id,
      rule_id: 'demo',
      class: MOCK_CLASSES[Math.floor(Math.random() * MOCK_CLASSES.length)],
      score: Math.round((0.6 + Math.random() * 0.39) * 100) / 100,
      ts_ms: ms,
      mode: vlmOk ? 'vlm' : 'small_only',
      vlm_status: vlmOk ? 'ok' : 'skipped',
      vlm_reason: vlmOk ? MOCK_REASONS[Math.floor(Math.random() * MOCK_REASONS.length)] : '',
      vlm_confidence: vlmOk ? Math.round((0.7 + Math.random() * 0.29) * 100) / 100 : 0,
      // 对齐后端：截图是 MinIO 对象 key（非直链）；离线 mock 无 MinIO，卡片会回落到「截图不可用」。
      screenshot_object: `${day}/${eid}.jpg`,
    };
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
}
