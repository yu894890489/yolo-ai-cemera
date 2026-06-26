/**
 * monitor-preview — 监控预览页入口。
 * 装配运行期 API，挂载预览页；URL 带 ?task=<id> 时自动选中该任务。
 */
import '@styles/base.scss';
import { createRuntime } from '@/api/bootstrap';
import { renderMonitorPreview } from '@/features/monitor-preview/monitor-preview';

const host = document.getElementById('app');
if (!host) throw new Error('#app not found');

const runtime = createRuntime();
const handle = renderMonitorPreview(host, runtime.api);

const taskId = new URLSearchParams(location.search).get('task');
if (taskId) handle.selectTask(taskId);
