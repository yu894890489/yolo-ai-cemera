import { describe, it, expect } from 'vitest';
import { validateSourceForm, buildTaskPayload } from './task-create.logic';

describe('validateSourceForm', () => {
  it('passes for a complete rtsp source', () => {
    const r = validateSourceForm({ name: '东门', protocol: 'rtsp', address: 'rtsp://x/y' });
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.value.name).toBe('东门');
      expect(r.value.enabled).toBe(true);
    }
  });

  it('flags each missing required field', () => {
    const r = validateSourceForm({ name: '', protocol: '', address: '' });
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.errors.name).toBeTruthy();
      expect(r.errors.protocol).toBeTruthy();
      expect(r.errors.address).toBeTruthy();
    }
  });

  it('trims whitespace-only values to errors', () => {
    const r = validateSourceForm({ name: '  ', protocol: 'rtsp', address: 'rtsp://x' });
    expect(r.ok).toBe(false);
  });
});

describe('buildTaskPayload', () => {
  it('builds a small_crop payload from a selected source', () => {
    const r = buildTaskPayload({
      sourceId: 's1',
      roi: '0,0,640,480',
      confidence: 0.7,
      prompt: '是否有人闯入',
      classes: '',
    });
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.value).toMatchObject({
        source_id: 's1',
        algorithm_id: 'small_crop',
        roi: '0,0,640,480',
        confidence: 0.7,
        prompt: '是否有人闯入',
      });
    }
  });

  it('rejects when no source is selected', () => {
    const r = buildTaskPayload({ sourceId: '', confidence: 0.5 });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.errors.sourceId).toBeTruthy();
  });

  it('rejects confidence outside [0,1]', () => {
    expect(buildTaskPayload({ sourceId: 's1', confidence: 1.5 }).ok).toBe(false);
    expect(buildTaskPayload({ sourceId: 's1', confidence: -0.1 }).ok).toBe(false);
    expect(buildTaskPayload({ sourceId: 's1', confidence: 0 }).ok).toBe(true);
    expect(buildTaskPayload({ sourceId: 's1', confidence: 1 }).ok).toBe(true);
  });

  it('folds target classes into the prompt (BE-M1-A create API has no class field)', () => {
    const r = buildTaskPayload({
      sourceId: 's1',
      confidence: 0.5,
      prompt: '判断是否异常',
      classes: 'person, car',
    });
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.value.prompt).toContain('person');
      expect(r.value.prompt).toContain('car');
      expect(r.value.prompt).toContain('判断是否异常');
    }
  });

  it('defaults prompt/roi to empty strings when omitted', () => {
    const r = buildTaskPayload({ sourceId: 's1', confidence: 0.5 });
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.value.roi).toBe('');
      expect(r.value.prompt).toBe('');
    }
  });
});
