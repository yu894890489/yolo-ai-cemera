/**
 * components-demo — 组件库 demo 页入口。
 * 展示全部 8 个组件的各种用法。
 */
import '@styles/base.scss';
import '@styles/components-demo.scss';

import {
  DataTable,
  createFormField,
  confirmDialog,
  Toast,
  createStatusBadge,
  createEmptyState,
  createSkeleton,
  createPageHeader,
} from '../components/index';

const demo = document.getElementById('component-demo');
if (!demo) throw new Error('#component-demo not found');

/* ---------- DataTable ---------- */
const dtSection = demo.querySelector<HTMLElement>('[data-demo="datatable"]')!;
const table = new DataTable(
  dtSection.querySelector<HTMLElement>('.demo-output')!,
  {
    columns: [
      { key: 'id', title: 'ID', width: 80, sortable: true, filterable: true },
      { key: 'name', title: '任务名称', sortable: true, filterable: true },
      { key: 'status', title: '状态', sortable: true, render: (r) => {
        const b = createStatusBadge({ label: String(r.status), variant: r.status === '运行中' ? 'processing' : r.status === '已完成' ? 'success' : r.status === '异常' ? 'danger' : 'neutral' });
        return b;
      } },
      { key: 'progress', title: '进度', width: 100, sortable: true },
    ],
    rows: [
      { id: '001', name: '东门人流分析', status: '运行中', progress: '67%' },
      { id: '002', name: '车库违停检测', status: '已完成', progress: '100%' },
      { id: '003', name: '围墙入侵监控', status: '异常', progress: '34%' },
      { id: '004', name: '食堂排队分析', status: '排队中', progress: '0%' },
      { id: '005', name: '实验室安全巡检', status: '运行中', progress: '82%' },
      { id: '006', name: '消防通道监测', status: '已完成', progress: '100%' },
      { id: '007', name: '外围周界预警', status: '运行中', progress: '45%' },
      { id: '008', name: '南门车流统计', status: '已完成', progress: '100%' },
      { id: '009', name: '操场异常行为', status: '已完成', progress: '100%' },
      { id: '010', name: '配电房巡检', status: '排队中', progress: '0%' },
      { id: '011', name: '监控中心值班', status: '运行中', progress: '91%' },
      { id: '012', name: '北门车流统计', status: '异常', progress: '12%' },
    ],
    pageSize: 5,
  },
);

// 空态示例
document.getElementById('dt-empty-btn')?.addEventListener('click', () => {
  table.setRows([]);
});
document.getElementById('dt-reset-btn')?.addEventListener('click', () => {
  table.setRows([
    { id: '001', name: '东门人流分析', status: '运行中', progress: '67%' },
    { id: '002', name: '车库违停检测', status: '已完成', progress: '100%' },
    { id: '003', name: '围墙入侵监控', status: '异常', progress: '34%' },
  ]);
});

/* ---------- FormField ---------- */
const ffSection = demo.querySelector<HTMLElement>('[data-demo="formfield"]')!;
const ffOutput = ffSection.querySelector<HTMLElement>('.demo-output')!;
const nameInput = document.createElement('input');
nameInput.type = 'text';
nameInput.id = 'demo-name';
nameInput.placeholder = '输入任务名称…';
const ff = createFormField(nameInput, {
  label: '任务名称',
  htmlFor: 'demo-name',
  helpText: '建议使用中文命名，长度 2～50 字',
  required: true,
});
ffOutput.appendChild(ff.el);

document.getElementById('ff-error-btn')?.addEventListener('click', () => {
  ff.setError('任务名称不能为空');
});
document.getElementById('ff-help-btn')?.addEventListener('click', () => {
  ff.setError(null);
  ff.setHelp('已通过校验 ✓');
});

