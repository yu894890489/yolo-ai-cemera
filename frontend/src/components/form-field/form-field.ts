import './form-field.scss';

export type FormFieldOptions = {
  label: string;
  htmlFor: string;
  helpText?: string;
  required?: boolean;
};

export type FormFieldHandle = {
  el: HTMLElement;
  setError(msg: string | null): void;
  setHelp(msg: string): void;
};

/**
 * FormField — 把已有的 <input>/<select>/<textarea> 包成带 label、帮助文本、
 * 校验错误的字段块。不接管输入控件本身，只负责容器与状态。
 */
export function createFormField(control: HTMLElement, opts: FormFieldOptions): FormFieldHandle {
  const wrap = document.createElement('div');
  wrap.className = 'mc-form-field';

  const label = document.createElement('label');
  label.className = 'mc-form-field__label';
  label.htmlFor = opts.htmlFor;
  label.textContent = opts.label;
  if (opts.required) {
    const star = document.createElement('span');
    star.className = 'mc-form-field__required';
    star.textContent = '*';
    label.appendChild(star);
  }

  const slot = document.createElement('div');
  slot.className = 'mc-form-field__control';
  slot.appendChild(control);

  const help = document.createElement('div');
  help.className = 'mc-form-field__help';
  if (opts.helpText) help.textContent = opts.helpText;

  const err = document.createElement('div');
  err.className = 'mc-form-field__error';
  err.hidden = true;

  wrap.append(label, slot, help, err);

  return {
    el: wrap,
    setError(msg) {
      if (msg && msg.length > 0) {
        err.textContent = msg;
        err.hidden = false;
        wrap.classList.add('is-invalid');
      } else {
        err.hidden = true;
        wrap.classList.remove('is-invalid');
      }
    },
    setHelp(msg) {
      help.textContent = msg;
    },
  };
}
