import './status-badge.scss';

export type StatusVariant =
  | 'success'
  | 'info'
  | 'warning'
  | 'danger'
  | 'neutral'
  | 'processing';

export type StatusBadgeOptions = {
  label: string;
  variant?: StatusVariant;
  dot?: boolean;
};

/** 任务状态、告警等级用的徽标。 */
export function createStatusBadge(opts: StatusBadgeOptions): HTMLElement {
  const el = document.createElement('span');
  const v = opts.variant ?? 'neutral';
  el.className = `mc-status mc-status--${v}`;
  if (opts.dot ?? true) {
    const dot = document.createElement('span');
    dot.className = 'mc-status__dot';
    el.appendChild(dot);
  }
  const text = document.createElement('span');
  text.textContent = opts.label;
  el.appendChild(text);
  return el;
}
