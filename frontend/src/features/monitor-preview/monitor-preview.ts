/**
 * 监控预览页 —— 选择任务、播放 BE-M1-A 返回的预览流、展示状态、启动/停止。
 */

import './monitor-preview.scss';
import { createPageHeader, createStatusBadge, Toast, type StatusVariant } from '@components/index';
import type { Task, TaskStatus } from '@/api/types';
import { type Api as ApiContract, ApiError } from '@/api/client';
import { StreamPlayer } from '@/player/stream-player';

export interface MonitorPreviewHandle {
  destroy(): void;
  selectTask(taskId: string): void;
}

const STATUS_META: Record<TaskStatus, { label: string; variant: StatusVariant }> = {
  created: { label: '已创建', variant: 'neutral' },
  running: { label: '运行中', variant: 'processing' },
  stopped: { label: '已停止', variant: 'warning' },
  error: { label: '异常', variant: 'danger' },
};

export function renderMonitorPreview(
  container: HTMLElement,
  api: ApiContract,
): MonitorPreviewHandle {
  container.classList.add('mc-monitor');
  container.innerHTML = '';

  container.appendChild(
    createPageHeader({
      title: '监控预览',
      subtitle: '单路实时预览 · 启停控制',
      breadcrumbs: [{ label: '首页', href: '/' }, { label: '监控预览' }],
    }),
  );

  const toolbar = document.createElement('div');
  toolbar.className = 'mc-monitor__toolbar';
  const select = document.createElement('select');
  select.className = 'mc-input mc-monitor__select';
  const refreshBtn = btn('刷新', 'mc-btn');
  const startBtn = btn('启动', 'mc-btn mc-btn--primary');
  const stopBtn = btn('停止', 'mc-btn mc-btn--danger');
  toolbar.append(select, refreshBtn, startBtn, stopBtn);
  container.appendChild(toolbar);

  const statusBar = document.createElement('div');
  statusBar.className = 'mc-monitor__statusbar';
  container.appendChild(statusBar);

  const stage = document.createElement('div');
  stage.className = 'mc-monitor__stage';
  container.appendChild(stage);

  const playerHost = document.createElement('div');
  playerHost.className = 'mc-monitor__player';
  stage.appendChild(playerHost);

  const placeholder = document.createElement('div');
  placeholder.className = 'mc-monitor__placeholder';
  placeholder.textContent = '选择一个运行中的任务以预览视频流';
  stage.appendChild(placeholder);

  const player = new StreamPlayer(playerHost, {
    autoplay: true,
    muted: true,
    controls: true,
    onError: () => Toast.error('视频流加载失败，请确认任务正在运行且 MediaMTX 可达'),
  });

  let destroyed = false;
  let current: Task | null = null;
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let lastPlayedUrl: string | null = null;

  select.addEventListener('change', () => {
    const t = tasksById.get(select.value);
    if (t) setCurrent(t);
  });
  refreshBtn.addEventListener('click', () => void loadTasks());
  startBtn.addEventListener('click', () => void doStart());
  stopBtn.addEventListener('click', () => void doStop());

  const tasksById = new Map<string, Task>();
  void loadTasks();

  async function loadTasks(): Promise<void> {
    try {
      const tasks = await api.listTasks();
      if (destroyed) return;
      tasksById.clear();
      select.innerHTML = '';
      if (tasks.length === 0) {
        const o = document.createElement('option');
        o.textContent = '暂无任务，请先创建';
        o.value = '';
        select.appendChild(o);
        setCurrent(null);
        return;
      }
      tasks.forEach((t) => {
        tasksById.set(t.id, t);
        const o = document.createElement('option');
        o.value = t.id;
        o.textContent = `${t.id} · ${STATUS_META[t.status]?.label ?? t.status}`;
        select.appendChild(o);
      });
      const keep = current && tasksById.has(current.id) ? tasksById.get(current.id)! : tasks[0];
      select.value = keep.id;
      setCurrent(keep);
    } catch (e) {
      if (!destroyed) Toast.error(errMsg(e, '加载任务失败'));
    }
  }

  function setCurrent(task: Task | null): void {
    current = task;
    renderStatus();
    if (!task) {
      stopPolling();
      showStream(null);
      return;
    }
    if (task.status === 'running' && task.preview_url) {
      showStream(task.preview_url);
      startPolling();
    } else {
      showStream(null);
      stopPolling();
    }
  }

  function renderStatus(): void {
    statusBar.innerHTML = '';
    if (!current) return;
    const meta = STATUS_META[current.status] ?? { label: current.status, variant: 'neutral' as StatusVariant };
    statusBar.appendChild(createStatusBadge({ label: meta.label, variant: meta.variant }));
    const info = document.createElement('span');
    info.className = 'mc-monitor__meta';
    info.textContent = `任务 ${current.id} · 置信度 ${current.confidence}`;
    statusBar.appendChild(info);
    if (current.status === 'error' && current.error_message) {
      const err = document.createElement('span');
      err.className = 'mc-monitor__err';
      err.textContent = current.error_message;
      statusBar.appendChild(err);
    }
    startBtn.disabled = current.status === 'running';
    stopBtn.disabled = current.status !== 'running';
  }

  function showStream(url: string | null): void {
    if (url) {
      placeholder.hidden = true;
      playerHost.hidden = false;
      if (url !== lastPlayedUrl) {
        player.play(url);
        lastPlayedUrl = url;
      }
    } else {
      playerHost.hidden = true;
      placeholder.hidden = false;
      lastPlayedUrl = null;
    }
  }

  async function doStart(): Promise<void> {
    if (!current) return;
    startBtn.disabled = true;
    try {
      const task = await api.startTask(current.id);
      tasksById.set(task.id, task);
      Toast.success('任务已启动');
      setCurrent(task);
    } catch (e) {
      Toast.error(errMsg(e, '启动失败'));
      renderStatus();
    }
  }

  async function doStop(): Promise<void> {
    if (!current) return;
    stopBtn.disabled = true;
    try {
      const task = await api.stopTask(current.id);
      tasksById.set(task.id, task);
      Toast.info('任务已停止');
      setCurrent(task);
    } catch (e) {
      Toast.error(errMsg(e, '停止失败'));
      renderStatus();
    }
  }

  function startPolling(): void {
    stopPolling();
    pollTimer = setInterval(() => void pollStatus(), 5000);
  }
  function stopPolling(): void {
    if (pollTimer !== null) clearInterval(pollTimer);
    pollTimer = null;
  }
  async function pollStatus(): Promise<void> {
    if (!current || destroyed) return;
    try {
      const st = await api.getTaskStatus(current.id);
      if (destroyed || !current || current.id !== st.id) return;
      const merged: Task = {
        ...current,
        status: st.status,
        error_message: st.error_message,
        preview_url: st.preview_url,
      };
      tasksById.set(merged.id, merged);
      // 状态有变才重渲染，避免无谓刷新播放器。
      if (merged.status !== current.status || merged.preview_url !== current.preview_url) {
        setCurrent(merged);
      } else {
        current = merged;
      }
    } catch {
      /* 轮询失败静默，等下一拍 */
    }
  }

  return {
    destroy(): void {
      destroyed = true;
      stopPolling();
      player.destroy();
      container.innerHTML = '';
    },
    selectTask(taskId: string): void {
      const t = tasksById.get(taskId);
      if (t) {
        select.value = taskId;
        setCurrent(t);
      } else {
        void loadTasks();
      }
    },
  };
}

function btn(label: string, cls: string): HTMLButtonElement {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = cls;
  b.textContent = label;
  return b;
}

function errMsg(e: unknown, fallback: string): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return fallback;
}