/* ---------- ConfirmDialog ---------- */
const cdSection = demo.querySelector<HTMLElement>('[data-demo="confirm"]')!;
const cdResult = cdSection.querySelector<HTMLElement>('.demo-result')!;
cdSection.querySelector<HTMLButtonElement>('#confirm-normal')?.addEventListener('click', async () => {
  const ok = await confirmDialog({
    title: '确认删除',
    message: '确定要删除「东门人流分析」这个任务吗？关联数据也会一并删除。',
    variant: 'danger',
  });
  cdResult.textContent = `结果: ${ok ? '确认' : '取消'}`;
});
cdSection.querySelector<HTMLButtonElement>('#confirm-info')?.addEventListener('click', async () => {
  const ok = await confirmDialog({
    title: '切换监控墙',
    message: '确认切换至 4 路网格模式？',
  });
  cdResult.textContent = `结果: ${ok ? '确认' : '取消'}`;
});

/* ---------- Toast ---------- */
const ttSection = demo.querySelector<HTMLElement>('[data-demo="toast"]')!;
ttSection.querySelector<HTMLButtonElement>('#toast-success')?.addEventListener('click', () => {
  Toast.success('任务创建成功', '操作完成');
});
ttSection.querySelector<HTMLButtonElement>('#toast-error')?.addEventListener('click', () => {
  Toast.error('YOLO 推理服务连接超时，请检查 docker_host', '服务异常');
});
ttSection.querySelector<HTMLButtonElement>('#toast-warning')?.addEventListener('click', () => {
  Toast.warning('存储空间已使用 85%，请及时清理', '磁盘预警');
});
ttSection.querySelector<HTMLButtonElement>('#toast-info')?.addEventListener('click', () => {
  Toast.info('系统巡检已排入队列', '提示');
});

/* ---------- StatusBadge ---------- */
const sbSection = demo.querySelector<HTMLElement>('[data-demo="statusbadge"]')!;
const sbOutput = sbSection.querySelector<HTMLElement>('.demo-output')!;
[
  { label: '运行中', variant: 'processing' as const },
  { label: '已完成', variant: 'success' as const },
  { label: '告警中', variant: 'danger' as const },
  { label: '排队中', variant: 'warning' as const },
  { label: '已停止', variant: 'neutral' as const },
  { label: '升级', variant: 'info' as const },
].forEach((s) => sbOutput.appendChild(createStatusBadge(s)));

/* ---------- EmptyState ---------- */
const esSection = demo.querySelector<HTMLElement>('[data-demo="emptystate"]')!;
const esOutput = esSection.querySelector<HTMLElement>('.demo-output')!;
esOutput.appendChild(createEmptyState({
  title: '暂无任务数据',
  description: '当前没有正在运行的分析任务，点击下方按钮创建一个。',
  action: { label: '新建任务', onClick: () => Toast.info('创建任务弹窗（待实现）') },
}));

/* ---------- LoadingSkeleton ---------- */
const lsSection = demo.querySelector<HTMLElement>('[data-demo="skeleton"]')!;
const lsOutput = lsSection.querySelector<HTMLElement>('.demo-output')!;
lsOutput.appendChild(createSkeleton({ rows: 4 }));
const blockDemo = document.createElement('div');
blockDemo.style.marginTop = '16px';
blockDemo.appendChild(createSkeleton({ shape: 'block' }));
lsOutput.appendChild(blockDemo);

/* ---------- PageHeader ---------- */
const phSection = demo.querySelector<HTMLElement>('[data-demo="pageheader"]')!;
const phOutput = phSection.querySelector<HTMLElement>('.demo-output')!;
const newBtn = document.createElement('button');
newBtn.className = 'mc-btn mc-btn--primary';
newBtn.textContent = '新建任务';
newBtn.addEventListener('click', () => Toast.info('新建任务'));
phOutput.appendChild(createPageHeader({
  title: '告警事件',
  subtitle: '查看和处置所有告警',
  breadcrumbs: [
    { label: '工作台', href: '/dashboard' },
    { label: '智能分析' },
    { label: '告警事件' },
  ],
  actions: [newBtn],
}));