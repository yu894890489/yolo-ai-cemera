import './empty-state.scss';

export type EmptyStateOptions = {
  title?: string;
  description?: string;
  icon?: string; // emoji or text glyph
  action?: { label: string; onClick: () => void };
};

export function createEmptyState(opts: EmptyStateOptions = {}): HTMLElement {
  const root = document.createElement('div');
  root.className = 'mc-empty';

  const icon = document.createElement('div');
  icon.className = 'mc-empty__icon';
  icon.textContent = opts.icon ?? '📭';
  root.appendChild(icon);

  const title = document.createElement('div');
  title.className = 'mc-empty__title';
  title.textContent = opts.title ?? '暂无数据';
  root.appendChild(title);

  if (opts.description) {
    const desc = document.createElement('div');
    desc.className = 'mc-empty__desc';
    desc.textContent = opts.description;
    root.appendChild(desc);
  }

  if (opts.action) {
    const btn = document.createElement('button');
    btn.className = 'mc-btn mc-btn--primary';
    btn.textContent = opts.action.label;
    btn.addEventListener('click', opts.action.onClick);
    root.appendChild(btn);
  }
  return root;
}
