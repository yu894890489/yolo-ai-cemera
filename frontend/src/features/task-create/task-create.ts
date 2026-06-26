/**
 * 任务创建页 —— 选择/新建单路视频源 + 配置 small_crop（ROI / 目标类别 / confidence / prompt）+ 提交。
 * 命令式渲染到给定容器，对齐既有组件库风格（无框架）。
 */

import './task-create.scss';
import { createPageHeader, createFormField, Toast, type FormFieldHandle } from '@components/index';
import type { Source, Task } from '@/api/types';
import type { Api as ApiContract } from '@/api/client';
import { ApiError } from '@/api/client';
import { validateSourceForm, buildTaskPayload } from './task-create.logic';

export interface TaskCreateHandle {
  destroy(): void;
}

export interface TaskCreateOptions {
  /** 任务创建成功后的回调（用于跳转监控预览等）。 */
  onCreated?: (task: Task) => void;
}

type Mode = 'existing' | 'new';

export function renderTaskCreate(
  container: HTMLElement,
  api: ApiContract,
  options: TaskCreateOptions = {},
): TaskCreateHandle {
  container.classList.add('mc-task-create');
  container.innerHTML = '';

  container.appendChild(
    createPageHeader({
      title: '创建分析任务',
      subtitle: '单路视频源 · small_crop 协同模式',
      breadcrumbs: [{ label: '首页', href: '/' }, { label: '任务创建' }],
    }),
  );

  const form = document.createElement('form');
  form.className = 'mc-task-create__form';
  form.noValidate = true;
  container.appendChild(form);

  // ---------- 视频源 ----------
  const sourceCard = card('视频源');
  form.appendChild(sourceCard.root);

  const modeRow = document.createElement('div');
  modeRow.className = 'mc-task-create__mode';
  const radioExisting = radio('mc-src-mode', '选择已有视频源', true);
  const radioNew = radio('mc-src-mode', '新建视频源', false);
  modeRow.append(radioExisting.label, radioNew.label);
  sourceCard.body.appendChild(modeRow);

  // 已有源下拉
  const select = document.createElement('select');
  select.className = 'mc-input';
  select.id = 'mc-source-select';
  const selectField = createFormField(select, {
    label: '已有视频源',
    htmlFor: 'mc-source-select',
    helpText: '加载中…',
  });
  sourceCard.body.appendChild(selectField.el);

  // 新建源字段
  const newWrap = document.createElement('div');
  newWrap.className = 'mc-task-create__new-source';
  newWrap.hidden = true;
  const nameInput = textInput('mc-src-name', '例如：东门入口');
  const nameField = createFormField(nameInput, { label: '名称', htmlFor: 'mc-src-name', required: true });
  const protocolSelect = document.createElement('select');
  protocolSelect.className = 'mc-input';
  protocolSelect.id = 'mc-src-protocol';
  ['rtsp', 'rtmp', 'http', 'file'].forEach((p) => {
    const o = document.createElement('option');
    o.value = p;
    o.textContent = p.toUpperCase();
    protocolSelect.appendChild(o);
  });
  const protocolField = createFormField(protocolSelect, {
    label: '协议',
    htmlFor: 'mc-src-protocol',
    required: true,
  });
  const addressInput = textInput('mc-src-address', 'rtsp://192.168.10.83:18554/stream');
  const addressField = createFormField(addressInput, {
    label: '地址',
    htmlFor: 'mc-src-address',
    required: true,
  });
  const noteInput = textInput('mc-src-note', '可选备注');
  const noteField = createFormField(noteInput, { label: '备注', htmlFor: 'mc-src-note' });
  newWrap.append(nameField.el, protocolField.el, addressField.el, noteField.el);
  sourceCard.body.appendChild(newWrap);

  // ---------- 算法配置 ----------
  const cfgCard = card('small_crop 配置');
  form.appendChild(cfgCard.root);

  const algoBadge = document.createElement('div');
  algoBadge.className = 'mc-task-create__algo';
  algoBadge.textContent = '协同模式：small_crop（YOLO 命中后裁剪交云端 VLM 判定）';
  cfgCard.body.appendChild(algoBadge);

  const roiInput = textInput('mc-roi', '例如：0,0,1920,1080 或留空表示全画面');
  const roiField = createFormField(roiInput, {
    label: 'ROI 区域',
    htmlFor: 'mc-roi',
    helpText: '格式 x,y,w,h；留空表示整帧检测',
  });
  cfgCard.body.appendChild(roiField.el);

  const classesInput = textInput('mc-classes', '例如：person, car（逗号分隔，可留空）');
  const classesField = createFormField(classesInput, {
    label: '目标类别',
    htmlFor: 'mc-classes',
    helpText: 'BE-M1-A 创建接口暂无独立类别字段，前端会折叠进 prompt',
  });
  cfgCard.body.appendChild(classesField.el);

  const confInput = document.createElement('input');
  confInput.type = 'range';
  confInput.min = '0';
  confInput.max = '1';
  confInput.step = '0.05';
  confInput.value = '0.5';
  confInput.id = 'mc-confidence';
  confInput.className = 'mc-range';
  const confValue = document.createElement('span');
  confValue.className = 'mc-range__value';
  confValue.textContent = '0.50';
  confInput.addEventListener('input', () => {
    confValue.textContent = Number(confInput.value).toFixed(2);
  });
  const confWrap = document.createElement('div');
  confWrap.className = 'mc-range-wrap';
  confWrap.append(confInput, confValue);
  const confField = createFormField(confWrap, {
    label: '置信度阈值 (confidence)',
    htmlFor: 'mc-confidence',
    helpText: '0~1，越高越严格',
  });
  cfgCard.body.appendChild(confField.el);

  const promptInput = document.createElement('textarea');
  promptInput.className = 'mc-input mc-textarea';
  promptInput.id = 'mc-prompt';
  promptInput.rows = 3;
  promptInput.placeholder = '交给云端 VLM 的判断提示，例如：画面中是否有人闯入禁区？';
  const promptField = createFormField(promptInput, {
    label: 'VLM Prompt',
    htmlFor: 'mc-prompt',
  });
  cfgCard.body.appendChild(promptField.el);

  // ---------- 提交 ----------
  const actions = document.createElement('div');
  actions.className = 'mc-task-create__actions';
  const submitBtn = document.createElement('button');
  submitBtn.type = 'submit';
  submitBtn.className = 'mc-btn mc-btn--primary';
  submitBtn.textContent = '创建任务';
  actions.appendChild(submitBtn);
  form.appendChild(actions);

  // ---------- 行为 ----------
  let mode: Mode = 'existing';
  const setMode = (m: Mode): void => {
    mode = m;
    newWrap.hidden = m !== 'new';
    selectField.el.hidden = m !== 'existing';
  };
  radioExisting.input.addEventListener('change', () => setMode('existing'));
  radioNew.input.addEventListener('change', () => setMode('new'));

  let destroyed = false;
  void loadSources();

  async function loadSources(): Promise<void> {
    try {
      const sources = await api.listSources();
      if (destroyed) return;
      select.innerHTML = '';
      if (sources.length === 0) {
        selectField.setHelp('暂无视频源，请切换到「新建视频源」');
        setMode('new');
        radioNew.input.checked = true;
      } else {
        sources.forEach((s: Source) => {
          const o = document.createElement('option');
          o.value = s.id;
          o.textContent = `${s.name}（${s.protocol}）${s.enabled ? '' : ' · 已禁用'}`;
          select.appendChild(o);
        });
        selectField.setHelp('选择一个已接入的视频源');
      }
    } catch (e) {
      if (destroyed) return;
      selectField.setHelp('加载视频源失败');
      Toast.error(errMsg(e, '加载视频源失败'));
    }
  }

  const clearErrors = (...fields: FormFieldHandle[]): void => fields.forEach((f) => f.setError(null));

  form.addEventListener('submit', (ev) => {
    ev.preventDefault();
    void submit();
  });

  async function submit(): Promise<void> {
    clearErrors(nameField, protocolField, addressField, selectField, confField);
    submitBtn.disabled = true;
    submitBtn.textContent = '提交中…';
    try {
      let sourceId: string;
      if (mode === 'new') {
        const sv = validateSourceForm({
          name: nameInput.value,
          protocol: protocolSelect.value,
          address: addressInput.value,
          note: noteInput.value,
        });
        if (!sv.ok) {
          if (sv.errors.name) nameField.setError(sv.errors.name);
          if (sv.errors.protocol) protocolField.setError(sv.errors.protocol);
          if (sv.errors.address) addressField.setError(sv.errors.address);
          return;
        }
        const created = await api.createSource(sv.value);
        sourceId = created.id;
      } else {
        sourceId = select.value;
      }

      const tv = buildTaskPayload({
        sourceId,
        confidence: Number(confInput.value),
        roi: roiInput.value,
        prompt: promptInput.value,
        classes: classesInput.value,
      });
      if (!tv.ok) {
        if (tv.errors.sourceId) selectField.setError(tv.errors.sourceId);
        if (tv.errors.confidence) confField.setError(tv.errors.confidence);
        return;
      }
      const task = await api.createTask(tv.value);
      Toast.success(`任务已创建（${task.id}）`, '成功');
      options.onCreated?.(task);
      form.reset();
      confValue.textContent = '0.50';
      void loadSources();
    } catch (e) {
      Toast.error(errMsg(e, '创建任务失败'));
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = '创建任务';
    }
  }

  return {
    destroy(): void {
      destroyed = true;
      container.innerHTML = '';
    },
  };
}

function errMsg(e: unknown, fallback: string): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return fallback;
}

function card(title: string): { root: HTMLElement; body: HTMLElement } {
  const root = document.createElement('section');
  root.className = 'mc-card';
  const h = document.createElement('h3');
  h.className = 'mc-card__title';
  h.textContent = title;
  const body = document.createElement('div');
  body.className = 'mc-card__body';
  root.append(h, body);
  return { root, body };
}

function textInput(id: string, placeholder: string): HTMLInputElement {
  const input = document.createElement('input');
  input.type = 'text';
  input.id = id;
  input.className = 'mc-input';
  input.placeholder = placeholder;
  return input;
}

function radio(name: string, label: string, checked: boolean): { label: HTMLLabelElement; input: HTMLInputElement } {
  const wrap = document.createElement('label');
  wrap.className = 'mc-radio';
  const input = document.createElement('input');
  input.type = 'radio';
  input.name = name;
  input.checked = checked;
  const span = document.createElement('span');
  span.textContent = label;
  wrap.append(input, span);
  return { label: wrap, input };
}
