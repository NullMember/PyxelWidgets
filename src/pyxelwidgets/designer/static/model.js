// The layout model: widget paths, devices and their controls, pages, the selection

import { state, $, el } from './core.js';
import { change } from './history.js';
import { learnButton } from './learn.js';
import { render } from './board.js';
import { setOption, optionField } from './properties.js';

export function childrenOf(path) {
  // The list a widget at `path` lives in (its siblings)
  let list = state.layout.widgets;
  for (const index of path.slice(0, -1)) list = list[index].widgets;
  return list;
}

export function widgetAt(path) {
  return childrenOf(path)[path[path.length - 1]];
}

export function containerSize(path) {
  // Size of the parent of the widget at `path`: a group or the surface
  if (path.length <= 1) return [state.layout.surface.width, state.layout.surface.height];
  const parent = widgetAt(path.slice(0, -1));
  return [parent.width, parent.height];
}

export function absolute(path) {
  let x = 0, y = 0;
  for (let i = 1; i <= path.length; i++) {
    const widget = widgetAt(path.slice(0, i));
    x += widget.x || 0;
    y += widget.y || 0;
  }
  return [x, y];
}

export function allWidgets(list = state.layout.widgets, prefix = []) {
  const found = [];
  list.forEach((widget, index) => {
    const path = [...prefix, index];
    found.push({ widget, path });
    if (widget.widgets) found.push(...allWidgets(widget.widgets, path));
  });
  return found;
}

export function uniqueName(type, reserved = new Set()) {
  const taken = new Set([...allWidgets().map(({ widget }) => widget.name), ...reserved]);
  const base = type.replace(/^./, (c) => c.toLowerCase());
  for (let i = 1; ; i++) if (!taken.has(`${base}${i}`)) return `${base}${i}`;
}

export function deviceInfo(device) {
  return state.catalog.devices.find((info) => info.type === device.type);
}

// Named controls of a layout device; a Launchpad's side buttons are controls with side_buttons off
export function deviceControls(device) {
  const info = deviceInfo(device);
  const controls = [...(info?.controls || [])];
  if (info?.side_buttons && device.options?.side_buttons === false) {
    controls.push(...info.side_buttons.map((button) => ({ name: button.name, kind: 'button' })));
  }
  // Options turning controls into another kind (a MiniLab 3's knobs into encoders)
  for (const [option, kinds] of Object.entries(info?.option_kinds || {})) {
    if (device.options?.[option] !== true) continue;
    controls.forEach((control, i) => { if (control.name in kinds) controls[i] = { ...control, kind: kinds[control.name] }; });
  }
  return controls;
}

// Controls of a layout device with a light links can set; a Launchpad's side buttons with side_buttons off
export function deviceLights(device) {
  const info = deviceInfo(device);
  if (info?.side_buttons) return device.options?.side_buttons === false ? info.lights || [] : [];
  return info?.lights || [];
}

// A layout device's screens links can write to
export function deviceScreens(device) {
  return Object.keys(deviceInfo(device)?.screens || {});
}

// A link target that is a device's control light or screen ({device, control}), not a widget name
export function isDeviceTarget(target) {
  return !!target && typeof target === 'object';
}

// What a link goes to, in words: a widget's name, a device's light or screen, or undefined (the transport, debug)
export function targetLabel(target) {
  if (!isDeviceTarget(target)) return target;
  const entry = state.layout.devices[target.device];
  return `${target.control} · ${target.device + 1}. ${entry ? deviceInfo(entry)?.model || entry.type : 'missing device'}`;
}

function controlKind(binding) {
  const device = state.layout.devices[binding.device];
  return device ? deviceControls(device).find((control) => control.name === binding.control)?.kind : undefined;
}

// ---- what messages and links start from: a widget ({widget}) or a device's control ({device, control})

export function isControlRule(object) {
  return object.widget === undefined && object.control !== undefined;
}

// A device's control as a rule owner, like a widget: {name, label, type: 'control', device, control, kind, events}
export function controlOwner(device, control) {
  const entry = state.layout.devices[device];
  const kind = entry ? deviceControls(entry).find((candidate) => candidate.name === control)?.kind : undefined;
  const all = [...new Set(Object.values(state.catalog.controls).flat())];
  return {
    name: control, label: `${control} · ${device + 1}. ${entry ? deviceInfo(entry)?.model || entry.type : 'missing device'}`,
    type: 'control', device, control, kind, events: state.catalog.controls[kind] || all,
  };
}

// The widget or control a message or link starts from (undefined: not in the layout)
export function ruleOwner(object) {
  if (isControlRule(object)) return state.layout.devices[object.device] ? controlOwner(object.device, object.control) : undefined;
  return allWidgets().find(({ widget }) => widget.name === object.widget)?.widget;
}

