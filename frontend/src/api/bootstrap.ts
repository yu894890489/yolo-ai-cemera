/**
 * 运行期配置 + 客户端装配。
 *
 * 真实部署：Flask 同源托管，API base 为空（相对路径），WS 走同源 /ws。
 * 离线演示：URL 带 ?mock=1 时切换到 MockApi + 内存告警 socket，断网也能跑通主流程。
 * 跨域 dev 联调：<meta name="api-base" content="http://192.168.10.83:5000"> 指定后端地址。
 */

import { ApiClient, type Api } from './client';
import { MockApi } from './mock';
import { AlarmSocket, resolveWsUrl, type AlarmSocketOptions, type AlarmSocketLike } from './alarm-socket';

export interface AppRuntime {
  api: Api;
  mock: boolean;
  /** MinIO endpoint，用于把告警 object_name 拼成可访问 URL（来自 meta 或默认）。 */
  minioBase: string;
  createAlarmSocket(handlers: Omit<AlarmSocketOptions, 'url' | 'factory'>): AlarmSocket;
}

function metaContent(name: string): string {
  const el = document.querySelector<HTMLMetaElement>(`meta[name="${name}"]`);
  return el?.content?.trim() ?? '';
}

function isMockMode(): boolean {
  try {
    const params = new URLSearchParams(location.search);
    if (params.get('mock') === '1') return true;
  } catch {
    /* location 不可用时忽略 */
  }
  return metaContent('api-mock') === '1';
}

export function createRuntime(): AppRuntime {
  const apiBase = metaContent('api-base');
  const minioBase = metaContent('minio-base') || 'http://192.168.10.83:19000';
  const mock = isMockMode();

  if (mock) {
    const mockApi = new MockApi();
    const factory = mockApi.alarmSocketFactory();
    return {
      api: mockApi,
      mock: true,
      minioBase,
      createAlarmSocket: (handlers) =>
        new AlarmSocket({ url: 'mock://ws', factory: factory as (u: string) => AlarmSocketLike, ...handlers }),
    };
  }

  return {
    api: new ApiClient(apiBase),
    mock: false,
    minioBase,
    createAlarmSocket: (handlers) => new AlarmSocket({ url: resolveWsUrl(apiBase), ...handlers }),
  };
}
