import './toast.scss';

export type ToastLevel = 'success' | 'error' | 'warning' | 'info';

export type ToastOptions = {
  level?: ToastLevel;
  title?: string;
  message: string;
  duration?: number; // ms; 0 = 不自动消失
};

const SLOT_ID = 'mc-toast-slot';

function getSlot(): HTMLElement {
  let slot = document.getElementById(SLOT_ID);
  if (!slot) {
    slot = document.createElement('div');
    slot.id = SLOT_ID;
    slot.className = 'mc-toast-slot';
    document.body.appendChild(slot);
  }
  return slot;
}

export function toast(opts: ToastOptions): () => void {
  const slot = getSlot();
  const level: ToastLevel = opts.level ?? 'info';
  const node = document.createElement('div');
  node.className = `mc-toast mc-toast--${level}`;
  node.setAttribute('role', level === 'error' ? 'alert' : 'status');

  const icon = document.createElement('span');
  icon.className = 'mc-toast__icon';
  icon.textContent =
    level === 'success' ? '✓' : level === 'error' ? '✕' : level === 'warning' ? '!' : 'i';

  const body = document.createElement('div');
  body.className = 'mc-toast__body';
  if (opts.title) {
    const t = document.createElement('div');
    t.className = 'mc-toast__title';
    t.textContent = opts.title;
    body.appendChild(t);
  }
  const m = document.createElement('div');
  m.className = 'mc-toast__msg';
  m.textContent = opts.message;
  body.appendChild(m);

  const close = document.createElement('button');
  close.className = 'mc-toast__close';
  close.textContent = '×';
  close.setAttribute('aria-label', '关闭');

  node.append(icon, body, close);
  slot.appendChild(node);

  const dismiss = (): void => {
    node.classList.add('is-leaving');
    window.setTimeout(() => node.remove(), 180);
  };
  close.addEventListener('click', dismiss);

  const duration = opts.duration ?? 3500;
  if (duration > 0) window.setTimeout(dismiss, duration);
  return dismiss;
}

export const Toast = {
  success: (message: string, title?: string) => toast({ level: 'success', message, title }),
  error: (message: string, title?: string) => toast({ level: 'error', message, title, duration: 5000 }),
  warning: (message: string, title?: string) => toast({ level: 'warning', message, title }),
  info: (message: string, title?: string) => toast({ level: 'info', message, title }),
};
