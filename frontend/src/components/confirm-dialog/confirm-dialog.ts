import './confirm-dialog.scss';

export type ConfirmDialogOptions = {
  title?: string;
  message: string | HTMLElement;
  confirmText?: string;
  cancelText?: string;
  variant?: 'default' | 'danger';
};

/**
 * ConfirmDialog — Promise<boolean>。resolve(true) 表示确认，false 表示取消。
 */
export function confirmDialog(opts: ConfirmDialogOptions): Promise<boolean> {
  return new Promise((resolve) => {
    const backdrop = document.createElement('div');
    backdrop.className = 'mc-confirm__backdrop';

    const dialog = document.createElement('div');
    dialog.className = 'mc-confirm';
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');

    const title = document.createElement('div');
    title.className = 'mc-confirm__title';
    title.textContent = opts.title ?? '请确认';

    const body = document.createElement('div');
    body.className = 'mc-confirm__body';
    if (opts.message instanceof HTMLElement) body.appendChild(opts.message);
    else body.textContent = opts.message;

    const footer = document.createElement('div');
    footer.className = 'mc-confirm__footer';

    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'mc-btn';
    cancelBtn.textContent = opts.cancelText ?? '取消';

    const okBtn = document.createElement('button');
    okBtn.className =
      'mc-btn ' + (opts.variant === 'danger' ? 'mc-btn--danger' : 'mc-btn--primary');
    okBtn.textContent = opts.confirmText ?? '确认';

    footer.append(cancelBtn, okBtn);
    dialog.append(title, body, footer);
    backdrop.appendChild(dialog);
    document.body.appendChild(backdrop);

    const cleanup = (result: boolean) => {
      backdrop.remove();
      document.removeEventListener('keydown', onKey);
      resolve(result);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') cleanup(false);
      if (e.key === 'Enter') cleanup(true);
    };
    document.addEventListener('keydown', onKey);
    cancelBtn.addEventListener('click', () => cleanup(false));
    okBtn.addEventListener('click', () => cleanup(true));
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) cleanup(false);
    });
    okBtn.focus();
  });
}
