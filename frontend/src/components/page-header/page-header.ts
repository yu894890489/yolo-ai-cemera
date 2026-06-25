import './page-header.scss';

export type Crumb = { label: string; href?: string };
export type PageHeaderOptions = {
  title: string;
  subtitle?: string;
  breadcrumbs?: Crumb[];
  actions?: HTMLElement[];
};

export function createPageHeader(opts: PageHeaderOptions): HTMLElement {
  const root = document.createElement('header');
  root.className = 'mc-page-header';

  const left = document.createElement('div');
  left.className = 'mc-page-header__left';

  if (opts.breadcrumbs && opts.breadcrumbs.length > 0) {
    const nav = document.createElement('nav');
    nav.className = 'mc-page-header__breadcrumbs';
    nav.setAttribute('aria-label', '面包屑');
    opts.breadcrumbs.forEach((c, i) => {
      if (i > 0) {
        const sep = document.createElement('span');
        sep.className = 'mc-page-header__sep';
        sep.textContent = '/';
        nav.appendChild(sep);
      }
      if (c.href) {
        const a = document.createElement('a');
        a.href = c.href;
        a.textContent = c.label;
        nav.appendChild(a);
      } else {
        const span = document.createElement('span');
        span.textContent = c.label;
        nav.appendChild(span);
      }
    });
    left.appendChild(nav);
  }

  const h1 = document.createElement('h1');
  h1.className = 'mc-page-header__title';
  h1.textContent = opts.title;
  left.appendChild(h1);

  if (opts.subtitle) {
    const sub = document.createElement('p');
    sub.className = 'mc-page-header__subtitle';
    sub.textContent = opts.subtitle;
    left.appendChild(sub);
  }

  root.appendChild(left);

  const actions = document.createElement('div');
  actions.className = 'mc-page-header__actions';
  (opts.actions ?? []).forEach((a) => actions.appendChild(a));
  root.appendChild(actions);

  return root;
}
