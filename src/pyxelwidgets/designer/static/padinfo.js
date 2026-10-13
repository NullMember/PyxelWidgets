// What a pad does (Try mode): hovering a pad lists the widgets a press reaches, topmost first, with
// the messages and links each sends, worked out for that pad, and what controls them

import { state, fill, el } from './core.js';
import { viewSet } from './prefs.js';
import { deviceInfo, isGroup } from './model.js';
import { ruleText } from './rules.js';

// The pad's own event values: x, y, cell (whole-number sources, with their offset) and {x+1} placeholders
function resolve(value, pad) {
  if (typeof value === 'string') {
    return value.replace(/\{(x|y|cell)([+-]\d+)?\}/g, (_, name, offset) => String(pad[name] + Number(offset || 0)));
  }
  if (Array.isArray(value)) return value.map((item) => resolve(item, pad));
  if (value && typeof value === 'object') {
    if ('source' in value && value.source in pad) return pad[value.source] + (value.offset || 0);
    if ('if' in value || 'choose' in value) return value;
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, resolve(item, pad)]));
  }
  return value;
}

function stops(widget) {
  const option = state.catalog.widgets[widget.type]?.options.find((candidate) => candidate.name === 'propagation');
  return (widget.options?.propagation ?? option?.default) === 'Stop';
}

// [{widget, x, y}] a press at surface x, y reaches, topmost first: children before their group, until a
// widget that stops presses. Plain groups aren't listed (they only hold widgets)
export function widgetsAtPad(px, py) {
  const hidden = viewSet('hidden');
  const found = [];
  const visit = (list, ox, oy) => {
    for (const widget of [...list].reverse()) {
      if (widget.options?.visible === false || hidden.has(widget.name)) continue;
      const x = px - ox - (widget.x || 0), y = py - oy - (widget.y || 0);
      if (x < 0 || y < 0 || x >= widget.width || y >= widget.height) continue;
      if (isGroup(widget)) {
        // A Pages container only shows its current page
        const page = state.pages?.[widget.name] ?? widget.options?.page ?? 0;
        const children = widget.type === 'Pages' ? [widget.widgets?.[page]].filter(Boolean) : widget.widgets || [];
        if (visit(children, ox + (widget.x || 0), oy + (widget.y || 0))) return true;
        if (widget.type === 'Group') continue;
      }
      found.push({ widget, x, y });
      if (stops(widget)) return true;
    }
    return false;
  };
  visit(state.layout.widgets, 0, 0);
  return found;
}

function padSummary(px, py) {
  const reached = widgetsAtPad(px, py);
  if (!reached.length) return [el('p', { class: 'hint' }, 'Nothing here: presses do nothing.')];
  return reached.map(({ widget, x, y }) => {
    const pad = { x, y, cell: x + y * widget.width };
    const lines = [];
    (state.layout.mappings || []).forEach((mapping, index) => {
      if (mapping.widget !== widget.name) return;
      const [when, to, what] = ruleText({ kind: 'mapping', index }, resolve(mapping, pad));
      lines.push(`${when} → ${to}: ${what}`);
    });
    (state.layout.links || []).forEach((link, index) => {
      if (link.widget !== widget.name) return;
      const [when, to, what] = ruleText({ kind: 'link', index }, resolve(link, pad));
      lines.push(`${when} → ${to}: ${what}`);
    });
    for (const binding of state.layout.bindings || []) {
      if (binding.widget !== widget.name) continue;
      const device = state.layout.devices[binding.device];
      lines.push(`moved by ${binding.control} (${deviceInfo(device)?.model || device?.type || 'device'})`);
    }
    return el('div', { class: 'reached' },
      el('div', { class: 'head' }, el('b', {}, widget.name), ` ${widget.type} · pad ${x}, ${y} · cell ${pad.cell}`),
      lines.length ? el('ul', {}, lines.map((line) => el('li', {}, line))) : el('p', { class: 'hint' }, 'No messages or links'));
  });
}

let shown = null;

export function showPadInfo(event) {
  if (state.mode !== 'try') return hidePadInfo();
  const x = Number(event.currentTarget.dataset.x), y = Number(event.currentTarget.dataset.y);
  let box = document.getElementById('pad-info');
  if (!box) {
    box = el('div', { id: 'pad-info', role: 'tooltip' });
    document.body.append(box);
  }
  if (shown !== `${x},${y}`) {
    shown = `${x},${y}`;
    fill(box, el('div', { class: 'title' }, `Pad ${x}, ${y}`), padSummary(x, y));
  }
  box.hidden = false;
  // Beside the pointer, inside the window
  const gap = 16, { innerWidth, innerHeight } = window, rect = box.getBoundingClientRect();
  const left = event.clientX + gap + rect.width > innerWidth ? event.clientX - gap - rect.width : event.clientX + gap;
  const top = Math.min(event.clientY + gap, innerHeight - rect.height - 8);
  box.style.left = `${Math.max(8, left)}px`;
  box.style.top = `${Math.max(8, top)}px`;
}

export function hidePadInfo() {
  shown = null;
  const box = document.getElementById('pad-info');
  if (box) box.hidden = true;
}
