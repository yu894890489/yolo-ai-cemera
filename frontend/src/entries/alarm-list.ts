/**
 * alarm-list — 实时告警列表页入口。
 * 装配运行期 API + 告警 socket，挂载告警列表页。
 */
import '@styles/base.scss';
import { createRuntime } from '@/api/bootstrap';
import { renderAlarmList } from '@/features/alarm-list/alarm-list';

const host = document.getElementById('app');
if (!host) throw new Error('#app not found');

const runtime = createRuntime();
renderAlarmList(host, runtime);
