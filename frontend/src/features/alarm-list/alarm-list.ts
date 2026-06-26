/**
 * 告警列表联调页 —— 订阅 WebSocket 实时告警，按时间倒序展示，
 * 处理加载 / 空 / 错误 / 断线重连等状态，对齐 BE-M1-B 后续补充的 VLM 字段。
 */

import './alarm-list.scss';
import { createPageHeader, createStatusBadge, createEmptyState, createSkeleton } from '@components/index';
import type { AlarmEvent } from '@/api/types';
import type { AppRuntime } from '@/api/bootstrap';
import type { AlarmSocket, AlarmSocketStatus } from '@/api/alarm-socket';
import { toAlarmRow, type AlarmRow } from './alarm-list.logic';

export interface AlarmListHandle {
  destroy(): void;
}

const MAX_ROWS = 200;

const CONN_META: Record<AlarmSocketStatus, { label: string; variant: 'processing' | 'success' | 'danger' }> = {
  connecting: { label: '连接中…', variant: 'processing' },
  open: { label: '实时连接', variant: 'success' },
  closed: { label: '已断开 · 重连中', variant: 'danger' },
};

export function renderAlarmList(container: HTMLElement, runtime: AppRuntime): AlarmListHandle {
  container.classList.add('mc-alarm');
  container.innerHTML = '';

  container.appendChild(
    createPageHeader({
      title: '实时告警',
      subtitle: 'WebSocket 推送 · 截图 / VLM 判定',
      breadcrumbs: [{ label: '首页', href: '/' }, { label: '实时告警' }],
    }),
  );

  const bar = document.createElement('div');
  bar.className = 'mc-alarm__bar';
  const connHost = document.createElement('div');
  connHost.className = 'mc-alarm__conn';
  const countSpan = document.createElement('span');
  countSpan.className = 'mc-alarm__count';
  bar.append(connHost, countSpan);
  container.appendChild(bar);

  const listHost = document.createElement('div');
  listHost.className = 'mc-alarm__list';
  container.appendChild(listHost);

  // 初始加载骨架
  listHost.appendChild(skeletonGroup());

  let destroyed = false;
  let firstStatus = true;
  const alarms: AlarmEvent[] = [];

  const renderConn = (status: AlarmSocketStatus): void => {
    const meta = CONN_META[status];
    connHost.innerHTML = '';
    connHost.appendChild(createStatusBadge({ label: meta.label, variant: meta.variant }));
  };

  const renderCount = (): void => {
    countSpan.textContent = alarms.length > 0 ? `共 ${alarms.length} 条告警` : '';
  };

  const showEmpty = (): void => {
    listHost.innerHTML = '';
    listHost.appendChild(
      createEmptyState({
        icon: '🔔',
        title: '暂无告警',
        description: '任务运行中检测到异常时，告警会在此实时出现',
      }),
    );
  };

  const renderList = (): void => {
    if (alarms.length === 0) {
      showEmpty();
      return;
    }
    listHost.innerHTML = '';
    alarms.slice(0, MAX_ROWS).forEach((a) => {
      listHost.appendChild(alarmCard(toAlarmRow(a, { minioBase: runtime.minioBase })));
    });
  };

  const socket: AlarmSocket = runtime.createAlarmSocket({
    onStatus: (status) => {
      if (destroyed) return;
      renderConn(status);
      // 首次状态到达即认为加载结束：若仍无数据则切换到空态。
      if (firstStatus) {
        firstStatus = false;
        if (alarms.length === 0) showEmpty();
      }
    },
    onAlarm: (alarm) => {
      if (destroyed) return;
      alarms.unshift(alarm);
      if (alarms.length > MAX_ROWS) alarms.length = MAX_ROWS;
      renderList();
      renderCount();
    },
    onError: () => {
      if (destroyed) return;
      // 错误不清空已有告警，仅靠连接徽标提示；socket 内部会自动重连。
    },
  });

  renderConn('connecting');
  socket.connect();

  return {
    destroy(): void {
      destroyed = true;
      socket.close();
      container.innerHTML = '';
    },
  };
}

function skeletonGroup(): HTMLElement {
  const wrap = document.createElement('div');
  wrap.className = 'mc-alarm__skeletons';
  for (let i = 0; i < 3; i += 1) {
    const row = document.createElement('div');
    row.className = 'mc-alarm__skeleton-row';
    row.appendChild(createSkeleton({ shape: 'block', width: '120px', height: '72px' }));
    row.appendChild(createSkeleton({ shape: 'line', rows: 3 }));
    wrap.appendChild(row);
  }
  return wrap;
}

function alarmCard(row: AlarmRow): HTMLElement {
  const card = document.createElement('article');
  card.className = 'mc-alarm__card';
  card.dataset.alarmId = row.alarmId;

  const thumb = document.createElement('div');
  thumb.className = 'mc-alarm__thumb';
  if (row.screenshotUrl) {
    const img = document.createElement('img');
    img.src = row.screenshotUrl;
    img.alt = `告警截图 ${row.className}`;
    img.loading = 'lazy';
    img.addEventListener('error', () => {
      thumb.classList.add('is-broken');
      thumb.textContent = '截图不可用';
    });
    thumb.appendChild(img);
  } else {
    thumb.classList.add('is-empty');
    thumb.textContent = '无截图';
  }
  card.appendChild(thumb);

  const body = document.createElement('div');
  body.className = 'mc-alarm__body';

  const top = document.createElement('div');
  top.className = 'mc-alarm__top';
  top.appendChild(createStatusBadge({ label: row.className, variant: 'danger' }));
  const time = document.createElement('span');
  time.className = 'mc-alarm__time';
  time.textContent = row.time;
  top.appendChild(time);
  body.appendChild(top);

  const reason = document.createElement('p');
  reason.className = 'mc-alarm__reason';
  reason.textContent = row.reason;
  body.appendChild(reason);

  const meta = document.createElement('div');
  meta.className = 'mc-alarm__meta';
  meta.append(
    metaItem('任务', row.taskName),
    metaItem('置信度', row.confidence),
  );
  body.appendChild(meta);

  card.appendChild(body);
  return card;
}

function metaItem(label: string, value: string): HTMLElement {
  const span = document.createElement('span');
  span.className = 'mc-alarm__meta-item';
  const k = document.createElement('span');
  k.className = 'mc-alarm__meta-key';
  k.textContent = `${label}：`;
  const v = document.createElement('span');
  v.textContent = value;
  span.append(k, v);
  return span;
}
