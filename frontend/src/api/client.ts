/**
 * API 客户端 — 基于 fetch 的轻量封装，对齐后端 BE-M1-A / BE-M1-C 路由。
 *
 * 设计要点：
 *   - 通过 Api 接口暴露能力，真实实现（ApiClient）与离线 mock（见 mock.ts）可互换；
 *   - 非 2xx 抛出 ApiError，携带后端 `{error}` 文案与状态码，供页面 toast 展示；
 *   - baseUrl 为空时走同源相对路径（Flask 同域托管），非空时用于跨域 dev 联调。
 */

import type {
  Source,
  SourceCreate,
  Task,
  TaskCreate,
  TaskStatusResult,
  RuntimeStatus,
} from './types';

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;
  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

/** sources / tasks / runtime 能力契约；真实与 mock 实现共用。 */
export interface Api {
  listSources(): Promise<Source[]>;
  getSource(id: string): Promise<Source>;
  createSource(payload: SourceCreate): Promise<Source>;
  updateSource(id: string, payload: SourceCreate): Promise<Source>;
  deleteSource(id: string): Promise<void>;

  listTasks(): Promise<Task[]>;
  getTask(id: string): Promise<Task>;
  createTask(payload: TaskCreate): Promise<Task>;
  startTask(id: string): Promise<Task>;
  stopTask(id: string): Promise<Task>;
  getTaskStatus(id: string): Promise<TaskStatusResult>;

  getRuntimeStatus(): Promise<RuntimeStatus>;
}

export class ApiClient implements Api {
  private readonly base: string;

  constructor(baseUrl = '') {
    // 去掉结尾斜杠，空串表示同源相对请求。
    this.base = baseUrl.replace(/\/+$/, '');
  }

  // --- sources ---
  listSources(): Promise<Source[]> {
    return this.request<Source[]>('GET', '/api/sources');
  }
  getSource(id: string): Promise<Source> {
    return this.request<Source>('GET', `/api/sources/${encodeURIComponent(id)}`);
  }
  createSource(payload: SourceCreate): Promise<Source> {
    return this.request<Source>('POST', '/api/sources', payload);
  }
  updateSource(id: string, payload: SourceCreate): Promise<Source> {
    return this.request<Source>('PUT', `/api/sources/${encodeURIComponent(id)}`, payload);
  }
  deleteSource(id: string): Promise<void> {
    return this.request<void>('DELETE', `/api/sources/${encodeURIComponent(id)}`);
  }

  // --- tasks ---
  listTasks(): Promise<Task[]> {
    return this.request<Task[]>('GET', '/api/tasks');
  }
  getTask(id: string): Promise<Task> {
    return this.request<Task>('GET', `/api/tasks/${encodeURIComponent(id)}`);
  }
  createTask(payload: TaskCreate): Promise<Task> {
    return this.request<Task>('POST', '/api/tasks', payload);
  }
  startTask(id: string): Promise<Task> {
    return this.request<Task>('POST', `/api/tasks/${encodeURIComponent(id)}/start`);
  }
  stopTask(id: string): Promise<Task> {
    return this.request<Task>('POST', `/api/tasks/${encodeURIComponent(id)}/stop`);
  }
  getTaskStatus(id: string): Promise<TaskStatusResult> {
    return this.request<TaskStatusResult>('GET', `/api/tasks/${encodeURIComponent(id)}/status`);
  }

  // --- runtime ---
  getRuntimeStatus(): Promise<RuntimeStatus> {
    return this.request<RuntimeStatus>('GET', '/api/runtime/status');
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const init: RequestInit = { method };
    if (body !== undefined) {
      init.headers = { 'Content-Type': 'application/json' };
      init.body = JSON.stringify(body);
    }
    const res = await fetch(`${this.base}${path}`, init);
    if (!res.ok) {
      const parsed = await safeJson(res);
      const message =
        (parsed && typeof parsed === 'object' && 'error' in parsed
          ? String((parsed as { error: unknown }).error)
          : '') || `${method} ${path} failed (${res.status})`;
      throw new ApiError(res.status, message, parsed);
    }
    if (res.status === 204) {
      return undefined as T;
    }
    return (await safeJson(res)) as T;
  }
}

async function safeJson(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}
