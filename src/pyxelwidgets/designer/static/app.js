// PyxelWidgets Designer: edits a layout (see pyxelwidgets.parser) and shows a
// live preview rendered by the Python widgets through the designer server.

const DEFAULT_SIZE = {
  Button: [1, 1], ButtonGroup: [4, 1], Fader: [1, 8], Keyboard: [8, 4], Knob: [3, 3],
  Sequencer: [8, 4], Sprite: [2, 2], Text: [8, 5], Tracker: [4, 8], XY: [4, 4],
};
const RHYTHMIC = new Set(['Sequencer', 'Tracker']);
const EVENTS = {
  Button: ['Changed', 'e.value'], Fader: ['Changed', 'e.value'], Knob: ['Changed', 'e.value'], XY: ['Changed', 'e.value'],
  Keyboard: ['NoteOn', 'e.note, e.velocity'], ButtonGroup: ['Toggled', 'e.x, e.y, e.state'],
  Sequencer: ['StepPlayed', 'e.step, e.active'], Tracker: ['RowPlayed', 'e.row, e.columns'],
};

const state = {
  catalog: null,
  layout: null,
  file: null,
  saved: '',
  selection: null, // null (surface) | {kind: 'widget', path: [i, j, ...]} | {kind: 'device', index}
  mode: 'edit',
  history: [],
  future: [],
  lastEvent: 0,
  playing: false,
  hardware: { enabled: false, devices: [] },
  error: null,
  frameSize: [0, 0],
};

const $ = (id) => document.getElementById(id);

