import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ApiClient, ApiError } from './client';

type FetchArgs = { url: string; init: RequestInit };

function mockFetch(impl: (args: FetchArgs) => Response | Promise<Response>) {
  const spy = vi.fn(async (input: string | URL, init?: RequestInit) => {
    return impl({ url: String(input), init: init ?? {} });
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('ApiClient', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('lists sources via GET /api/sources', async () => {
    const fetchSpy = mockFetch(() => jsonResponse([{ id: 's1', name: 'cam' }]));
    const client = new ApiClient('http://api.test');
    const sources = await client.listSources();
    expect(fetchSpy).toHaveBeenCalledOnce();
    const call = fetchSpy.mock.calls[0];
    expect(call[0]).toBe('http://api.test/api/sources');
    expect((call[1]?.method ?? 'GET')).toBe('GET');
    expect(sources).toEqual([{ id: 's1', name: 'cam' }]);
  });

  it('creates a source with POST and JSON body', async () => {
    const fetchSpy = mockFetch(() => jsonResponse({ id: 's2', name: 'door' }, 201));
    const client = new ApiClient('http://api.test');
    await client.createSource({ name: 'door', protocol: 'rtsp', address: 'rtsp://x' });
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe('http://api.test/api/sources');
    expect(init?.method).toBe('POST');
    expect(init?.headers).toMatchObject({ 'Content-Type': 'application/json' });
    expect(JSON.parse(String(init?.body))).toEqual({
      name: 'door',
      protocol: 'rtsp',
      address: 'rtsp://x',
    });
  });

  it('creates a task with POST /api/tasks', async () => {
    const fetchSpy = mockFetch(() => jsonResponse({ id: 't1', status: 'created' }, 201));
    const client = new ApiClient('http://api.test');
    await client.createTask({ source_id: 's1', algorithm_id: 'small_crop', confidence: 0.6 });
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe('http://api.test/api/tasks');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(String(init?.body))).toMatchObject({
      source_id: 's1',
      algorithm_id: 'small_crop',
      confidence: 0.6,
    });
  });

  it('starts a task via POST /api/tasks/:id/start', async () => {
    const fetchSpy = mockFetch(() =>
      jsonResponse({ id: 't1', status: 'running', preview_url: '/hls/t1/index.m3u8' }),
    );
    const client = new ApiClient('http://api.test');
    const task = await client.startTask('t1');
    expect(fetchSpy.mock.calls[0][0]).toBe('http://api.test/api/tasks/t1/start');
    expect(fetchSpy.mock.calls[0][1]?.method).toBe('POST');
    expect(task.preview_url).toBe('/hls/t1/index.m3u8');
  });

  it('stops a task via POST /api/tasks/:id/stop', async () => {
    const fetchSpy = mockFetch(() => jsonResponse({ id: 't1', status: 'stopped' }));
    const client = new ApiClient('http://api.test');
    await client.stopTask('t1');
    expect(fetchSpy.mock.calls[0][0]).toBe('http://api.test/api/tasks/t1/stop');
    expect(fetchSpy.mock.calls[0][1]?.method).toBe('POST');
  });

  it('fetches task status via GET /api/tasks/:id/status', async () => {
    mockFetch(() => jsonResponse({ id: 't1', status: 'running', error_message: '' }));
    const client = new ApiClient('http://api.test');
    const status = await client.getTaskStatus('t1');
    expect(status.status).toBe('running');
  });

  it('fetches runtime status via GET /api/runtime/status', async () => {
    mockFetch(() =>
      jsonResponse({ config_version: 3, task: {}, vlm: { active_provider: 'qwen' } }),
    );
    const client = new ApiClient('http://api.test');
    const rt = await client.getRuntimeStatus();
    expect(rt.config_version).toBe(3);
  });

  it('throws ApiError carrying server error message on non-2xx', async () => {
    mockFetch(() => jsonResponse({ error: 'source_id does not exist' }, 422));
    const client = new ApiClient('http://api.test');
    await expect(client.createTask({ source_id: 'x', algorithm_id: 'small_crop' })).rejects.toThrow(
      ApiError,
    );
    try {
      await client.createTask({ source_id: 'x', algorithm_id: 'small_crop' });
    } catch (e) {
      const err = e as ApiError;
      expect(err.status).toBe(422);
      expect(err.message).toContain('source_id does not exist');
    }
  });

  it('handles 204 No Content (deleteSource) without parsing body', async () => {
    mockFetch(() => new Response(null, { status: 204 }));
    const client = new ApiClient('http://api.test');
    await expect(client.deleteSource('s1')).resolves.toBeUndefined();
  });

  it('normalizes empty baseUrl to same-origin relative requests', async () => {
    const fetchSpy = mockFetch(() => jsonResponse([]));
    const client = new ApiClient('');
    await client.listSources();
    expect(fetchSpy.mock.calls[0][0]).toBe('/api/sources');
  });
});
