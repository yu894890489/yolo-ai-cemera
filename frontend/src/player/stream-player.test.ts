import { describe, it, expect, vi } from 'vitest';
import { chooseHlsStrategy, StreamPlayer } from './stream-player';

describe('chooseHlsStrategy', () => {
  it('prefers native HLS when the browser can play m3u8 directly (Safari/iOS)', () => {
    expect(chooseHlsStrategy({ nativeHls: true, mseHls: true })).toBe('native');
    expect(chooseHlsStrategy({ nativeHls: true, mseHls: false })).toBe('native');
  });

  it('falls back to hls.js MSE when native HLS is unavailable', () => {
    expect(chooseHlsStrategy({ nativeHls: false, mseHls: true })).toBe('mse');
  });

  it('reports unsupported when neither path works', () => {
    expect(chooseHlsStrategy({ nativeHls: false, mseHls: false })).toBe('unsupported');
  });
});

describe('StreamPlayer', () => {
  it('mounts a video element into the container', () => {
    const container = document.createElement('div');
    const player = new StreamPlayer(container, { canPlayNativeHls: () => true });
    player.play('/hls/t1/index.m3u8');
    const video = container.querySelector('video');
    expect(video).not.toBeNull();
    expect(video?.getAttribute('src')).toBe('/hls/t1/index.m3u8');
    player.destroy();
  });

  it('destroy() removes the video and releases the hls.js instance', () => {
    const destroySpy = vi.fn();
    const fakeHls = {
      loadSource: vi.fn(),
      attachMedia: vi.fn(),
      on: vi.fn(),
      destroy: destroySpy,
    };
    const container = document.createElement('div');
    const player = new StreamPlayer(container, {
      canPlayNativeHls: () => false,
      hlsFactory: () => fakeHls as never,
      isMseSupported: () => true,
    });
    player.play('/hls/t1/index.m3u8');
    expect(fakeHls.loadSource).toHaveBeenCalledWith('/hls/t1/index.m3u8');
    player.destroy();
    expect(destroySpy).toHaveBeenCalledOnce();
    expect(container.querySelector('video')).toBeNull();
  });

  it('switching streams tears down the previous hls.js instance (no leak)', () => {
    const destroyA = vi.fn();
    const destroyB = vi.fn();
    const instances = [
      { loadSource: vi.fn(), attachMedia: vi.fn(), on: vi.fn(), destroy: destroyA },
      { loadSource: vi.fn(), attachMedia: vi.fn(), on: vi.fn(), destroy: destroyB },
    ];
    let i = 0;
    const container = document.createElement('div');
    const player = new StreamPlayer(container, {
      canPlayNativeHls: () => false,
      isMseSupported: () => true,
      hlsFactory: () => instances[i++] as never,
    });
    player.play('/hls/a/index.m3u8');
    player.play('/hls/b/index.m3u8');
    expect(destroyA).toHaveBeenCalledOnce();
    player.destroy();
    expect(destroyB).toHaveBeenCalledOnce();
  });

  it('reports an error via onError when playback is unsupported', () => {
    const onError = vi.fn();
    const container = document.createElement('div');
    const player = new StreamPlayer(container, {
      canPlayNativeHls: () => false,
      isMseSupported: () => false,
      onError,
    });
    player.play('/hls/t1/index.m3u8');
    expect(onError).toHaveBeenCalledOnce();
    player.destroy();
  });
});