function fill(node, ...children) {
  node.replaceChildren(...children.flat(Infinity).filter((child) => child != null));
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === 'class') node.className = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else if (value === true) node.setAttribute(key, '');
    else if (value !== false && value != null) node.setAttribute(key, value);
  }
  for (const child of children.flat(Infinity)) {
    if (child != null) node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

async function api(method, path, body) {
  const response = await fetch(path, {
    method,
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  return { ok: response.ok, ...data };
}

// ---------------------------------------------------------------- layout model

function childrenOf(path) {
  // The list a widget at `path` lives in (its siblings)
  let list = state.layout.widgets;
  for (const index of path.slice(0, -1)) list = list[index].widgets;
  return list;
}

function widgetAt(path) {
  return childrenOf(path)[path[path.length - 1]];
}

function containerSize(path) {
  // Size of the parent of the widget at `path`: a group or the surface
  if (path.length <= 1) return [state.layout.surface.width, state.layout.surface.height];
  const parent = widgetAt(path.slice(0, -1));
  return [parent.width, parent.height];
}

function absolute(path) {
  let x = 0, y = 0;
  for (let i = 1; i <= path.length; i++) {
    const widget = widgetAt(path.slice(0, i));
    x += widget.x || 0;
    y += widget.y || 0;
  }
  return [x, y];
}

function allWidgets(list = state.layout.widgets, prefix = []) {
  const found = [];
  list.forEach((widget, index) => {
    const path = [...prefix, index];
    found.push({ widget, path });
    if (widget.widgets) found.push(...allWidgets(widget.widgets, path));
  });
  return found;
}

function uniqueName(type, reserved = new Set()) {
  const taken = new Set([...allWidgets().map(({ widget }) => widget.name), ...reserved]);
  const base = type.replace(/^./, (c) => c.toLowerCase());
  for (let i = 1; ; i++) if (!taken.has(`${base}${i}`)) return `${base}${i}`;
}

function deviceInfo(device) {
  return state.catalog.devices.find((info) => info.type === device.type);
}

// Named controls of a layout device; a Launchpad's side buttons are controls with side_buttons off
function deviceControls(device) {
  const info = deviceInfo(device);
  const controls = [...(info?.controls || [])];
  if (info?.side_buttons && device.options?.side_buttons === false) {
    controls.push(...info.side_buttons.map((button) => ({ name: button.name, kind: 'button' })));
  }
  return controls;
}

function controlKind(binding) {
  const device = state.layout.devices[binding.device];
  return device ? deviceControls(device).find((control) => control.name === binding.control)?.kind : undefined;
}

// A select of every device control; calls choose(deviceIndex, control) or choose(null)
function controlSelect(id, binding, choose) {
  const current = binding ? `${binding.device}:${binding.control}` : '';
  let found = !binding;
  const groups = state.layout.devices.map((device, index) => {
    const controls = deviceControls(device);
    if (!controls.length) return null;
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
  el('option', { value: '' }, '—'),
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

function bindingFields(widget) {
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
    el('div', { class: 'control' }, select),
    binding ? state.catalog.binding.options.filter((option) => shown[option.name]).flatMap((option) => optionField(binding, option)) : null,
  ];
}

function transportControls() {
  if (!hasControls()) return el('p', { class: 'hint' }, NO_CONTROLS);
  return el('div', { class: 'fields' }, state.catalog.binding.actions.flatMap((action) => {
    const binding = (state.layout.bindings || []).find((b) => b.action === action);
    const id = `action-${action.replace('.', '-')}`;
    return [
      el('label', { for: id }, action.replace('transport.', '')),
      el('div', { class: 'control' }, controlSelect(id, binding, (device, control) => setBinding(
        (b) => b.action === action, device === null ? null : { device, control, action }))),
    ];
  }));
}

function deviceSize(device) {
  const info = deviceInfo(device);
  const options = device.options || {};
  if (device.type === 'virtual.Virtual') return [options.columns ?? 8, options.rows ?? 8];
  if (options.side_buttons === false && info?.main) return [info.main.width, info.main.height];
  return info ? [info.grid.width, info.grid.height] : [1, 1];
}

function isGroup(widget) {
  return state.catalog.widgets[widget.type]?.container;
}

// ---------------------------------------------------------------- pages

function currentPage(pages) {
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
function hiddenBy(path) {
  const found = [];
  for (let i = 1; i < path.length; i++) {
    const parent = widgetAt(path.slice(0, i));
    if (parent.type === 'Pages' && path[i] !== currentPage(parent)) found.push([path.slice(0, i), path[i]]);
  }
  return found;
}

function addPage(path) {
  const pages = widgetAt(path);
  const [x, y, width, height] = pagesContent(pages);
  change(() => {
    pages.widgets = pages.widgets || [];
    pages.widgets.push({ type: 'Group', name: uniqueName('page'), x, y, width, height, options: {}, widgets: [] });
    setOption(pages, 'page', pages.widgets.length - 1 || undefined);
    state.selection = { kind: 'widget', path: [...path, pages.widgets.length - 1] };
  });
}

function samePath(a, b) {
  return a && b && a.length === b.length && a.every((value, i) => value === b[i]);
}

// ---------------------------------------------------------------- history and sync

function change(mutate) {
  state.history.push(JSON.stringify(state.layout));
  if (state.history.length > 300) state.history.shift();
  state.future = [];
  mutate(state.layout);
  render();
  scheduleSync();
}

function replaceLayout(layout) {
  state.history.push(JSON.stringify(state.layout));
  state.future = [];
  state.layout = layout;
  state.selection = null;
  render();
  scheduleSync();
}

function undo() {
  if (!state.history.length) return;
  state.future.push(JSON.stringify(state.layout));
  state.layout = JSON.parse(state.history.pop());
  checkSelection();
  render();
  scheduleSync();
}

function redo() {
  if (!state.future.length) return;
  state.history.push(JSON.stringify(state.layout));
  state.layout = JSON.parse(state.future.pop());
  checkSelection();
  render();
  scheduleSync();
}

function checkSelection() {
  const selection = state.selection;
  if (selection?.kind === 'widget') {
    try { if (!widgetAt(selection.path)) state.selection = null; } catch { state.selection = null; }
  } else if (selection?.kind === 'device' && !state.layout.devices[selection.index]) {
    state.selection = null;
  }
}

let syncTimer = null;
let syncing = Promise.resolve();
function scheduleSync() {
  clearTimeout(syncTimer);
  syncTimer = setTimeout(sync, 120);
  renderDirty();
}

// Send a pending layout change now; resolves once the preview has it
function flushSync() {
  if (syncTimer !== null) sync();
  return syncing;
}

function sync() {
  clearTimeout(syncTimer);
  syncTimer = null;
  syncing = syncing.then(putLayout, putLayout);
  return syncing;
}

async function putLayout() {
  const reply = await api('PUT', '/api/layout', state.layout);
  if (reply.ok) {
    if (state.error) setStatus('');
    state.error = null;
  } else {
    state.error = reply.error;
    setStatus(reply.error, 'error');
  }
}

let statusTimer = null;
function setStatus(text, kind = '') {
  const status = $('status');
  status.textContent = text;
  status.className = kind;
  clearTimeout(statusTimer);
  if (kind === 'ok') statusTimer = setTimeout(() => setStatus(state.error || '', state.error ? 'error' : ''), 2500);
}

// ---------------------------------------------------------------- preview

async function poll() {
  try {
    const frame = await api('GET', `/api/frame?since=${state.lastEvent}`);
    paint(frame);
    addEvents(frame.events);
    if (frame.playing !== state.playing) {
      state.playing = frame.playing;
      renderToolbar();
    }
    $('position').textContent = frame.position ? `bar ${frame.position}` : '';
    if (JSON.stringify(frame.hardware) !== JSON.stringify(state.hardware)) {
      state.hardware = frame.hardware;
      renderToolbar();
      renderDevices();
    }
  } catch {
    setStatus('Lost connection to the designer server', 'error');
  }
  setTimeout(poll, document.hidden ? 500 : 80);
}

function paint(frame) {
  if (frame.width !== state.frameSize[0] || frame.height !== state.frameSize[1]) return;
  const pads = $('pads').children;
  frame.pixels.forEach((row, top) => row.forEach((color, x) => {
    const pad = pads[top * frame.width + x];
    if (pad && pad.dataset.color !== color) {
      pad.dataset.color = color;
      pad.style.backgroundColor = color;
    }
  }));
}

function addEvents(events) {
  if (!events.length) return;
  const list = $('events');
  for (const event of events) {
    state.lastEvent = Math.max(state.lastEvent, event.id);
    const fields = Object.entries(event)
      .filter(([key]) => !['id', 'widget', 'event'].includes(key))
      .map(([key, value]) => `${key}=${Array.isArray(value) ? `[${value}]` : value}`)
      .join(' ');
    list.prepend(el('li', { title: `${event.widget} ${event.event} ${fields}` },
      el('b', {}, event.widget), ' ', el('span', { class: 'kind' }, event.event), ' ', fields));
  }
  while (list.children.length > 200) list.lastChild.remove();
}

// Input goes in order, and after any pending layout change: rebuilding the preview resets widget state
let inputs = Promise.resolve();
function sendInput(x, y, velocity) {
  inputs = inputs.then(flushSync).then(() => api('POST', '/api/input', { x, y, velocity })).catch(() => {});
}

const held = new Map();
function padDown(event) {
  if (state.mode !== 'try') {
    state.selection = null;
    render();
    return;
  }
  const { x, y } = event.currentTarget.dataset;
  event.currentTarget.setPointerCapture(event.pointerId);
  held.set(event.pointerId, [Number(x), Number(y)]);
  sendInput(Number(x), Number(y), 1.0);
}

function padUp(event) {
  const pad = held.get(event.pointerId);
  if (!pad) return;
  held.delete(event.pointerId);
  sendInput(pad[0], pad[1], 0.0);
}

// ---------------------------------------------------------------- rendering

function render() {
  renderBoard();
  renderOverlay();
  renderTree();
  renderDevices();
  renderProperties();
  renderCode();
  renderToolbar();
  renderDirty();
}

function step() {
  const style = getComputedStyle(document.documentElement);
  return parseFloat(style.getPropertyValue('--pad')) + parseFloat(style.getPropertyValue('--gap'));
}

function renderBoard() {
  const { width, height } = state.layout.surface;
  const stage = $('stage');
  const gap = 4;
  const fit = (space, count) => Math.floor((space - 80 - gap * (count - 1)) / count);
  const pad = Math.max(22, Math.min(64, fit(stage.clientWidth, width), fit(stage.clientHeight - 40, height)));
  document.documentElement.style.setProperty('--pad', `${pad}px`);
  if (state.frameSize[0] === width && state.frameSize[1] === height) return;
  state.frameSize = [width, height];
  const pads = $('pads');
  pads.style.gridTemplateColumns = `repeat(${width}, var(--pad))`;
  pads.replaceChildren();
  for (let top = 0; top < height; top++) {
    for (let x = 0; x < width; x++) {
      pads.append(el('div', {
        class: 'pad', dataset: { x, y: height - 1 - top },
        onpointerdown: padDown, onpointerup: padUp, onpointercancel: padUp,
      }));
    }
  }
}

function place(node, x, y, width, height) {
  const size = step();
  const surfaceHeight = state.layout.surface.height;
  node.style.left = `${x * size - 2}px`;
  node.style.top = `${(surfaceHeight - y - height) * size - 2}px`;
  node.style.width = `${width * size - 4 + 4}px`;
  node.style.height = `${height * size - 4 + 4}px`;
}

function renderOverlay() {
  const overlay = $('overlay');
  overlay.replaceChildren();
  state.layout.devices.forEach((device, index) => {
    const [width, height] = deviceSize(device);
    const outline = el('div', { class: 'outline device' }, el('span', { class: 'tag' }, deviceInfo(device)?.model || device.type));
    place(outline, device.x || 0, device.y || 0, width, height);
    overlay.append(outline);
  });
  for (const { widget, path } of allWidgets()) {
    const [x, y] = absolute(path);
    const selected = state.selection?.kind === 'widget' && samePath(state.selection.path, path);
    // Widgets on other pages of a Pages aren't shown
    if (hiddenBy(path).length && !selected) continue;
    const hidden = widget.options?.visible === false;
    const outline = el('div', {
      class: `outline widget${isGroup(widget) ? ' group' : ''}${selected ? ' selected' : ''}`,
      title: `${widget.name} (${widget.type})`,
      onpointerdown: (event) => startDrag(event, path, 'move'),
    }, el('span', { class: 'tag' }, widget.name));
    if (hidden) outline.style.opacity = 0.35;
    if (selected) outline.append(el('div', { class: 'handle', onpointerdown: (event) => startDrag(event, path, 'resize') }));
    place(outline, x, y, widget.width, widget.height);
    overlay.append(outline);
  }
}

function startDrag(event, path, kind) {
  if (state.mode !== 'edit' || event.button !== 0) return;
  event.stopPropagation();
  event.preventDefault();
  if (!(state.selection?.kind === 'widget' && samePath(state.selection.path, path))) {
    state.selection = { kind: 'widget', path };
    render();
  }
  const widget = widgetAt(path);
  const [parentWidth, parentHeight] = containerSize(path);
  const origin = { x: widget.x || 0, y: widget.y || 0, width: widget.width, height: widget.height };
  const start = [event.clientX, event.clientY];
  const target = [...$('overlay').querySelectorAll('.outline.widget')].find((node) => node.classList.contains('selected'));
  let result = origin;
  const move = (e) => {
    const dx = Math.round((e.clientX - start[0]) / step());
    const dy = -Math.round((e.clientY - start[1]) / step());
    if (kind === 'move') {
      result = {
        ...origin,
        x: Math.max(0, Math.min(parentWidth - origin.width, origin.x + dx)),
        y: Math.max(0, Math.min(parentHeight - origin.height, origin.y + dy)),
      };
    } else {
      result = {
        ...origin,
        width: Math.max(1, Math.min(parentWidth - origin.x, origin.width + dx)),
        height: Math.max(1, Math.min(parentHeight - origin.y, origin.height + dy)),
      };
    }
    const [ax, ay] = absolute(path);
    if (target) place(target, ax - origin.x + result.x, ay - origin.y + result.y, result.width, result.height);
  };
  const up = () => {
    window.removeEventListener('pointermove', move);
    window.removeEventListener('pointerup', up);
    if (['x', 'y', 'width', 'height'].some((key) => result[key] !== origin[key])) {
      change(() => Object.assign(widgetAt(path), { x: result.x, y: result.y, width: result.width, height: result.height }));
    }
  };
  window.addEventListener('pointermove', move);
  window.addEventListener('pointerup', up);
}

function renderTree() {
  const build = (list, prefix) => el('ul', {}, [...list.entries()].reverse().map(([index, widget]) => {
    const path = [...prefix, index];
    const selected = state.selection?.kind === 'widget' && samePath(state.selection.path, path);
    const visible = widget.options?.visible !== false;
    const offPage = widget.type !== undefined && prefix.length && widgetAt(prefix).type === 'Pages' && index !== currentPage(widgetAt(prefix));
    return el('li', {},
      el('div', {
        class: `node${selected ? ' selected' : ''}${offPage ? ' off-page' : ''}`,
        title: offPage ? 'Another page: selecting it shows that page' : null,
        onclick: () => {
          const hidden = hiddenBy(path);
          if (!hidden.length) return select({ kind: 'widget', path });
          // Show the page the widget is on
          change(() => {
            for (const [pagesPath, page] of hidden) setOption(widgetAt(pagesPath), 'page', page || undefined);
            state.selection = { kind: 'widget', path };
          });
        },
      },
        el('button', {
          class: `eye${visible ? '' : ' hidden'}`, title: visible ? 'Hide' : 'Show',
          onclick: (event) => {
            event.stopPropagation();
            change(() => setOption(widgetAt(path), 'visible', visible ? false : undefined));
          },
        }, visible ? '◉' : '○'),
        el('span', { class: 'name' }, widget.name),
        el('span', { class: 'type' }, widget.type)),
      widget.widgets?.length ? build(widget.widgets, path) : null);
  }));
  const tree = $('tree');
  tree.replaceChildren(...build(state.layout.widgets, []).children);
  if (!state.layout.widgets.length) tree.append(el('li', { class: 'hint' }, 'No widgets yet.'));
}

function renderDevices() {
  const list = $('devices');
  list.replaceChildren(...state.layout.devices.map((device, index) => {
    const selected = state.selection?.kind === 'device' && state.selection.index === index;
    return el('li', { class: selected ? 'selected' : '', onclick: () => select({ kind: 'device', index }) },
      el('span', { class: 'swatch-device' }),
      el('span', { class: 'name' }, deviceInfo(device)?.model || device.type),
      hardwareDot(index),
      el('span', { class: 'type' }, `at ${device.x || 0}, ${device.y || 0}`));
  }));
  if (!state.layout.devices.length) list.append(el('li', { class: 'hint' }, 'Preview only. Add the hardware the layout runs on.'));
}

function hardwareDot(index) {
  if (!state.hardware.enabled) return null;
  const status = state.hardware.devices[index];
  if (!status) return el('span', { class: 'dot', title: 'Connecting…' });
  return el('span', {
    class: `dot ${status.connected ? 'on' : 'off'}`,
    title: status.connected ? 'Connected: mirrors the preview, pads work the widgets' : status.error,
  });
}

function select(selection) {
  state.selection = selection;
  render();
}

function setOption(target, name, value) {
  target.options = target.options || {};
  if (value === undefined) delete target.options[name];
  else target.options[name] = value;
}

// A labelled editor for one option from the catalog schema
function optionField(target, option) {
  const options = target.options || {};
  const set = option.name in options;
  const value = set ? options[option.name] : option.default;
  const commit = (newValue) => change(() => setOption(target, option.name, newValue));
  let control, suggestions;
  switch (option.kind) {
    case 'enum':
      control = el('select', { onchange: (e) => commit(e.target.value) },
        option.choices.map((choice) => el('option', { value: choice, selected: choice === value }, choice)));
      break;
    case 'bool':
      control = el('input', { type: 'checkbox', checked: !!value, onchange: (e) => commit(e.target.checked) });
      break;
    case 'int':
    case 'float':
      control = el('input', {
        type: 'number', step: option.kind === 'int' ? 1 : 0.01, value: value ?? '', placeholder: value == null ? 'auto' : null,
        onchange: (e) => commit(e.target.value === '' ? undefined : (option.kind === 'int' ? parseInt(e.target.value, 10) : parseFloat(e.target.value))),
      });
      break;
    case 'color': {
      const text = value || '#000000';
      const rgb = text.slice(0, 7);
      const alpha = text.length === 9 ? parseInt(text.slice(7), 16) : 255;
      const picker = el('input', { type: 'color', value: rgb });
      const slider = el('input', { type: 'range', min: 0, max: 255, value: alpha, title: 'Opacity' });
      const update = () => commit(picker.value + (Number(slider.value) === 255 ? '' : Number(slider.value).toString(16).padStart(2, '0')));
      picker.addEventListener('change', update);
      slider.addEventListener('change', update);
      control = el('div', { class: 'color' }, picker, slider);
      break;
    }
    case 'point': {
      const point = value || [0, 0];
      const axis = (i) => el('input', {
        type: 'number', step: 0.01, value: point[i],
        onchange: (e) => commit(point.map((v, j) => (j === i ? parseFloat(e.target.value) : v))),
      });
      control = el('div', { class: 'control' }, axis(0), axis(1));
      break;
    }
    case 'rate':
      // Any note value is accepted; the list only suggests common ones
      control = el('input', { type: 'text', value: value ?? '', list: `rates-${option.name}`, onchange: (e) => commit(e.target.value.trim() || undefined) });
      suggestions = el('datalist', { id: `rates-${option.name}` }, option.choices.map((choice) => el('option', { value: choice })));
      break;
    default:
      control = el('input', { type: 'text', value: value ?? '', onchange: (e) => commit(e.target.value) });
  }
  const id = `option-${option.name}`;
  control.id = id;
  return [
    el('label', { for: id, class: set ? 'changed' : '', title: option.name }, option.name.replace(/_/g, ' ')),
    el('div', { class: 'control' }, control, suggestions,
      el('button', { class: 'link reset', title: `Reset to ${JSON.stringify(option.default)}`, onclick: () => commit(undefined) }, 'reset')),
  ];
}

function numberInput(label, value, onchange, attrs = {}) {
  return el('label', {}, label, el('input', { type: 'number', value, step: 1, ...attrs, onchange: (e) => onchange(parseInt(e.target.value, 10)) }));
}

function renderProperties() {
  const panel = $('properties');
  const selection = state.selection;
  if (selection?.kind === 'widget') {
    const path = selection.path;
    const widget = widgetAt(path);
    const info = state.catalog.widgets[widget.type];
    const [parentWidth, parentHeight] = containerSize(path);
    const setGeometry = (key) => (value) => {
      if (Number.isNaN(value)) return render();
      // Keep the widget inside its parent, like dragging does
      const x = widget.x || 0, y = widget.y || 0;
      const limits = {
        x: [0, parentWidth - widget.width], y: [0, parentHeight - widget.height],
        width: [1, parentWidth - x], height: [1, parentHeight - y],
      }[key];
      value = Math.max(limits[0], Math.min(limits[1], value));
      if (value === (widget[key] ?? 0)) return render();
      change(() => { widget[key] = value; });
    };
    fill(panel,
      el('h3', {}, widget.type),
      el('p', { class: 'doc' }, (info?.doc || '').replace(/``/g, '')),
      el('div', { class: 'quad' },
        numberInput('x', widget.x || 0, setGeometry('x'), { min: 0, max: parentWidth - 1 }),
        numberInput('y', widget.y || 0, setGeometry('y'), { min: 0, max: parentHeight - 1 }),
        numberInput('width', widget.width, setGeometry('width'), { min: 1 }),
        numberInput('height', widget.height, setGeometry('height'), { min: 1 })),
      el('div', { class: 'fields' },
        el('label', { for: 'widget-name' }, 'name'),
        el('div', { class: 'control' }, el('input', {
          type: 'text', id: 'widget-name', value: widget.name,
          onchange: (e) => {
            const name = e.target.value.trim();
            if (!name || allWidgets().some((item) => item.widget !== widget && item.widget.name === name)) {
              setStatus(`Widget name "${name}" is empty or already used`, 'error');
              return render();
            }
            change((layout) => {
              for (const binding of layout.bindings || []) if (binding.widget === widget.name) binding.widget = name;
              widget.name = name;
            });
          },
        })),
        (info?.options || []).flatMap((option) => optionField(widget, option)),
        info?.bindable ? bindingFields(widget) : null),
      el('div', { class: 'actions' },
        el('button', { onclick: () => reorder(path, 1), title: 'Draw above the next widget' }, 'Raise'),
        el('button', { onclick: () => reorder(path, -1), title: 'Draw below the previous widget' }, 'Lower'),
        el('button', { onclick: () => duplicate(path), title: 'Ctrl+D' }, 'Duplicate'),
        el('button', { class: 'danger', onclick: () => removeSelection(), title: 'Delete' }, 'Delete')),
      widget.type === 'Pages' ? [
        el('p', { class: 'hint' }, `Page ${currentPage(widget) + 1} of ${widget.widgets?.length || 0} shown. Widgets added from the palette go on it; select a widget in Layers to show its page.`),
        el('div', { class: 'actions' }, el('button', { onclick: () => addPage(path) }, 'Add page')),
      ] : isGroup(widget) ? el('p', { class: 'hint' }, 'Widgets added from the palette go inside this group.') : null,
    );
    return;
  }
  if (selection?.kind === 'device') {
    const device = state.layout.devices[selection.index];
    const info = deviceInfo(device);
    const [width, height] = deviceSize(device);
    const port = (key, label) => [
      el('label', { for: `device-${key}` }, label),
      el('div', { class: 'control' }, el('input', {
        type: 'text', id: `device-${key}`, value: device[key] || '', placeholder: 'find by name',
        onchange: (e) => change(() => { if (e.target.value) device[key] = e.target.value; else delete device[key]; }),
      })),
    ];
    fill(panel,
      el('h3', {}, info?.model || device.type),
      el('p', { class: 'doc' }, `${device.type} · ${width}×${height} pads${info?.ports?.length ? ` · ports matching ${info.ports.join(', ')}` : ''}`),
      el('div', { class: 'quad' },
        numberInput('x', device.x || 0, (v) => change(() => { device.x = v; })),
        numberInput('y', device.y || 0, (v) => change(() => { device.y = v; })),
        el('label', {}, 'width', el('input', { type: 'number', value: width, disabled: true })),
        el('label', {}, 'height', el('input', { type: 'number', value: height, disabled: true }))),
      el('div', { class: 'fields' },
        info?.ports?.length ? [port('input', 'input port'), port('output', 'output port')] : null,
        (info?.options || []).flatMap((option) => optionField(device, option))),
      info?.controls?.length ? el('p', { class: 'hint' }, `Controls: ${info.controls.map((c) => c.name).join(', ')}`) : null,
      el('div', { class: 'actions' }, el('button', { class: 'danger', onclick: () => removeSelection() }, 'Remove device')),
    );
    return;
  }
  const { surface } = state.layout;
  const transport = state.layout.transport || {};
  const signature = transport.signature || [4, 4];
  fill(panel,
    el('h3', {}, 'Surface'),
    el('p', { class: 'doc' }, 'The grid widgets are placed on. Devices show parts of it.'),
    el('div', { class: 'quad' },
      numberInput('width', surface.width, (v) => v > 0 && change(() => { surface.width = v; }), { min: 1 }),
      numberInput('height', surface.height, (v) => v > 0 && change(() => { surface.height = v; }), { min: 1 }),
      numberInput('bpm', transport.bpm ?? 120, (v) => v > 0 && change((l) => { l.transport = { ...transport, bpm: v }; }), { min: 1 }),
      el('label', {}, 'time sig.', el('input', {
        type: 'text', value: signature.join('/'), title: 'Beats per bar / beat note value, e.g. 6/8',
        onchange: (e) => {
          const match = e.target.value.match(/^\s*(\d+)\s*\/\s*(\d+)\s*$/);
          if (match && +match[1] > 0 && +match[2] > 0) change((l) => { l.transport = { ...transport, signature: [+match[1], +match[2]] }; });
          else render();
        },
      }))),
    el('p', { class: 'hint' }, 'Select a widget to edit it. In Try mode, click pads to press them; hold for a Held event.'),
    el('h4', {}, 'Transport controls'),
    transportControls(),
  );
}

function renderCode() {
  const used = new Set();
  const lines = allWidgets().filter(({ widget }) => EVENTS[widget.type]).map(({ widget }) => {
    const [event, fields] = EVENTS[widget.type];
    used.add(event);
    return `ui[${JSON.stringify(widget.name)}].on(${event}, lambda e: print(${JSON.stringify(widget.name)}, ${fields}))`;
  });
  const file = state.file ? state.file.split(/[\\/]/).pop() : 'layout.json';
  $('code').textContent = [
    'from pyxelwidgets import parser',
    used.size ? `from pyxelwidgets.events import ${[...used].sort().join(', ')}` : null,
    '',
    `ui = parser.load(${JSON.stringify(file)})`,
    ...(lines.length ? ['', ...lines] : []),
    '',
    ...(allWidgets().some(({ widget }) => RHYTHMIC.has(widget.type))
      ? ['app = ui.app()  # Sequencers and Trackers follow app.transport', 'app.transport.play()', 'app.run()']
      : ['ui.app().run()']),
  ].filter((line) => line !== null).join('\n');
}

function renderToolbar() {
  $('mode-edit').classList.toggle('active', state.mode === 'edit');
  $('mode-try').classList.toggle('active', state.mode === 'try');
  document.body.classList.toggle('try', state.mode === 'try');
  $('undo').disabled = !state.history.length;
  $('redo').disabled = !state.future.length;
  $('save').disabled = !state.file;
  $('save').title = state.file ? `Save to ${state.file} (Ctrl+S)` : 'Started without a file: use Download';
  const play = $('play');
  play.textContent = state.playing ? '■ Stop' : '▶ Play';
  play.classList.toggle('on', state.playing);
  if (!state.playing) $('position').textContent = '';
  const hardware = $('hardware');
  const connected = state.hardware.devices.filter((d) => d.connected).length;
  hardware.classList.toggle('on', state.hardware.enabled);
  hardware.textContent = state.hardware.enabled ? `Hardware ${connected}/${state.hardware.devices.length}` : 'Hardware';
  $('palette-hint').textContent = targetGroup() ? `Click to add to ${widgetAt(targetGroup()).name}.` : 'Click to add to the surface.';
}

function renderDirty() {
  const dirty = JSON.stringify(state.layout) !== state.saved;
  $('file').classList.toggle('dirty', dirty);
  $('file').textContent = state.file ? state.file.split(/[\\/]/).pop() : 'Unsaved layout (use Download)';
  $('file').title = state.file || '';
  document.title = `${dirty ? '• ' : ''}PyxelWidgets Designer`;
}

// ---------------------------------------------------------------- editing actions

function targetGroup() {
  // Path of the group new widgets go into, or null for the surface
  const selection = state.selection;
  if (selection?.kind !== 'widget') return null;
  const widget = widgetAt(selection.path);
  if (widget.type === 'Pages') {
    // Into the shown page when it's a group
    const page = widget.widgets?.[currentPage(widget)];
    return page && isGroup(page) ? [...selection.path, currentPage(widget)] : selection.path;
  }
  if (isGroup(widget)) return selection.path;
  return selection.path.length > 1 ? selection.path.slice(0, -1) : null;
}

function addWidget(type) {
  const group = targetGroup();
  const [maxWidth, maxHeight] = group ? [widgetAt(group).width, widgetAt(group).height] : [state.layout.surface.width, state.layout.surface.height];
  const [width, height] = DEFAULT_SIZE[type] || [maxWidth, maxHeight];
  const widget = { type, name: uniqueName(type), x: 0, y: 0, width: Math.min(width, maxWidth), height: Math.min(height, maxHeight), options: {} };
  if (state.catalog.widgets[type].container) widget.widgets = [];
  change((layout) => {
    const list = group ? widgetAt(group).widgets : layout.widgets;
    list.push(widget);
    state.selection = { kind: 'widget', path: [...(group || []), list.length - 1] };
  });
}

function addDevice() {
  const type = $('device-type').value;
  change((layout) => {
    layout.devices.push({ type, x: 0, y: 0, options: {} });
    state.selection = { kind: 'device', index: layout.devices.length - 1 };
  });
}

function removeSelection() {
  const selection = state.selection;
  if (!selection) return;
  change((layout) => {
    let bindings = layout.bindings || [];
    if (selection.kind === 'widget') {
      childrenOf(selection.path).splice(selection.path[selection.path.length - 1], 1);
      const names = new Set(allWidgets().map(({ widget }) => widget.name));
      bindings = bindings.filter((binding) => binding.widget === undefined || names.has(binding.widget));
    } else {
      layout.devices.splice(selection.index, 1);
      bindings = bindings.filter((binding) => binding.device !== selection.index)
        .map((binding) => (binding.device > selection.index ? { ...binding, device: binding.device - 1 } : binding));
    }
    if (bindings.length) layout.bindings = bindings;
    else delete layout.bindings;
    state.selection = null;
  });
}

function reorder(path, direction) {
  const list = childrenOf(path);
  const index = path[path.length - 1];
  const target = index + direction;
  if (target < 0 || target >= list.length) return;
  change(() => {
    [list[index], list[target]] = [list[target], list[index]];
    state.selection = { kind: 'widget', path: [...path.slice(0, -1), target] };
  });
}

function duplicate(path) {
  const copy = JSON.parse(JSON.stringify(widgetAt(path)));
  const taken = new Set();
  const rename = (widget) => {
    widget.name = uniqueName(widget.type, taken);
    taken.add(widget.name);
    (widget.widgets || []).forEach(rename);
  };
  change(() => {
    rename(copy);
    const list = childrenOf(path);
    list.splice(path[path.length - 1] + 1, 0, copy);
    state.selection = { kind: 'widget', path: [...path.slice(0, -1), path[path.length - 1] + 1] };
  });
}

function nudge(dx, dy, resize) {
  const selection = state.selection;
  if (selection?.kind !== 'widget') return;
  const widget = widgetAt(selection.path);
  const [parentWidth, parentHeight] = containerSize(selection.path);
  change(() => {
    if (resize) {
      widget.width = Math.max(1, Math.min(parentWidth - (widget.x || 0), widget.width + dx));
      widget.height = Math.max(1, Math.min(parentHeight - (widget.y || 0), widget.height + dy));
    } else {
      widget.x = Math.max(0, Math.min(parentWidth - widget.width, (widget.x || 0) + dx));
      widget.y = Math.max(0, Math.min(parentHeight - widget.height, (widget.y || 0) + dy));
    }
  });
}

async function save() {
  if (!state.file) return;
  const reply = await api('POST', '/api/save', state.layout);
  if (reply.ok) {
    state.saved = JSON.stringify(state.layout);
    renderDirty();
    setStatus(`Saved ${state.file}`, 'ok');
  } else {
    setStatus(reply.error, 'error');
  }
}

function download() {
  const blob = new Blob([JSON.stringify(state.layout, null, 2) + '\n'], { type: 'application/json' });
  const link = el('a', { href: URL.createObjectURL(blob), download: state.file ? state.file.split(/[\\/]/).pop() : 'layout.json' });
  link.click();
  URL.revokeObjectURL(link.href);
}

async function open(file) {
  try {
    const layout = JSON.parse(await file.text());
    const reply = await api('PUT', '/api/layout', layout);
    if (!reply.ok) throw new Error(reply.error);
    // Older versions come back upgraded
    replaceLayout(reply.layout);
    setStatus(`Opened ${file.name}`, 'ok');
  } catch (error) {
    setStatus(`Can't open ${file.name}: ${error.message}`, 'error');
    scheduleSync();
  }
}

function setMode(mode) {
  state.mode = mode;
  for (const pointer of held.keys()) padUp({ pointerId: pointer });
  renderToolbar();
}

// ---------------------------------------------------------------- startup

function bindToolbar() {
  $('mode-edit').onclick = () => setMode('edit');
  $('mode-try').onclick = () => setMode('try');
  $('hardware').onclick = async () => {
    const reply = await api('POST', '/api/hardware', { enabled: !state.hardware.enabled });
    state.hardware = { enabled: !state.hardware.enabled, devices: reply.devices || [] };
    renderToolbar();
    renderDevices();
    const failed = state.hardware.devices.find((d) => !d.connected);
    if (state.hardware.enabled && failed) setStatus(`Some devices aren't connected: ${failed.error}`, 'error');
    else if (state.hardware.enabled) setStatus('Hardware connected: it mirrors the preview', 'ok');
  };
  $('play').onclick = async () => {
    state.playing = !state.playing;
    renderToolbar();
    await api('POST', '/api/play', { playing: state.playing });
  };
  $('undo').onclick = undo;
  $('redo').onclick = redo;
  $('save').onclick = save;
  $('download').onclick = download;
  $('open').onclick = () => $('open-file').click();
  $('open-file').onchange = (e) => { if (e.target.files[0]) open(e.target.files[0]); e.target.value = ''; };
  $('add-device').onclick = addDevice;
  $('clear-events').onclick = () => $('events').replaceChildren();
  $('copy-code').onclick = async () => {
    await navigator.clipboard?.writeText($('code').textContent);
    setStatus('Copied the Python snippet', 'ok');
  };
  $('stage').addEventListener('pointerdown', (event) => {
    if (state.mode === 'edit' && (event.target.id === 'stage' || event.target.id === 'board')) select(null);
  });
  window.addEventListener('resize', () => { renderBoard(); renderOverlay(); });
  window.addEventListener('beforeunload', (event) => {
    if (state.file && JSON.stringify(state.layout) !== state.saved) event.preventDefault();
  });
  window.addEventListener('keydown', (event) => {
    if (event.target.closest('input, select, textarea')) return;
    const mod = event.ctrlKey || event.metaKey;
    const key = event.key.toLowerCase();
    if (mod && key === 'z') { event.preventDefault(); return event.shiftKey ? redo() : undo(); }
    if (mod && key === 'y') { event.preventDefault(); return redo(); }
    if (mod && key === 's') { event.preventDefault(); return save(); }
    if (mod && key === 'd' && state.selection?.kind === 'widget') { event.preventDefault(); return duplicate(state.selection.path); }
    if (mod) return;
    if (key === 'e') return setMode('edit');
    if (key === 't') return setMode('try');
    if (key === 'escape') return select(null);
    // A focused button handles Space itself
    if (key === ' ' && !event.target.closest('button')) { event.preventDefault(); return $('play').click(); }
    if (state.mode !== 'edit') return;
    if (key === 'delete' || key === 'backspace') { event.preventDefault(); return removeSelection(); }
    const arrows = { arrowleft: [-1, 0], arrowright: [1, 0], arrowup: [0, 1], arrowdown: [0, -1] };
    if (arrows[key]) { event.preventDefault(); nudge(...arrows[key], event.shiftKey); }
  });
}

function buildCatalog() {
  $('palette').replaceChildren(...Object.entries(state.catalog.widgets).map(([type, info]) =>
    el('button', { title: (info.doc || type).replace(/``/g, ''), onclick: () => addWidget(type), dataset: { type } },
      el('span', { class: 'glyph' }, type === 'ButtonGroup' ? 'BG' : type.slice(0, 2)), el('span', { class: 'label' }, type))));
  const groups = {};
  for (const device of state.catalog.devices) (groups[device.vendor || 'Other'] ||= []).push(device);
  $('device-type').replaceChildren(...Object.entries(groups).map(([vendor, devices]) =>
    el('optgroup', { label: vendor }, devices.map((device) => el('option', { value: device.type }, device.model)))));
}

async function start() {
  const [catalog, current] = await Promise.all([api('GET', '/api/catalog'), api('GET', '/api/layout')]);
  state.catalog = catalog;
  state.layout = current.layout;
  state.layout.devices = state.layout.devices || [];
  state.layout.widgets = state.layout.widgets || [];
  state.file = current.file;
  state.saved = JSON.stringify(state.layout);
  buildCatalog();
  bindToolbar();
  render();
  poll();
}

start();
