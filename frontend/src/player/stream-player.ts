/**
 * StreamPlayer — 单路视频预览播放器。
 *
 * 后端 BE-M1-A 任务启动后返回 HLS 地址（/hls/{task_id}/index.m3u8），因此这里以 HLS 为主：
 *   - 浏览器原生支持 HLS（Safari/iOS）→ 直接 video.src；
 *   - 否则用 hls.js 走 MSE；
 *   - 都不支持 → onError 上报。
 *
 * 关键约束（来自 FE-M0-07 验收）：单实例自适应尺寸、切流/销毁必须释放 hls.js 实例，避免内存泄漏。
 */

import Hls from 'hls.js';

export type HlsStrategy = 'native' | 'mse' | 'unsupported';

export interface HlsCaps {
  nativeHls: boolean;
  mseHls: boolean;
}

/** 纯决策：原生优先，其次 hls.js，再否则不支持。 */
export function chooseHlsStrategy(caps: HlsCaps): HlsStrategy {
  if (caps.nativeHls) return 'native';
  if (caps.mseHls) return 'mse';
  return 'unsupported';
}

interface HlsLike {
  loadSource(url: string): void;
  attachMedia(video: HTMLVideoElement): void;
  on(event: unknown, cb: (...args: unknown[]) => void): void;
  destroy(): void;
}

export interface StreamPlayerOptions {
  autoplay?: boolean;
  muted?: boolean;
  controls?: boolean;
  onError?: (err: unknown) => void;
  onStrategy?: (strategy: HlsStrategy) => void;
  /** 测试可注入：是否支持原生 HLS。 */
  canPlayNativeHls?: () => boolean;
  /** 测试可注入：是否支持 hls.js（MSE）。 */
  isMseSupported?: () => boolean;
  /** 测试可注入：hls.js 实例工厂。 */
  hlsFactory?: () => HlsLike;
}

export class StreamPlayer {
  private readonly container: HTMLElement;
  private readonly opts: StreamPlayerOptions;
  private video: HTMLVideoElement | null = null;
  private hls: HlsLike | null = null;

  constructor(container: HTMLElement, options: StreamPlayerOptions = {}) {
    this.container = container;
    this.opts = options;
    this.container.classList.add('mc-stream-player');
  }

  /** 播放给定地址；重复调用会先释放上一路再播放新流。 */
  play(url: string): void {
    this.teardownStream();
    const video = this.ensureVideo();

    const caps: HlsCaps = {
      nativeHls: this.canPlayNativeHls(),
      mseHls: this.isMseSupported(),
    };
    const strategy = chooseHlsStrategy(caps);
    this.opts.onStrategy?.(strategy);

    if (strategy === 'native') {
      video.src = url;
      video.load?.();
      this.tryAutoplay(video);
      return;
    }
    if (strategy === 'mse') {
      const hls = (this.opts.hlsFactory ?? (() => new Hls({ enableWorker: true }) as HlsLike))();
      this.hls = hls;
      hls.on(Hls.Events.ERROR, (...args: unknown[]) => {
        // 仅致命错误上报，非致命由 hls.js 自行恢复。
        const data = args[1] as { fatal?: boolean } | undefined;
        if (data?.fatal) this.opts.onError?.(data);
      });
      hls.loadSource(url);
      hls.attachMedia(video);
      this.tryAutoplay(video);
      return;
    }
    this.opts.onError?.(new Error('当前浏览器不支持 HLS 播放'));
  }

  /** 停止播放并彻底清理 DOM 与 hls.js 实例。 */
  destroy(): void {
    this.teardownStream();
    if (this.video) {
      this.video.remove();
      this.video = null;
    }
  }

  private ensureVideo(): HTMLVideoElement {
    if (this.video) return this.video;
    const video = document.createElement('video');
    video.className = 'mc-stream-player__video';
    video.playsInline = true;
    video.controls = this.opts.controls ?? true;
    video.muted = this.opts.muted ?? true;
    video.autoplay = this.opts.autoplay ?? true;
    this.container.appendChild(video);
    this.video = video;
    return video;
  }

  private teardownStream(): void {
    if (this.hls) {
      this.hls.destroy();
      this.hls = null;
    }
    if (this.video) {
      this.video.removeAttribute('src');
      this.video.load?.();
    }
  }

  private tryAutoplay(video: HTMLVideoElement): void {
    if (this.opts.autoplay === false) return;
    const p = video.play?.();
    if (p && typeof p.catch === 'function') p.catch(() => undefined);
  }

  private canPlayNativeHls(): boolean {
    if (this.opts.canPlayNativeHls) return this.opts.canPlayNativeHls();
    const probe = document.createElement('video');
    return probe.canPlayType('application/vnd.apple.mpegurl') !== '';
  }

  private isMseSupported(): boolean {
    if (this.opts.isMseSupported) return this.opts.isMseSupported();
    return Hls.isSupported();
  }
}
