/**
 * 任务创建页的纯校验 / 组装逻辑（与 DOM 解耦，便于单测）。
 */

import type { SourceCreate, TaskCreate } from '@/api/types';

export type ValidationResult<T> =
  | { ok: true; value: T }
  | { ok: false; errors: Record<string, string> };

export interface SourceFormInput {
  name: string;
  protocol: string;
  address: string;
  note?: string;
  enabled?: boolean;
}

/** 校验「新建视频源」表单，对齐 BE-M1-A POST /api/sources 的必填项。 */
export function validateSourceForm(input: SourceFormInput): ValidationResult<SourceCreate> {
  const errors: Record<string, string> = {};
  const name = input.name?.trim() ?? '';
  const protocol = input.protocol?.trim() ?? '';
  const address = input.address?.trim() ?? '';
  if (!name) errors.name = '请填写视频源名称';
  if (!protocol) errors.protocol = '请选择协议';
  if (!address) errors.address = '请填写视频源地址';
  if (Object.keys(errors).length > 0) return { ok: false, errors };
  return {
    ok: true,
    value: {
      name,
      protocol,
      address,
      note: input.note?.trim() ?? '',
      enabled: input.enabled ?? true,
    },
  };
}

export interface TaskFormInput {
  sourceId: string;
  confidence: number;
  roi?: string;
  prompt?: string;
  /** 目标类别（逗号分隔）。BE-M1-A 的创建接口暂无独立字段，折叠进 prompt。 */
  classes?: string;
}

/** 校验并组装 small_crop 任务创建载荷。 */
export function buildTaskPayload(input: TaskFormInput): ValidationResult<TaskCreate> {
  const errors: Record<string, string> = {};
  const sourceId = input.sourceId?.trim() ?? '';
  if (!sourceId) errors.sourceId = '请选择或新建视频源';

  const confidence = input.confidence;
  if (typeof confidence !== 'number' || Number.isNaN(confidence) || confidence < 0 || confidence > 1) {
    errors.confidence = 'confidence 需在 0~1 之间';
  }
  if (Object.keys(errors).length > 0) return { ok: false, errors };

  const classes = (input.classes ?? '')
    .split(',')
    .map((c) => c.trim())
    .filter(Boolean);
  const basePrompt = (input.prompt ?? '').trim();
  const prompt = classes.length
    ? `[关注目标类别: ${classes.join(', ')}] ${basePrompt}`.trim()
    : basePrompt;

  return {
    ok: true,
    value: {
      source_id: sourceId,
      algorithm_id: 'small_crop',
      roi: (input.roi ?? '').trim(),
      prompt,
      confidence,
    },
  };
}
