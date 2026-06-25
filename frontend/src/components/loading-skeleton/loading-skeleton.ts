import './loading-skeleton.scss';

export type SkeletonShape = 'line' | 'block' | 'circle';
export type SkeletonOptions = {
  shape?: SkeletonShape;
  width?: string;
  height?: string;
  rows?: number; // for 'line': 重复几行
};

export function createSkeleton(opts: SkeletonOptions = {}): HTMLElement {
  const shape = opts.shape ?? 'line';
  const rows = shape === 'line' ? opts.rows ?? 3 : 1;
  const wrap = document.createElement('div');
  wrap.className = 'mc-skeleton';

  for (let i = 0; i < rows; i += 1) {
    const item = document.createElement('div');
    item.className = `mc-skeleton__item mc-skeleton__item--${shape}`;
    if (opts.width) item.style.width = opts.width;
    if (opts.height) item.style.height = opts.height;
    // 最后一行行宽收窄一点，更像真实段落
    if (shape === 'line' && i === rows - 1 && !opts.width) item.style.width = '60%';
    wrap.appendChild(item);
  }
  return wrap;
}