export function ownerEvents(owner) {
  return owner?.events || state.catalog.widgets[owner?.type]?.events || [];
}

// The same for a rule and for its owner
export function ownerKey(object) {
  return object.control !== undefined && object.widget === undefined ? `control:${object.device}:${object.control}` : `widget:${object.widget ?? object.name}`;
}

// What a rule of `owner` says it starts from
export function ownerRef(owner) {
  return owner.type === 'control' ? { device: owner.device, control: owner.control } : { widget: owner.name };
}

export function ruleLabel(object) {
  return isControlRule(object) ? controlOwner(object.device, object.control).label : object.widget;
}

// The owners of the layout's control rules, of one device or all, in device and first-use order
export function controlOwners(device = null) {
  const seen = new Map();
  for (const object of [...(state.layout.mappings || []), ...(state.layout.links || [])]) {
    if (!isControlRule(object) || (device !== null && object.device !== device)) continue;
    const key = ownerKey(object);
    if (!seen.has(key)) seen.set(key, controlOwner(object.device, object.control));
  }
  return [...seen.values()].sort((a, b) => a.device - b.device);
}

// Show where a rule starts: select its widget, or its control's device
export function selectOwner(object) {
  if (isControlRule(object)) {
    state.selection = { kind: 'device', index: object.device };
    state.deviceControls[object.device] = object.control;
  } else {
    const found = allWidgets().find(({ widget }) => widget.name === object.widget);
    if (found) state.selection = widgetSelection([found.path]);
  }
  render();
}

// The device and control of a rule from a control, picked or learned; `moved(object)` fixes what
// the new control can't send (its event)
export function controlField(id, object, moved) {
  const set = (device, control) => change(() => {
    if (device === null) return;
    Object.assign(object, { device, control });
    if (!ownerEvents(controlOwner(device, control)).includes(object.on)) moved(object);
  });
  return [
    el('label', { for: id, title: 'The knob, fader, encoder or button of a device it starts from' }, 'control'),
    el('div', { class: 'control learnable' }, controlSelect(id, object, set, false),
      learnButton(id, 'control', (event) => set(event._device, event.control))),
  ];
}

// A select of every device control (or of device `only`'s); calls choose(deviceIndex, control) or choose(null)
export function controlSelect(id, binding, choose, empty = true, only = null) {
  const current = binding ? `${binding.device}:${binding.control}` : '';
  let found = !binding;
  const groups = state.layout.devices.map((device, index) => {
    const controls = deviceControls(device);
    if (!controls.length || (only !== null && index !== only)) return null;
    return el('optgroup', { label: `${index + 1}. ${deviceInfo(device)?.model || device.type}` }, controls.map((control) => {
      const value = `${index}:${control.name}`;
      if (value === current) found = true;
      return el('option', { value, selected: value === current }, `${control.name} (${control.kind})`);
    }));
  });
  return el('select', {
    id,
    onchange: (e) => {
      const value = e.target.value;
      const split = value.indexOf(':');
      if (value) choose(Number(value.slice(0, split)), value.slice(split + 1));
      else choose(null);
    },
  },
  empty ? el('option', { value: '' }, '—') : null,
  groups,
  // Bound to a control the device doesn't list any more (e.g. side buttons turned back on)
  found ? null : el('option', { value: current, selected: true }, `${binding.control} (not available)`));
}

function hasControls() {
  return state.layout.devices.some((device) => deviceControls(device).length);
}

const NO_CONTROLS = 'Add a device with knobs, faders or buttons to bind its controls (on a Launchpad, turn side buttons off).';

function setBinding(match, entry) {
  change((layout) => {
    const bindings = (layout.bindings || []).filter((binding) => !match(binding));
    if (entry) bindings.push(entry);
    if (bindings.length) layout.bindings = bindings;
    else delete layout.bindings;
  });
}

export function bindingFields(widget) {
  const binding = (state.layout.bindings || []).find((b) => b.widget === widget.name);
  if (!binding && !hasControls()) return [el('label', {}, 'control'), el('p', { class: 'hint' }, NO_CONTROLS)];
  const select = controlSelect('widget-control', binding, (device, control) => setBinding(
    (b) => b.widget === widget.name,
    device === null ? null : { device, control, widget: widget.name, ...(binding?.options ? { options: binding.options } : {}) }));
  const kind = binding && controlKind(binding);
  const takeover = binding?.options?.takeover ?? 'Glide';
  const shown = {
    takeover: kind === 'absolute',
    glide_time: kind === 'absolute' && takeover === 'Glide',
    step: kind === 'relative',
    axis: widget.type === 'XY' && kind !== 'button',
  };
  return [
    el('label', { for: 'widget-control', title: 'A device control that drives this widget' }, 'control'),
    el('div', { class: 'control learnable' }, select, learnButton('widget-control', 'control', (event) => setBinding(
      (b) => b.widget === widget.name,
      { device: event._device, control: event.control, widget: widget.name, ...(binding?.options ? { options: binding.options } : {}) }))),
    binding ? state.catalog.binding.options.filter((option) => shown[option.name]).flatMap((option) => optionField(binding, option)) : null,
  ];
}

