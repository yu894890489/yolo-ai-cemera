/**
 * DataTable — 可排序、筛选、分页、列宽拖拽、空态。
 * 命令式 API，无外部依赖，渲染到给定容器即可。
 */
import './data-table.scss';

export type DataTableColumn<T> = {
  key: keyof T & string;
  title: string;
  width?: number;
  sortable?: boolean;
  filterable?: boolean;
  render?: (row: T) => string | HTMLElement;
};

export type DataTableOptions<T> = {
  columns: DataTableColumn<T>[];
  rows: T[];
  pageSize?: number;
  emptyText?: string;
  rowKey?: (row: T, index: number) => string;
};

type SortState<T> = { key: keyof T & string; dir: 'asc' | 'desc' } | null;

export class DataTable<T extends Record<string, unknown>> {
  private root: HTMLElement;
  private columns: DataTableColumn<T>[];
  private allRows: T[];
  private viewRows: T[] = [];
  private pageSize: number;
  private page = 1;
  private sort: SortState<T> = null;
  private filters: Record<string, string> = {};
  private emptyText: string;
  private widths: Record<string, number> = {};
  private rowKey: (row: T, index: number) => string;

  constructor(container: HTMLElement, opts: DataTableOptions<T>) {
    this.root = container;
    this.columns = opts.columns;
    this.allRows = opts.rows.slice();
    this.pageSize = opts.pageSize ?? 10;
    this.emptyText = opts.emptyText ?? '暂无数据';
    this.rowKey = opts.rowKey ?? ((_, i) => String(i));
    this.columns.forEach((c) => {
      if (c.width) this.widths[c.key] = c.width;
    });
    this.root.classList.add('mc-data-table');
    this.recompute();
    this.render();
  }

  setRows(rows: T[]): void {
    this.allRows = rows.slice();
    this.page = 1;
    this.recompute();
    this.render();
  }

  private recompute(): void {
    let rows = this.allRows;
    for (const [key, val] of Object.entries(this.filters)) {
      const needle = val.trim().toLowerCase();
      if (!needle) continue;
      rows = rows.filter((r) => String(r[key] ?? '').toLowerCase().includes(needle));
    }
    if (this.sort) {
      const { key, dir } = this.sort;
      const mul = dir === 'asc' ? 1 : -1;
      rows = rows.slice().sort((a, b) => {
        const av = a[key] as unknown;
        const bv = b[key] as unknown;
        if (av == null && bv == null) return 0;
        if (av == null) return -1 * mul;
        if (bv == null) return 1 * mul;
        if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * mul;
        return String(av).localeCompare(String(bv), 'zh') * mul;
      });
    }
    this.viewRows = rows;
  }

  private render(): void {
    this.root.innerHTML = '';
    const table = document.createElement('table');
    table.className = 'mc-data-table__table';

    const thead = document.createElement('thead');
    const headRow = document.createElement('tr');
    this.columns.forEach((col) => {
      const th = document.createElement('th');
      if (this.widths[col.key]) th.style.width = `${this.widths[col.key]}px`;
      const label = document.createElement('span');
      label.textContent = col.title;
      th.appendChild(label);

      if (col.sortable) {
        th.classList.add('is-sortable');
        const indicator = document.createElement('span');
        indicator.className = 'mc-data-table__sort';
        if (this.sort?.key === col.key) {
          indicator.textContent = this.sort.dir === 'asc' ? '▲' : '▼';
        } else {
          indicator.textContent = '⇅';
        }
        th.appendChild(indicator);
        th.addEventListener('click', () => this.toggleSort(col.key));
      }

      // 列宽拖拽
      const handle = document.createElement('span');
      handle.className = 'mc-data-table__resize';
      handle.addEventListener('mousedown', (ev) => this.startResize(ev, col.key, th));
      th.appendChild(handle);

      headRow.appendChild(th);
    });
    thead.appendChild(headRow);

    // 筛选行
    const hasFilter = this.columns.some((c) => c.filterable);
    if (hasFilter) {
      const filterRow = document.createElement('tr');
      filterRow.className = 'mc-data-table__filter-row';
      this.columns.forEach((col) => {
        const td = document.createElement('th');
        if (col.filterable) {
          const input = document.createElement('input');
          input.type = 'search';
          input.placeholder = '筛选…';
          input.value = this.filters[col.key] ?? '';
          input.addEventListener('input', (e) => {
            this.filters[col.key] = (e.target as HTMLInputElement).value;
            this.page = 1;
            this.recompute();
            this.render();
          });
          td.appendChild(input);
        }
        filterRow.appendChild(td);
      });
      thead.appendChild(filterRow);
    }
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    if (this.viewRows.length === 0) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = this.columns.length;
      td.className = 'mc-data-table__empty';
      td.textContent = this.emptyText;
      tr.appendChild(td);
      tbody.appendChild(tr);
    } else {
      const start = (this.page - 1) * this.pageSize;
      const slice = this.viewRows.slice(start, start + this.pageSize);
      slice.forEach((row, i) => {
        const tr = document.createElement('tr');
        tr.dataset.key = this.rowKey(row, start + i);
        this.columns.forEach((col) => {
          const td = document.createElement('td');
          const v = col.render ? col.render(row) : (row[col.key] as string);
          if (v instanceof HTMLElement) td.appendChild(v);
          else td.textContent = v == null ? '' : String(v);
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
    }
    table.appendChild(tbody);

    this.root.appendChild(table);

    // 分页器
    const totalPages = Math.max(1, Math.ceil(this.viewRows.length / this.pageSize));
    const pager = document.createElement('div');
    pager.className = 'mc-data-table__pager';
    pager.innerHTML = `
      <button class="mc-btn" data-act="prev" ${this.page <= 1 ? 'disabled' : ''}>上一页</button>
      <span>第 ${this.page} / ${totalPages} 页，共 ${this.viewRows.length} 条</span>
      <button class="mc-btn" data-act="next" ${this.page >= totalPages ? 'disabled' : ''}>下一页</button>
    `;
    pager.querySelector<HTMLButtonElement>('[data-act=prev]')?.addEventListener('click', () => {
      if (this.page > 1) {
        this.page -= 1;
        this.render();
      }
    });
    pager.querySelector<HTMLButtonElement>('[data-act=next]')?.addEventListener('click', () => {
      if (this.page < totalPages) {
        this.page += 1;
        this.render();
      }
    });
    this.root.appendChild(pager);
  }

  private toggleSort(key: keyof T & string): void {
    if (!this.sort || this.sort.key !== key) this.sort = { key, dir: 'asc' };
    else if (this.sort.dir === 'asc') this.sort = { key, dir: 'desc' };
    else this.sort = null;
    this.recompute();
    this.render();
  }

  private startResize(ev: MouseEvent, key: string, th: HTMLElement): void {
    ev.preventDefault();
    ev.stopPropagation();
    const startX = ev.clientX;
    const startW = th.getBoundingClientRect().width;
    const onMove = (e: MouseEvent) => {
      const w = Math.max(60, startW + (e.clientX - startX));
      this.widths[key] = w;
      th.style.width = `${w}px`;
    };
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }
}
