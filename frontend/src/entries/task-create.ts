/**
 * task-create — 任务创建页入口。
 * 装配运行期 API，挂载任务创建页；创建成功后跳转监控预览（带 task 锚点）。
 */
import '@styles/base.scss';
import { createRuntime } from '@/api/bootstrap';
import { renderTaskCreate } from '@/features/task-create/task-create';

const host = document.getElementById('app');
if (!host) throw new Error('#app not found');

const runtime = createRuntime();
renderTaskCreate(host, runtime.api, {
  onCreated: (task) => {
    const params = new URLSearchParams(location.search);
    const mock = params.get('mock') === '1' ? '&mock=1' : '';
    location.href = `./monitor-preview.html?task=${encodeURIComponent(task.id)}${mock}`;
  },
});