export function transportControls() {
  if (!hasControls()) return el('p', { class: 'hint' }, NO_CONTROLS);
  return el('div', { class: 'fields' }, state.catalog.binding.actions.flatMap((action) => {
    const binding = (state.layout.bindings || []).find((b) => b.action === action);
    const id = `action-${action.replace('.', '-')}`;
    return [
      el('label', { for: id, title: action === 'surface.reveal' ? 'Shows where each widget is on the devices for 2 seconds' : null }, action === 'surface.reveal' ? 'show widgets' : action.replace('transport.', '')),
      el('div', { class: 'control learnable' }, controlSelect(id, binding, (device, control) => setBinding(
        (b) => b.action === action, device === null ? null : { device, control, action })),
      learnButton(id, 'control', (event) => setBinding((b) => b.action === action, { device: event._device, control: event.control, action }))),
    ];
  }));
}

export function deviceSize(device) {
  const info = deviceInfo(device);
  const options = device.options || {};
  // On-screen and browser grids are as big as their options say
  if (device.type === 'virtual.Virtual' || device.type === 'web.WebGrid') return [options.columns ?? 8, options.rows ?? 8];
  if (options.side_buttons === false && info?.main) return [info.main.width, info.main.height];
  return info ? [info.grid.width, info.grid.height] : [1, 1];
}

export function isGroup(widget) {
  return state.catalog.widgets[widget.type]?.container;
}

// ---------------------------------------------------------------- pages

export function currentPage(pages) {
  return pages.options?.page ?? 0;
}

// The area pages fill: everything besides the selector strip
function pagesContent(pages) {
  const { width: w, height: h } = pages;
  return {
    Off: [0, 0, w, h], Top: [0, 0, w, h - 1], Bottom: [0, 1, w, h - 1], Left: [1, 0, w - 1, h], Right: [0, 0, w - 1, h],
  }[pages.options?.selector ?? 'Top'];
}

// Pages along ``path`` that don't show it: [[pages path, page index], ...]
export function hiddenBy(path) {
  const found = [];
  for (let i = 1; i < path.length; i++) {
    const parent = widgetAt(path.slice(0, i));
    if (parent.type === 'Pages' && path[i] !== currentPage(parent)) found.push([path.slice(0, i), path[i]]);
  }
  return found;
}

export function addPage(path) {
  const pages = widgetAt(path);
  const [x, y, width, height] = pagesContent(pages);
  change(() => {
    pages.widgets = pages.widgets || [];
    pages.widgets.push({ type: 'Group', name: uniqueName('page'), x, y, width, height, options: {}, widgets: [] });
    setOption(pages, 'page', pages.widgets.length - 1 || undefined);
    state.selection = widgetSelection([[...path, pages.widgets.length - 1]]);
  });
}

export function samePath(a, b) {
  return a && b && a.length === b.length && a.every((value, i) => value === b[i]);
}

// ---------------------------------------------------------------- selection

export function widgetSelection(paths, path = paths[paths.length - 1]) {
  return paths.length ? { kind: 'widget', path, paths } : null;
}

export function selectedPaths() {
  return state.selection?.kind === 'widget' ? state.selection.paths : [];
}

export function isSelected(path) {
  return selectedPaths().some((selected) => samePath(selected, path));
}

export function isInside(path, ancestor) {
  return ancestor.length < path.length && samePath(ancestor, path.slice(0, ancestor.length));
}

// Selected widgets without those inside another selected one: what moves, copies and deletes
export function topSelected() {
  const paths = selectedPaths();
  return paths.filter((path) => !paths.some((other) => isInside(path, other)));
}

// Shift/Ctrl/Cmd+click adds a widget to the selection or takes it out
export function toggleSelected(path) {
  const paths = selectedPaths();
  state.selection = isSelected(path)
    ? widgetSelection(paths.filter((selected) => !samePath(selected, path)))
    : widgetSelection([...paths, path]);
  render();
}

// Paths of widget objects, after a change moved them
export function pathsOf(widgets) {
  const found = allWidgets();
  return widgets.map((widget) => found.find((item) => item.widget === widget)?.path).filter(Boolean);
}
