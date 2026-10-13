// PyxelWidgets Designer: edits a layout (see pyxelwidgets.parser) and shows a
// live preview rendered by the Python widgets through the designer server.

const DEFAULT_SIZE = {
  Button: [1, 1], ButtonGroup: [4, 1], ClipLauncher: [8, 4], DrumPads: [4, 4], Fader: [1, 8], Keyboard: [8, 4], Knob: [3, 3],
  Meter: [1, 8], Sequencer: [8, 4], Sprite: [2, 2], Text: [8, 5], Tracker: [4, 8], XY: [4, 4],
};
// Colors offered for painting Sprite frames (any color can be picked too)
const SWATCHES = ['White', 'Gray', 'Red', 'OrangeRed', 'Orange', 'Yellow', 'Lime', 'Green', 'Cyan', 'DodgerBlue', 'Blue', 'Purple', 'Magenta', 'HotPink'];

const state = {
  catalog: null,
  // What outputs scanned in the DAW, by output name: {tracks, plugins: {track: [...]}, parameters: {'track/plugin': [...]}}
  scans: {},
  layout: null,
  file: null,
  saved: '',
  // null (surface) | {kind: 'widget', path: [i, j, ...], paths: [path, ...]} | {kind: 'device', index} | {kind: 'output', index}
  // `paths` are all selected widgets, `path` the last one picked (the one panels edit)
  selection: null,
  mode: 'edit',
  history: [],
  future: [],
  lastEvent: 0,
  playing: false,
  hardware: { devices: [], outputs: [] },
  dragType: null, // a palette widget type being dragged onto the grid
  zoom: 1, // pad size relative to the size that fits the window
  pan: { x: 0, y: 0 }, // the board moved from the middle of the stage, in pixels
  layerDrag: null, // paths of the layers being dragged in the Layers panel
  error: null,
  frameSize: [0, 0],
  spriteFrame: 0, // the Sprite frame being painted
  paint: { color: '#ffffff', erase: false },
  eventLog: [], // events from the preview, newest last
  eventsPaused: false,
  // The messages and links window: shown, every widget's or the selected ones', picked rules, Shift+click
  // start, search, whether keys go to it
  rules: { open: false, all: false, picked: [], anchor: null, query: '', focused: false },
  // Several picked rules edited as one: {kind, rep, others} (see spreadChange)
  broadcast: null,
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

// ---------------------------------------------------------------- view preferences (this browser only)

// Folded sections, panel sizes, the drawer; per layout file: collapsed, hidden and locked layers
const prefs = (() => {
  try {
    return JSON.parse(localStorage.getItem('pyxelwidgets.designer') || '{}');
  } catch {
    return {};
  }
})();

function savePrefs() {
  try {
    localStorage.setItem('pyxelwidgets.designer', JSON.stringify(prefs));
  } catch {
    // Private windows: preferences last for this page only
  }
}

function viewKey() {
  return state.file || '(unsaved)';
}

// Widget names in a per-file view set: 'collapsed', 'hidden' (in the designer only) or 'locked'
function viewSet(kind) {
  return new Set(prefs.views?.[viewKey()]?.[kind] || []);
}

function setViewSet(kind, names) {
  prefs.views ||= {};
  prefs.views[viewKey()] ||= {};
  prefs.views[viewKey()][kind] = [...names];
  savePrefs();
  if (kind === 'hidden') sendHidden();
}

function toggleView(kind, name) {
  const names = viewSet(kind);
  if (names.has(name)) names.delete(name);
  else names.add(name);
  setViewSet(kind, names);
  render();
}

// Keep view sets following renamed widgets
function renameInViews(from, to) {
  for (const kind of ['collapsed', 'hidden', 'locked']) {
    const names = viewSet(kind);
    if (names.delete(from)) {
      names.add(to);
      setViewSet(kind, names);
    }
  }
}

// Widgets hidden in the designer only are hidden in the preview too
function sendHidden() {
  api('POST', '/api/view', { hidden: [...viewSet('hidden')] });
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
  // On-screen and browser grids are as big as their options say
  if (device.type === 'virtual.Virtual' || device.type === 'web.WebGrid') return [options.columns ?? 8, options.rows ?? 8];
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
    state.selection = widgetSelection([[...path, pages.widgets.length - 1]]);
  });
}

function samePath(a, b) {
  return a && b && a.length === b.length && a.every((value, i) => value === b[i]);
}

// ---------------------------------------------------------------- selection

function widgetSelection(paths, path = paths[paths.length - 1]) {
  return paths.length ? { kind: 'widget', path, paths } : null;
}

function selectedPaths() {
  return state.selection?.kind === 'widget' ? state.selection.paths : [];
}

function isSelected(path) {
  return selectedPaths().some((selected) => samePath(selected, path));
}

function isInside(path, ancestor) {
  return ancestor.length < path.length && samePath(ancestor, path.slice(0, ancestor.length));
}

// Selected widgets without those inside another selected one: what moves, copies and deletes
function topSelected() {
  const paths = selectedPaths();
  return paths.filter((path) => !paths.some((other) => isInside(path, other)));
}

// Shift/Ctrl/Cmd+click adds a widget to the selection or takes it out
function toggleSelected(path) {
  const paths = selectedPaths();
  state.selection = isSelected(path)
    ? widgetSelection(paths.filter((selected) => !samePath(selected, path)))
    : widgetSelection([...paths, path]);
  render();
}

// Paths of widget objects, after a change moved them
function pathsOf(widgets) {
  const found = allWidgets();
  return widgets.map((widget) => found.find((item) => item.widget === widget)?.path).filter(Boolean);
}

// ---------------------------------------------------------------- outputs and mappings

const INTEGER_SOURCES = new Set(['x', 'y', 'cell', 'note', 'step', 'row', 'page', 'delta']);

function outputsOf(layout = state.layout) {
  return layout.outputs || [];
}

function outputInfo(output) {
  return state.catalog.outputs.find((info) => info.type === output?.type);
}

function setMappings(layout, mappings) {
  if (mappings.length) layout.mappings = mappings;
  else delete layout.mappings;
}

function uniqueOutputName(base) {
  const taken = new Set(outputsOf().map((output) => output.name));
  if (!taken.has(base)) return base;
  for (let i = 2; ; i++) if (!taken.has(`${base}${i}`)) return `${base}${i}`;
}

function addOutput() {
  const type = $('output-type').value;
  const info = state.catalog.outputs.find((output) => output.type === type);
  const base = { 'mackie.MackieControl': 'mackie', 'mackie.HUI': 'hui', 'osc.REAPER': 'reaper', 'osc.OSC': 'osc', 'desktop.Desktop': 'desktop' }[type] || 'midi';
  change((layout) => {
    const name = uniqueOutputName(base);
    // MIDI outputs start as a virtual port other software can pick
    const output = { name, type, ...(info?.midi ? { virtual: `PyxelWidgets ${name}` } : {}), options: {} };
    layout.outputs = [...outputsOf(layout), output];
    state.selection = { kind: 'output', index: layout.outputs.length - 1 };
  });
}

function removeOutput(index) {
  change((layout) => {
    const [removed] = layout.outputs.splice(index, 1);
    if (!layout.outputs.length) delete layout.outputs;
    setMappings(layout, (layout.mappings || []).filter((mapping) => mapping.output !== removed.name));
    state.selection = null;
  });
}

function renderOutputs() {
  const list = $('outputs');
  list.replaceChildren(...outputsOf().map((output, index) => {
    const selected = state.selection?.kind === 'output' && state.selection.index === index;
    const count = (state.layout.mappings || []).filter((mapping) => mapping.output === output.name).length;
    return el('li', { class: selected ? 'selected' : '', onclick: () => select({ kind: 'output', index }) },
      el('span', { class: 'swatch-output' }),
      el('span', { class: 'label' },
        el('span', { class: 'name' }, output.name),
        el('span', { class: 'type' }, `${outputInfo(output)?.model || output.type}${count ? ` · ${count} message${count > 1 ? 's' : ''}` : ''}`)),
      hardwareDot(index, 'outputs'),
      connectButton('outputs', index));
  }));
  if (!outputsOf().length) list.append(el('li', { class: 'hint' }, 'MIDI ports, OSC, Mackie Control or HUI that widgets send to.'));
}

function outputProperties(panel, index) {
  const output = outputsOf()[index];
  const info = outputInfo(output);
  const port = (key, label, placeholder) => [
    el('label', { for: `output-${key}` }, label),
    el('div', { class: 'control' }, el('input', {
      type: 'text', id: `output-${key}`, value: output[key] || '', placeholder,
      onchange: (e) => change(() => { if (e.target.value.trim()) output[key] = e.target.value.trim(); else delete output[key]; }),
    })),
  ];
  const used = (state.layout.mappings || []).filter((mapping) => mapping.output === output.name);
  fill(panel,
    el('h3', {}, info?.model || output.type),
    el('p', { class: 'doc' }, info?.midi
      ? 'Other software (a DAW, a synth) picks the virtual port, or set existing input/output ports instead.'
      : output.type.startsWith('osc.') ? 'Sends OSC to host:send port and listens on the receive port.' : (info?.doc || '').replace(/``/g, '')),
    info && info.auto_connect === false ? el('p', { class: 'hint' },
      'Not connected by itself in the designer: press Connect in Outputs when its actions should happen for real. The event log shows them either way.') : null,
    el('div', { class: 'fields' },
      el('label', { for: 'output-name' }, 'name'),
      el('div', { class: 'control' }, el('input', {
        type: 'text', id: 'output-name', value: output.name,
        onchange: (e) => {
          const name = e.target.value.trim();
          if (!name || outputsOf().some((other) => other !== output && other.name === name)) {
            setStatus(`Output name "${name}" is empty or already used`, 'error');
            return render();
          }
          change((layout) => {
            for (const mapping of layout.mappings || []) if (mapping.output === output.name) mapping.output = name;
            output.name = name;
          });
        },
      })),
      info?.midi ? [port('virtual', 'virtual port', 'none'), port('input', 'input port', 'none'), port('output', 'output port', 'none')] : null,
      (info?.options || []).filter((option) => !ADVANCED.has(option.name)).flatMap((option) => optionField(output, option))),
    optionFields(output, (info?.options || []).filter((option) => ADVANCED.has(option.name))),
    el('p', { class: 'hint note' }, used.length
      ? `${used.length} message${used.length > 1 ? 's' : ''} from ${[...new Set(used.map((m) => m.widget))].join(', ')}.`
      : 'Select a widget and add a message to send its events here.'),
    el('div', { class: 'actions' }, el('button', { class: 'danger', onclick: () => removeOutput(index) }, 'Remove output')),
  );
}

// The event a new message is sent on: the widget's main one
function defaultEvent(widget) {
  const events = state.catalog.widgets[widget.type]?.events || [];
  return ['Changed', 'Toggled', 'NoteOn', 'StepPlayed', 'RowPlayed', 'ClipStarted', 'PageChanged', 'Pressed'].find((name) => events.includes(name)) || events[0];
}

// A useful first message for an event on an output
function defaultMessage(widget, on, info) {
  const accepts = info?.messages || [];
  const source = (name, extra = {}) => ({ source: name, ...extra });
  const xy = widget.type === 'XY';
  if (accepts.includes('Hotkey')) {
    if (on === 'Changed' && xy) return { type: 'MouseMove', x: source('value_x'), y: source('value_y'), relative: false };
    if (on === 'Changed' && widget.type === 'Knob') return { type: 'Scroll', dx: 0, dy: source('delta') };
    if (on === 'Changed' && widget.type === 'Button') return { type: 'Key', keys: 'shift', state: source('value') };
    if (on === 'Changed') return { type: 'Scroll', dx: 0, dy: source('delta') };
    if (on === 'Toggled') return { type: 'Hotkey', keys: 'f{x+1}' };
    return { type: 'Hotkey', keys: 'ctrl+c' };
  }
  if (accepts.includes('Command')) {
    if (on === 'Changed') return { type: 'Command', name: 'Fader 1', value: source(xy ? 'value_x' : 'value') };
    if (on === 'Toggled') return { type: 'Command', name: 'Mute {x+1}', value: source('state') };
    return { type: 'Command', name: 'Play', value: on === 'Released' ? 0 : 1 };
  }
  if (accepts.includes('OscMessage')) {
    if (on === 'Changed') return { type: 'OscMessage', address: '/track/1/volume', args: [source(xy ? 'value_x' : 'value')] };
    if (on === 'Toggled') return { type: 'OscMessage', address: '/track/{x+1}/mute', args: [source('state')] };
    return { type: 'OscMessage', address: '/play', args: [on === 'Released' ? 0 : 1] };
  }
  const cells = widget.width * widget.height > 1 && !['Fader', 'Knob', 'XY', 'Button'].includes(widget.type);
  const note = cells ? source('cell', { offset: 36 }) : 60;
  switch (on) {
    case 'Pressed': return { type: 'NoteOn', note, velocity: source('velocity'), channel: 1 };
    case 'Released': return { type: 'NoteOff', note, velocity: 0, channel: 1 };
    case 'Changed': return { type: 'ControlChange', control: 1, value: source(xy ? 'value_x' : 'value'), channel: 1 };
    case 'Toggled': return { type: 'NoteOn', note: source('cell', { offset: 36 }), velocity: source('state'), channel: 1 };
    case 'NoteOn': return { type: 'NoteOn', note: source('note'), velocity: source('velocity'), channel: 1 };
    case 'NoteOff': return { type: 'NoteOff', note: source('note'), velocity: 0, channel: 1 };
    case 'Pressure': return { type: 'PolyPressure', note, pressure: source('pressure'), channel: 1 };
    case 'StepPlayed': return { type: 'NoteOn', note: 36, velocity: source('active'), channel: 1 };
    case 'StepEnded': return { type: 'NoteOff', note: 36, velocity: 0, channel: 1 };
    default: return { type: 'NoteOn', note: 60, velocity: 127, channel: 1 };
  }
}

// Names of the event values a layout message uses, placeholders included
function messageSources(message) {
  const found = [];
  const visit = (value) => {
    if (value && typeof value === 'object' && !Array.isArray(value)) found.push(value.source);
    else if (Array.isArray(value)) value.forEach(visit);
    else if (typeof value === 'string') for (const match of value.matchAll(/\{(\w+)/g)) found.push(match[1]);
  };
  for (const [key, value] of Object.entries(message || {})) if (key !== 'type') visit(value);
  return found;
}

// Sources a field can take: the event's values, or (receiving only) anything a message carries
function sourceNames(on) {
  if (on) return state.catalog.events[on]?.sources || [];
  return [...new Set([...Object.values(state.catalog.events).flatMap((event) => event.sources), 'state', 'text'])];
}

// A field's editor: a constant or one of the event's values (with its range or offset)
function valueEditor(id, value, field, sources, commit) {
  const isSource = value && typeof value === 'object';
  const textual = field.kind === 'text' || field.kind === 'arg';
  const mode = el('select', {
    id, title: 'A constant, or a value from the event',
    onchange: (e) => commit(e.target.value === '' ? (field.range ? field.range[0] : (textual ? '' : 0)) : { source: e.target.value }),
  },
  el('option', { value: '', selected: !isSource }, 'constant'),
  sources.map((name) => el('option', { value: name, selected: isSource && value.source === name }, name)),
  // A source the event doesn't have (e.g. after changing the event)
  isSource && !sources.includes(value.source) ? el('option', { value: value.source, selected: true }, `${value.source} (not available)`) : null);
  const number = (key, placeholder, attrs = {}) => el('input', {
    type: 'number', class: 'small', value: value?.[key] ?? '', placeholder, title: key, ...attrs,
    onchange: (e) => {
      const next = { ...value };
      if (e.target.value === '') delete next[key];
      else next[key] = Number(e.target.value);
      commit(next);
    },
  });
  let detail;
  if (!isSource) {
    detail = el('input', {
      type: textual ? 'text' : 'number', class: textual ? '' : 'small', value: value ?? '',
      ...(field.range ? { min: field.range[0], max: field.range[1], step: 1 } : { step: 'any' }),
      onchange: (e) => {
        const text = e.target.value;
        // OSC arguments: numbers when they look like one
        commit(field.range ? parseInt(text || field.range[0], 10) : (textual && !/^-?\d*\.?\d+$/.test(text) ? text : Number(text)));
      },
    });
  } else if (INTEGER_SOURCES.has(value.source)) {
    detail = number('offset', '+0', { step: 1 });
  } else if (value.source === 'text') {
    detail = null;
  } else {
    detail = el('span', { class: 'range', title: 'The range 0.0-1.0 covers' },
      number('min', field.range ? String(field.range[0]) : '0'), '–', number('max', field.range ? String(field.range[1]) : '1'));
  }
  return el('div', { class: 'control value' }, mode, detail);
}

const COMMAND_KINDS = [
  ['button', 'Buttons'], ['fader', 'Faders'], ['relative', 'V-Pots and jog wheel (steps)'],
  ['display', 'Displays (received)'], ['meter', 'Meters (received)'],
];

// An output's commands for a picker: by kind, then numbered families as one per pad ('Mute {x+1}')
function commandChoices(info) {
  const commands = info?.commands || [];
  if (!commands.length) return [];
  const groups = COMMAND_KINDS.map(([kind, label]) => ({
    label, items: commands.filter((command) => command.kind === kind).map((command) => ({ value: command.name, kind })),
  }));
  const families = new Map();
  for (const command of commands) {
    const match = command.name.match(/^(.*\D) 1$/);
    if (match && commands.some((other) => other.name === `${match[1]} 2`)) families.set(`${match[1]} {x+1}`, command.kind);
  }
  groups.push({ label: 'One per pad column: {x+1} (use {y+1} or {cell+1} by typing)', items: [...families].map(([value, kind]) => ({ value, kind })) });
  return groups.filter((group) => group.items.length);
}

function addressChoices(info) {
  const addresses = info?.addresses || [];
  return addresses.length ? [{ label: info.model, items: addresses.map((value) => ({ value })) }] : [];
}

// Set a picked command (or address) and give the message a value that suits it
function pickName(widget, mapping, field, item) {
  change(() => {
    mapping.message[field] = item.value;
    if (mapping.message.type !== 'Command' || !item.kind) return;
    const xy = widget.type === 'XY';
    const wanted = { fader: xy ? 'value_x' : 'value', meter: 'value', relative: 'delta', display: 'text' }[item.kind];
    if (item.kind === 'display' || item.kind === 'meter') {
      // Only the DAW sends these
      delete mapping.on;
      mapping.feedback = true;
    }
    if (wanted) mapping.message.value = { source: wanted };
    else if (typeof mapping.message.value === 'object') mapping.message.value = mapping.on === 'Released' ? 0 : 1;
    // Sent on an event that has every value it uses ({x+1} needs x), else only received
    const needed = messageSources(mapping.message);
    if (mapping.on && !needed.every((name) => sourceNames(mapping.on).includes(name))) {
      const event = (state.catalog.widgets[widget.type]?.events || []).find((name) => needed.every((source) => sourceNames(name).includes(source)));
      if (event) mapping.on = event;
      else {
        delete mapping.on;
        mapping.feedback = true;
      }
    }
  });
}

// Browser key names → the keyboard output's ('KeyA' → 'a', 'ArrowUp' → 'up')
const KEY_CODES = {
  ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right', Enter: 'enter', NumpadEnter: 'enter',
  Space: 'space', Tab: 'tab', Escape: 'esc', Backspace: 'backspace', Delete: 'delete', CapsLock: 'caps_lock',
  Home: 'home', End: 'end', PageUp: 'page_up', PageDown: 'page_down',
  MediaPlayPause: 'media_play_pause', MediaTrackNext: 'media_next', MediaTrackPrevious: 'media_previous',
  AudioVolumeUp: 'media_volume_up', AudioVolumeDown: 'media_volume_down', AudioVolumeMute: 'media_volume_mute',
};
const MODIFIERS = { Control: 'ctrl', Shift: 'shift', Alt: 'alt', Meta: 'cmd' };

function keyName(event) {
  if (KEY_CODES[event.code]) return KEY_CODES[event.code];
  if (/^F\d+$/.test(event.code)) return event.code.toLowerCase();
  if (/^Key[A-Z]$/.test(event.code)) return event.code.slice(3).toLowerCase();
  if (/^Digit\d$/.test(event.code)) return event.code.slice(5);
  return event.key.length === 1 ? (event.key === '+' ? 'plus' : event.key.toLowerCase()) : null;
}

// Wait for a key combination; resolves with 'ctrl+shift+s' (or modifiers alone, released), or null on Escape
function recordKeys() {
  return new Promise((resolve) => {
    const held = [];
    const finish = (keys) => {
      window.removeEventListener('keydown', down, true);
      window.removeEventListener('keyup', up, true);
      resolve(keys);
    };
    const down = (event) => {
      event.preventDefault();
      event.stopPropagation();
      const modifier = MODIFIERS[event.key];
      if (modifier) {
        if (!held.includes(modifier)) held.push(modifier);
        return;
      }
      if (event.key === 'Escape' && !held.length) return finish(null);
      const key = keyName(event);
      if (key) finish([...held, key].join('+'));
    };
    const up = (event) => {
      event.preventDefault();
      event.stopPropagation();
      // Only modifiers pressed (e.g. Shift to hold)
      if (MODIFIERS[event.key] && held.length) finish(held.join('+'));
    };
    window.addEventListener('keydown', down, true);
    window.addEventListener('keyup', up, true);
  });
}

// A keys field: typed ('ctrl+shift+s', 'f{x+1}') or recorded by pressing them
function keysField(id, value, info, commit) {
  const input = el('input', {
    type: 'text', id, value: value ?? '', list: `${id}-names`, placeholder: 'ctrl+shift+s',
    title: 'Keys joined with +: ctrl, shift, alt, cmd, enter, f1-f20, up, media_play_pause... or single characters',
    onchange: (e) => commit(e.target.value.trim()),
  });
  const record = el('button', {
    id: `${id}-record`, title: 'Press the keys to use (Escape cancels)',
    onclick: async () => {
      record.textContent = 'Press keys…';
      record.classList.add('active');
      const keys = await recordKeys();
      record.classList.remove('active');
      record.textContent = 'Record';
      if (keys) commit(keys);
    },
  }, 'Record');
  return [
    el('label', { for: id }, 'keys'),
    el('div', { class: 'control' }, input, record,
      el('datalist', { id: `${id}-names` }, (info?.keys || []).map((name) => el('option', { value: name })))),
  ];
}

const SCANS = { track: 'tracks', plugin: 'plugins', parameter: 'parameters' };
const SCAN_HINTS = {
  track: 'A track of the DAW: Scan reads them from the Mackie Control display (7 characters at most)',
  plugin: 'A plug-in on the track: Scan opens the DAW\'s plug-in mode for the track',
  parameter: 'A parameter of the plug-in: Scan opens it and pages through its parameters',
};

// What an output scanned for PluginParameter's track, plugin or parameter (null: not scanned)
function scannedNames(output, name, message) {
  const scans = state.scans[output?.name];
  if (!scans) return null;
  if (name === 'track') return scans.tracks?.length ? scans.tracks : null;
  if (name === 'plugin') return scans.plugins?.[message.track] || null;
  return scans.parameters?.[`${message.track}/${message.plugin}`] || null;
}

async function scanDaw(output, what, message, button) {
  const index = outputsOf().indexOf(output);
  button.textContent = 'Scanning…';
  button.disabled = true;
  setStatus(what === 'tracks' ? 'Scanning the DAW\'s tracks…' : `Scanning ${what === 'plugins' ? `the plug-ins on ${message.track}` : `the parameters of ${message.plugin}`}…`, '');
  const result = await api('POST', '/api/scan', { output: index, what, track: message.track, plugin: message.plugin });
  if (!result.ok) {
    setStatus(result.error, 'error');
  } else {
    state.scans[output.name] = result.scanned;
    setStatus(result.names.length ? `Found ${result.names.length} ${what}` : `No ${what} found`, result.names.length ? 'ok' : 'error');
  }
  render();
}

// PluginParameter's track, plugin and parameter: picked from a scan of the DAW, or typed
function scanField(id, name, mapping, output, commit) {
  const message = mapping.message;
  if (output && !(output.name in state.scans)) {
    // What earlier scans found (the output keeps them while connected)
    state.scans[output.name] = null;
    api('POST', '/api/scan', { output: outputsOf().indexOf(output), what: 'known' }).then((result) => {
      if (result.ok && result.scanned) {
        state.scans[output.name] = result.scanned;
        render();
      }
    });
  }
  const value = message[name] ?? '';
  const names = scannedNames(output, name, message);
  const known = names?.includes(value);
  const input = el('input', {
    type: 'text', id, value, hidden: !!(names && (known || !value)), placeholder: { track: 'Track name', plugin: 'Plug-in name', parameter: 'Parameter name' }[name],
    title: SCAN_HINTS[name], onchange: (e) => commit(e.target.value.trim()),
  });
  const picker = names ? el('select', {
    id: `${id}-pick`, title: SCAN_HINTS[name],
    onchange: (e) => {
      if (e.target.value === '\u0000') {
        input.hidden = false;
        return input.focus();
      }
      commit(e.target.value);
    },
  },
  value && !known ? null : el('option', { value: '', selected: !value, disabled: true }, `Pick a ${name}`),
  names.map((item) => el('option', { value: item, selected: item === value }, item)),
  el('option', { value: '\u0000', selected: !!(value && !known) }, 'Type a name…')) : null;
  const missing = name === 'plugin' ? !message.track : name === 'parameter' ? !(message.track && message.plugin) : false;
  const scan = el('button', {
    id: `${id}-scan`, disabled: missing,
    title: missing ? `Pick the ${name === 'plugin' ? 'track' : 'track and plug-in'} first` : `${SCAN_HINTS[name].split(': ')[1]} (connect the output first)`,
    onclick: () => scanDaw(output, SCANS[name], message, scan),
  }, 'Scan');
  return [
    el('label', { for: names ? `${id}-pick` : id }, name),
    el('div', { class: 'control scan' }, picker, input, scan),
  ];
}

function mappingCard(widget, mapping, index) {
  const events = state.catalog.widgets[widget.type]?.events || [];
  const output = outputsOf().find((candidate) => candidate.name === mapping.output);
  const info = outputInfo(output);
  const message = mapping.message || {};
  const schema = state.catalog.messages[message.type];
  const id = (name) => `mapping-${index}-${name}`;
  const edit = (mutate) => change(() => mutate(mapping));
  const sources = sourceNames(mapping.on);
  const setField = (name) => (value) => edit(() => {
    mapping.message[name] = value;
    // A track's volume follows a value, its pan steps or a value, mute/solo/record a state
    if (mapping.message.type === 'TrackParameter' && name === 'parameter') {
      const source = trackValueSource(value, info, sourceNames(mapping.on));
      if (source) mapping.message.value = { source };
    }
  });
  const fieldEditors = (schema?.fields || []).flatMap((field) => {
    if (field.kind === 'list') {
      // OSC arguments
      const args = message.args || [];
      return [
        el('label', {}, 'arguments'),
        el('div', { class: 'args' },
          args.map((arg, i) => el('div', { class: 'arg' },
            valueEditor(id(`arg${i}`), arg, { kind: 'arg' }, sources, (value) => edit(() => { mapping.message.args[i] = value; })),
            el('button', { class: 'link', title: 'Remove', onclick: () => edit(() => { mapping.message.args.splice(i, 1); }) }, '×'))),
          el('button', { class: 'link', onclick: () => edit(() => { mapping.message.args = [...args, { source: sources.includes('value') ? 'value' : sources[0] || 'value' }]; }) }, '+ argument')),
      ];
    }
    const value = field.name in message ? message[field.name] : field.default;
    if (field.kind === 'choice') {
      return [el('label', { for: id(field.name) }, field.name), el('div', { class: 'control' }, el('select', {
        id: id(field.name), onchange: (e) => setField(field.name)(e.target.value),
      }, field.choices.map((choice) => el('option', { value: choice, selected: choice === value }, choice))))];
    }
    if (field.kind === 'bool') {
      return [el('label', { for: id(field.name) }, field.name), el('div', { class: 'control' }, el('input', {
        type: 'checkbox', id: id(field.name), checked: !!value, onchange: (e) => setField(field.name)(e.target.checked),
      }))];
    }
    if (field.kind === 'keys') return keysField(id(field.name), value, info, setField(field.name));
    if (field.kind === 'scan') return scanField(id(field.name), field.name, mapping, output, setField(field.name));
    if (field.kind === 'text') {
      const groups = message.type === 'Command' ? commandChoices(info) : message.type === 'OscMessage' ? addressChoices(info) : [];
      const known = groups.some((group) => group.items.some((item) => item.value === value));
      const input = el('input', {
        type: 'text', id: id(field.name), value: value ?? '', hidden: !!(groups.length && known),
        title: 'Placeholders like {x+1} take a value from the event', onchange: (e) => setField(field.name)(e.target.value),
      });
      const picker = groups.length ? el('select', {
        id: id(`${field.name}-pick`), title: 'Pick one, or Custom to type a name with {x+1} placeholders',
        onchange: (e) => {
          if (e.target.value === '') {
            input.hidden = false;
            return input.focus();
          }
          const item = groups.flatMap((group) => group.items).find((candidate) => candidate.value === e.target.value);
          pickName(widget, mapping, field.name, item);
        },
      },
      groups.map((group) => el('optgroup', { label: group.label },
        group.items.map((item) => el('option', { value: item.value, selected: item.value === value }, item.value)))),
      el('option', { value: '', selected: !known }, 'Custom…')) : null;
      return [
        el('label', { for: id(groups.length ? `${field.name}-pick` : field.name) }, field.name),
        el('div', { class: 'control picker' }, picker, input),
      ];
    }
    return [el('label', { for: id(field.name) }, field.name), valueEditor(id(field.name), value, field, sources, setField(field.name))];
  });
  return el('div', { class: 'mapping' },
    el('div', { class: 'mapping-head' },
      el('select', {
        id: id('on'), title: 'The widget event that sends it; receive only: just feedback',
        onchange: (e) => edit(() => {
          if (e.target.value) {
            mapping.on = e.target.value;
            // A message using values the new event doesn't have becomes its default one
            const available = sourceNames(mapping.on);
            if (messageSources(mapping.message).some((name) => !available.includes(name))) {
              mapping.message = defaultMessage(widget, mapping.on, info);
            }
          } else {
            delete mapping.on;
            mapping.feedback = true;
          }
        }),
      },
      events.map((name) => el('option', { value: name, selected: name === mapping.on }, name)),
      el('option', { value: '', selected: !mapping.on }, 'receive only')),
      el('span', { class: 'arrow' }, '→'),
      el('select', {
        id: id('output'),
        onchange: (e) => edit(() => {
          mapping.output = e.target.value;
          const next = outputInfo(outputsOf().find((candidate) => candidate.name === mapping.output));
          // A message the new output can't send becomes its default one
          if (!next?.messages.includes(mapping.message?.type)) mapping.message = defaultMessage(widget, mapping.on, next);
        }),
      }, outputsOf().map((candidate) => el('option', { value: candidate.name, selected: candidate.name === mapping.output }, candidate.name))),
      el('button', {
        class: 'link remove', title: 'Remove this message',
        onclick: () => change((layout) => setMappings(layout, layout.mappings.filter((_, i) => i !== index))),
      }, '×')),
    el('div', { class: 'fields' },
      el('label', { for: id('type') }, 'message'),
      el('div', { class: 'control' }, el('select', {
        id: id('type'),
        onchange: (e) => edit(() => {
          const type = e.target.value;
          const fields = state.catalog.messages[type].fields;
          // Keep the fields both types have
          const next = { type };
          for (const field of fields) if (field.name in mapping.message && field.kind !== 'list') next[field.name] = mapping.message[field.name];
          if (type === 'OscMessage') Object.assign(next, { address: mapping.message.address || '/', args: mapping.message.args || [] });
          // A knob or fader turns a plug-in parameter by its steps (Mackie Control), or sets it (REAPER)
          const value = info?.parameter_value || 'delta';
          if (type === 'PluginParameter' && sourceNames(mapping.on).includes(value)) next.value = { source: value };
          if (type === 'TrackParameter') {
            const source = trackValueSource(next.parameter || 'Volume', info, sourceNames(mapping.on));
            if (source) next.value = { source };
          }
          mapping.message = next;
        }),
      }, (info?.messages || Object.keys(state.catalog.messages)).map((type) => el('option', { value: type, selected: type === message.type }, type)))),
      fieldEditors,
      // Outputs that send nothing back (the keyboard and mouse) have no feedback
      info?.receives === false ? null : [
        el('label', { for: id('feedback'), title: 'Matching messages from the output update the widget' }, 'feedback'),
        el('div', { class: 'control' }, el('input', {
          type: 'checkbox', id: id('feedback'), checked: !!mapping.feedback, disabled: !mapping.on,
          onchange: (e) => edit(() => { if (e.target.checked) mapping.feedback = true; else delete mapping.feedback; }),
        }))]),
  );
}

// ---------------------------------------------------------------- links

function setLinks(layout, links) {
  if (links.length) layout.links = links;
  else delete layout.links;
}

function widgetNamed(name) {
  return allWidgets().find(({ widget }) => widget.name === name)?.widget;
}

// The options of a widget a link can change: position, size and its options
function linkOptions(widget) {
  return state.catalog.widgets[widget?.type]?.linkable || [];
}

// Set always; Add to numbers and choices; Toggle on/off options and choices
function linkChanges(kind) {
  return Object.entries(state.catalog.link.changes).filter(([, kinds]) => !kinds || kinds.includes(kind)).map(([name]) => name);
}

// What an option is in the layout (or by default)
function layoutValue(widget, option) {
  if (option.name === 'x' || option.name === 'y') return widget[option.name] || 0;
  if (option.name === 'width' || option.name === 'height') return widget[option.name] ?? 1;
  return widget.options && option.name in widget.options ? widget.options[option.name] : option.default;
}

// Event values a link to an option of `kind` can take
function linkSources(on, kind, change) {
  if (change !== 'Add' && !state.catalog.link.sources.includes(kind)) return [];
  return sourceNames(on).filter((name) => {
    if (name === 'text') return kind === 'str';
    // Colors cover a range: 0.0-1.0 values only
    if (kind === 'color' && change !== 'Add') return !INTEGER_SOURCES.has(name);
    return true;
  });
}

// A first change and value that suit the event and the option: a value from the event where one fits
function defaultLinkValue(link) {
  const target = widgetNamed(link.target);
  const option = linkOptions(target).find((candidate) => candidate.name === link.option);
  for (const key of ['value', 'min', 'max', 'change']) delete link[key];
  if (!option) return;
  const sources = sourceNames(link.on);
  const level = ['value', 'state', 'velocity', 'pressure', 'active'].find((name) => sources.includes(name));
  switch (option.kind) {
    case 'bool': {
      // Follows a switch or a cell; presses toggle it
      const onOff = ['value', 'state'].find((name) => sources.includes(name));
      if (onOff) link.value = { source: onOff };
      else link.change = 'Toggle';
      return;
    }
    case 'enum':
      link.change = 'Toggle';
      return;
    case 'int': {
      // One per pad (e.g. a page per ButtonGroup cell), else one more each time
      const source = widgetNamed(link.widget);
      if (sources.includes('cell') && source && source.width * source.height > 1) link.value = { source: 'cell' };
      else {
        link.change = 'Add';
        link.value = 1;
      }
      return;
    }
    case 'float':
    case 'color':
      link.value = level ? { source: level } : layoutValue(target, option);
      return;
    case 'str':
      if (level) Object.assign(link, { value: { source: level }, min: 0, max: 100 });
      else link.value = layoutValue(target, option) ?? '';
      return;
    default:
      link.value = layoutValue(target, option);
  }
}

// The value a link sets or adds: a constant, or an event value with its range (or offset)
// "if <event value> <op> <constant> then <value> else <value>"
function conditionEditor(link, option, id, edit, change) {
  const condition = link.value;
  const sources = sourceNames(link.on).filter((name) => name !== 'text');
  const source = condition.if?.source;
  const choose = (key) => {
    const commit = (value) => edit(() => { link.value[key] = value; });
    if (change === 'Add' || option.action) {
      return el('input', {
        type: 'number', class: 'small', id: id(key), value: condition[key] ?? 0, step: option.kind === 'float' || option.action ? 'any' : 1,
        onchange: (e) => commit(Number(e.target.value)),
      });
    }
    return optionControl(option, condition[key], (value) => { if (value !== undefined) commit(value); }, id(key))[0];
  };
  return [
    el('div', { class: 'cond-row' },
      el('span', { class: 'word' }, 'if'),
      el('select', {
        id: id('if'), title: 'The event value to compare',
        onchange: (e) => edit(() => { link.value.if = { source: e.target.value }; }),
      }, sources.map((name) => el('option', { value: name, selected: name === source }, name)),
      source && !sources.includes(source) ? el('option', { value: source, selected: true }, `${source} (not available)`) : null),
      el('select', {
        id: id('op'), class: 'op',
        onchange: (e) => edit(() => { link.value.op = e.target.value; }),
      }, state.catalog.link.operators.map((op) => el('option', { value: op, selected: op === (condition.op || '==') }, op))),
      el('input', {
        type: 'text', class: 'small', id: id('to'), value: condition.to ?? 0,
        title: INTEGER_SOURCES.has(source) ? 'A whole number (cell 0 is the bottom-left pad)' : '0.0-1.0 values are compared as they are',
        onchange: (e) => edit(() => {
          const text = e.target.value.trim();
          link.value.to = /^-?\d*\.?\d+$/.test(text) ? Number(text) : text;
        }),
      })),
    el('div', { class: 'cond-row' }, el('span', { class: 'word' }, 'then'), choose('then')),
    el('div', { class: 'cond-row' }, el('span', { class: 'word' }, 'else'), choose('else')),
  ];
}

// A link's value in words: "cell == 3 ? true : false", "{value}", "1"
function describeValue(link) {
  const value = link.value;
  if (value && typeof value === 'object' && 'if' in value) return `${value.if.source} ${value.op || '=='} ${value.to} ? ${value.then} : ${value.else}`;
  if (value && typeof value === 'object') return `{${value.source}}`;
  return value === undefined ? '' : String(value);
}

function linkValueEditor(link, option, id, edit) {
  const change = link.change || 'Set';
  const sources = linkSources(link.on, option.kind, change);
  const isCondition = !!(link.value && typeof link.value === 'object' && 'if' in link.value);
  const isSource = !isCondition && link.value && typeof link.value === 'object' && !Array.isArray(link.value);
  const constant = change === 'Add' ? 1 : option.action ? 0 : layoutValue(widgetNamed(link.target), option);
  const mode = el('select', {
    id: id('value'), title: 'A constant, a value from the event, or a condition choosing between two values',
    onchange: (e) => edit(() => {
      delete link.min;
      delete link.max;
      if (e.target.value === '\u0000if') {
        // Compares an event value (a whole number one first: cell, x...) with a constant
        const all = sourceNames(link.on).filter((name) => name !== 'text');
        const first = all.includes('cell') ? 'cell' : all.find((name) => INTEGER_SOURCES.has(name)) || all[0];
        const onOff = option.kind === 'bool' && change === 'Set';
        link.value = { if: { source: first }, op: '==', to: 0, then: onOff ? true : constant, else: onOff ? false : (option.action ? 0 : option.default ?? constant) };
        return;
      }
      link.value = e.target.value === '' ? constant : { source: e.target.value };
      if (change === 'Set' && option.kind === 'str' && !INTEGER_SOURCES.has(e.target.value)) Object.assign(link, { min: 0, max: 100 });
    }),
  },
  el('option', { value: '', selected: !isSource && !isCondition }, 'constant'),
  el('option', { value: '\u0000if', selected: isCondition }, 'condition…'),
  sources.map((name) => el('option', { value: name, selected: isSource && link.value.source === name }, name)),
  isSource && !sources.includes(link.value.source) ? el('option', { value: link.value.source, selected: true }, `${link.value.source} (not available)`) : null);
  const number = (key, placeholder, attrs = {}) => el('input', {
    type: 'number', class: 'small', value: link[key] ?? '', placeholder, title: key, step: option.kind === 'float' ? 'any' : 1, ...attrs,
    onchange: (e) => edit(() => {
      if (e.target.value === '') delete link[key];
      else link[key] = Number(e.target.value);
    }),
  });
  let detail = null;
  if (isCondition) {
    return el('div', { class: 'control value condition' }, mode, conditionEditor(link, option, id, edit, change));
  }
  if (!isSource) {
    if (change === 'Add') {
      detail = el('input', {
        type: 'number', class: 'small', value: link.value ?? 1, step: option.kind === 'float' ? 'any' : 1,
        title: option.kind === 'enum' ? 'Choices to move by' : 'Added each time',
        onchange: (e) => edit(() => { link.value = option.kind === 'float' ? Number(e.target.value) : parseInt(e.target.value || '0', 10); }),
      });
    } else {
      [detail] = optionControl(option, link.value, (value) => edit(() => { link.value = Number.isNaN(value) ? constant : value ?? constant; }), id('constant'));
    }
  } else if (INTEGER_SOURCES.has(link.value.source)) {
    detail = el('input', {
      type: 'number', class: 'small', value: link.value.offset ?? '', placeholder: '+0', step: 1, title: 'offset',
      onchange: (e) => edit(() => {
        if (e.target.value === '') delete link.value.offset;
        else link.value.offset = parseInt(e.target.value, 10);
      }),
    });
  } else if (change === 'Set' && link.value.source !== 'text') {
    // The range 0.0-1.0 covers
    const title = 'The range 0.0-1.0 covers';
    if (option.kind === 'color') {
      const bound = (key, fallback) => optionControl({ kind: 'color' }, link[key] ?? fallback, (value) => edit(() => { link[key] = value; }), id(key))[0];
      detail = el('span', { class: 'range', title }, bound('min', '#000000'), '–', bound('max', layoutValue(widgetNamed(link.target), option)));
    } else if (option.kind === 'enum') {
      const bound = (key, fallback) => el('select', {
        id: id(key), title: key,
        onchange: (e) => edit(() => { link[key] = e.target.value; }),
      }, option.choices.map((choice) => el('option', { value: choice, selected: choice === (link[key] ?? fallback) }, choice)));
      detail = el('span', { class: 'range', title }, bound('min', option.choices[0]), '–', bound('max', option.choices[option.choices.length - 1]));
    } else if (option.kind !== 'bool') {
      detail = el('span', { class: 'range', title }, number('min', '0'), '–', number('max', option.kind === 'int' && !option.action ? '127' : '1'));
    }
  }
  return el('div', { class: 'control value' }, mode, detail);
}

// Actions a link can call on a target: a widget's methods, or the transport's (target '')
function linkActions(target) {
  if (!target) return Object.fromEntries(Object.entries(state.catalog.link.actions).filter(([name]) => name !== 'debug'));
  return state.catalog.widgets[target.type]?.actions || {};
}

// An action's first value: the pad's cell or the event's step where there is one; a tempo from a fader
function defaultActionValue(link) {
  for (const key of ['value', 'min', 'max', 'change']) delete link[key];
  if (linkActions(widgetNamed(link.target))[link.action] === null) return;
  const sources = sourceNames(link.on);
  if (link.action === 'transport.tempo') {
    if (sources.includes('value')) Object.assign(link, { value: { source: 'value' }, min: 60, max: 180 });
    else link.value = 120;
    return;
  }
  if (link.action === 'transport.tempo_add') {
    link.value = 1;
    return;
  }
  const source = ['step', 'row', 'cell', 'note'].find((name) => sources.includes(name));
  link.value = source ? { source } : 0;
}

// A link writing to the debug log (the event log in the designer, printed when running)
function debugCard(widget, link, index, events) {
  const id = (name) => `link-${index}-${name}`;
  const edit = (mutate) => change(() => mutate(link));
  const sources = sourceNames(link.on);
  return el('div', { class: 'mapping link' },
    el('div', { class: 'mapping-head' },
      el('select', {
        id: id('on'), title: 'The event of this widget that writes',
        onchange: (e) => edit(() => { link.on = e.target.value; }),
      }, events.map((name) => el('option', { value: name, selected: name === link.on }, name))),
      el('span', { class: 'arrow' }, '→'),
      el('select', {
        id: id('target'), title: 'Where it goes',
        onchange: (e) => edit(() => {
          delete link.action;
          delete link.value;
          if (!e.target.value) {
            link.action = 'transport.toggle';
          } else {
            link.target = e.target.value;
            link.option = 'visible';
            defaultLinkValue(link);
          }
        }),
      },
      el('option', { value: '' }, 'Transport'),
      el('option', { value: '\u0000debug', selected: true }, 'Debug log'),
      allWidgets().map(({ widget: candidate }) => el('option', { value: candidate.name }, candidate === widget ? `${candidate.name} (itself)` : candidate.name))),
      el('button', {
        class: 'link remove', title: 'Remove this link',
        onclick: () => change((layout) => setLinks(layout, layout.links.filter((_, i) => i !== index))),
      }, '×')),
    el('div', { class: 'fields' },
      el('label', { for: id('value') }, 'text'),
      el('div', { class: 'control' }, el('input', {
        type: 'text', id: id('value'), value: link.value ?? '', placeholder: `${link.on} {all}`,
        title: `Placeholders take the event's values: ${sources.map((name) => `{${name}}`).join(' ')}; {all} is every value. Empty: the event and every value.`,
        onchange: (e) => edit(() => { if (e.target.value.trim()) link.value = e.target.value; else delete link.value; }),
      })),
      el('p', { class: 'hint', style: 'grid-column: 1 / -1' },
        `Shows in Events (filter: Only debug); printed when the layout runs. Values: ${sources.map((name) => `{${name}}`).join(' ')} {all}`)));
}

function linkCard(widget, link, index) {
  const events = state.catalog.widgets[widget.type]?.events || [];
  if (link.action === 'debug') return debugCard(widget, link, index, events);
  const transport = !link.target;
  const target = transport ? null : widgetNamed(link.target);
  const options = transport ? [] : linkOptions(target);
  const actions = linkActions(target);
  const isAction = link.action !== undefined;
  const option = isAction
    ? (actions[link.action] ? { name: link.action, kind: actions[link.action], action: true } : null)
    : options.find((candidate) => candidate.name === link.option);
  const changeName = link.change || 'Set';
  const id = (name) => `link-${index}-${name}`;
  const edit = (mutate) => change(() => mutate(link));
  // Numbers added to are kept within limits
  const limits = !isAction && changeName === 'Add' && option && (option.kind === 'int' || option.kind === 'float');
  const actionLabel = (name) => name.replace(/^transport\./, '');
  const valueFields = () => {
    if (isAction) {
      if (!(link.action in actions)) return el('p', { class: 'hint' }, `${link.target || 'The transport'} has no action ${link.action}`);
      const label = { play: 'step', 'transport.tempo': 'bpm', 'transport.tempo_add': 'by' }[link.action] || 'with';
      return option ? [el('label', { for: id('value') }, label), linkValueEditor(link, option, id, edit)] : null;
    }
    if (!option) return el('p', { class: 'hint' }, `${link.target} has no option ${link.option}`);
    return [
      el('label', { for: id('change') }, 'change'),
      el('div', { class: 'control' }, el('select', {
        id: id('change'), title: 'Set it, add to it, or toggle it (on/off, next choice)',
        onchange: (e) => edit(() => {
          const next = e.target.value;
          for (const key of ['value', 'min', 'max', 'change']) delete link[key];
          if (next === 'Toggle') link.change = 'Toggle';
          else if (next === 'Add') Object.assign(link, { change: 'Add', value: 1 });
          else {
            defaultLinkValue(link);
            if (link.change) {
              // This option's default is another change: set a constant instead
              for (const key of ['value', 'min', 'max', 'change']) delete link[key];
              link.value = layoutValue(target, option);
            }
          }
        }),
      }, linkChanges(option.kind).map((name) => el('option', { value: name, selected: name === changeName }, name.toLowerCase())))),
      changeName !== 'Toggle' ? [el('label', { for: id('value') }, changeName === 'Add' ? 'by' : 'to'), linkValueEditor(link, option, id, edit)] : null,
      limits ? [
        el('label', { title: 'The lowest and highest it goes' }, 'limits'),
        el('div', { class: 'control value' }, el('span', { class: 'range' }, ...['min', 'max'].flatMap((key, i) => [i ? '–' : null, el('input', {
          type: 'number', class: 'small', id: id(key), value: link[key] ?? '', placeholder: 'none', title: key, step: option.kind === 'float' ? 'any' : 1,
          onchange: (e) => edit(() => {
            if (e.target.value === '') delete link[key];
            else link[key] = Number(e.target.value);
          }),
        })]))),
      ] : null,
    ];
  };
  return el('div', { class: 'mapping link' },
    el('div', { class: 'mapping-head' },
      el('select', {
        id: id('on'), title: 'The event of this widget that changes the option',
        onchange: (e) => edit(() => {
          link.on = e.target.value;
          const source = link.value?.source;
          if (source && !linkSources(link.on, option?.kind, changeName).includes(source)) {
            if (isAction) defaultActionValue(link);
            else defaultLinkValue(link);
          }
        }),
      }, events.map((name) => el('option', { value: name, selected: name === link.on }, name))),
      el('span', { class: 'arrow' }, '→'),
      el('select', {
        id: id('target'), title: 'The widget whose option changes, or the transport',
        onchange: (e) => edit(() => {
          for (const key of ['value', 'min', 'max', 'change']) delete link[key];
          if (!e.target.value || e.target.value === '\u0000debug') {
            // Transport actions and the debug log have no target
            delete link.target;
            delete link.option;
            link.action = e.target.value ? 'debug' : 'transport.toggle';
            return;
          }
          link.target = e.target.value;
          const next = widgetNamed(link.target);
          if (isAction && link.action in linkActions(next)) return defaultActionValue(link);
          delete link.action;
          if (!linkOptions(next).some((candidate) => candidate.name === link.option)) link.option = 'visible';
          defaultLinkValue(link);
        }),
      },
      el('option', { value: '', selected: transport }, 'Transport'),
      el('option', { value: '\u0000debug' }, 'Debug log'),
      allWidgets().map(({ widget: candidate }) => el('option', { value: candidate.name, selected: candidate.name === link.target },
        candidate === widget ? `${candidate.name} (itself)` : candidate.name))),
      el('button', {
        class: 'link remove', title: 'Remove this link',
        onclick: () => change((layout) => setLinks(layout, layout.links.filter((_, i) => i !== index))),
      }, '×')),
    el('div', { class: 'fields' },
      el('label', { for: id('option') }, isAction ? 'action' : 'option'),
      el('div', { class: 'control' }, el('select', {
        id: id('option'), title: 'An option to change, or an action to call',
        onchange: (e) => edit(() => {
          const [kind, name] = e.target.value.split(':');
          if (kind === 'action') {
            delete link.option;
            link.action = name;
            defaultActionValue(link);
          } else {
            delete link.action;
            link.option = name;
            defaultLinkValue(link);
          }
        }),
      },
      options.length ? el('optgroup', { label: 'Options' }, options.map((candidate) => el('option', {
        value: `option:${candidate.name}`, selected: !isAction && candidate.name === link.option,
      }, candidate.name.replace(/_/g, ' ')))) : null,
      Object.keys(actions).length ? el('optgroup', { label: 'Actions' }, Object.keys(actions).map((name) => el('option', {
        value: `action:${name}`, selected: isAction && name === link.action,
      }, actionLabel(name)))) : null)),
      valueFields()),
  );
}

// ---------------------------------------------------------------- the messages and links window

// A floating window listing the messages (layout.mappings) and links of the selected widgets, or
// of every widget. Rules are picked as {kind: 'mapping' | 'link', index}; several picked ones of
// one kind are edited together: a change to the first is made to the others (`spreadChange`).

const RULES_CLIPBOARD = 'pyxelwidgets.rules';

function ruleKey(rule) {
  return `${rule.kind}:${rule.index}`;
}

function ruleObject(rule) {
  return (rule.kind === 'mapping' ? state.layout.mappings : state.layout.links)?.[rule.index];
}

// The selected widgets in layout order
function selectedWidgets() {
  const picked = new Set(selectedPaths().map((path) => widgetAt(path)));
  return allWidgets().map((item) => item.widget).filter((widget) => picked.has(widget));
}

// Widgets whose rules show: the selected ones, or all of them
function ruleWidgets() {
  return state.rules.all ? allWidgets().map((item) => item.widget) : selectedWidgets();
}

function fieldText(value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    if ('if' in value) return `(${value.if?.source} ${value.op || '=='} ${value.to} ? ${value.then} : ${value.else})`;
    return `{${value.source}${value.offset ? `${value.offset > 0 ? '+' : ''}${value.offset}` : ''}}`;
  }
  if (Array.isArray(value)) return value.map(fieldText).join(' ');
  return String(value);
}

// A message in a few words: "ControlChange control 1 · value {value} · channel 1"
function messageText(message = {}) {
  switch (message.type) {
    case 'Command': return `${message.name ?? 'Play'} = ${fieldText(message.value ?? 1)}`;
    case 'OscMessage': return `${message.address ?? '/'} ${fieldText(message.args || [])}`.trim();
    case 'PluginParameter': return `${message.track || '?'} / ${message.plugin || '?'} / ${message.parameter || '?'}`;
    case 'TrackParameter': return `${message.track || '?'} · ${message.parameter || 'Volume'}`;
    default: return Object.entries(message).filter(([key]) => key !== 'type').map(([key, value]) => `${key} ${fieldText(value)}`).join(' · ');
  }
}

// [when, to, what] of a rule
function ruleText(rule, object = ruleObject(rule)) {
  if (rule.kind === 'mapping') {
    return [object.on || 'receive only', object.output, `${object.message?.type || '?'} ${messageText(object.message)}`];
  }
  if (object.action === 'debug') return [object.on, 'Debug log', `"${object.value ?? `${object.on} {all}`}"`];
  const what = object.action ? object.action.replace(/^transport\./, '') : `${(object.change || 'set').toLowerCase()} ${object.option}`;
  const value = describeValue(object);
  return [object.on, object.target || 'Transport', value ? `${what} ${object.change === 'Add' ? 'by' : object.action ? '' : '='} ${value}`.replace(/  +/g, ' ') : what];
}

// The rows the window lists: [{rule, widget, text}], by widget, messages before links
function ruleRows() {
  const query = state.rules.query.trim().toLowerCase();
  const rows = [];
  for (const widget of ruleWidgets()) {
    const add = (kind, list) => list.forEach((object, index) => {
      if (object.widget !== widget.name) return;
      const rule = { kind, index };
      const text = ruleText(rule, object);
      if (query && ![widget.name, ...text].some((part) => String(part).toLowerCase().includes(query))) return;
      rows.push({ rule, widget, text });
    });
    add('mapping', state.layout.mappings || []);
    add('link', state.layout.links || []);
  }
  return rows;
}

function pickedRules() {
  const shown = new Set(ruleRows().map((row) => ruleKey(row.rule)));
  return state.rules.picked.filter((rule) => shown.has(ruleKey(rule)) && ruleObject(rule));
}

function isPicked(rule) {
  return state.rules.picked.some((picked) => ruleKey(picked) === ruleKey(rule));
}

// Click: this one; Shift+click: the rows from the one clicked before; Ctrl/Cmd+click or the box: one more or less
function pickRule(rule, event = {}) {
  const rules = state.rules;
  const rows = ruleRows().map((row) => row.rule);
  if (event.shiftKey && rules.anchor) {
    const keys = rows.map(ruleKey);
    const [a, b] = [keys.indexOf(ruleKey(rules.anchor)), keys.indexOf(ruleKey(rule))];
    if (a >= 0 && b >= 0) {
      rules.picked = rows.slice(Math.min(a, b), Math.max(a, b) + 1);
      return renderRules();
    }
  }
  rules.anchor = rule;
  if (event.ctrlKey || event.metaKey || event.toggle) {
    rules.picked = isPicked(rule) ? rules.picked.filter((picked) => ruleKey(picked) !== ruleKey(rule)) : [...pickedRules(), rule];
  } else {
    rules.picked = [rule];
  }
  renderRules();
}

function openRules(picked = null) {
  state.rules.open = true;
  if (picked) {
    state.rules.picked = picked;
    state.rules.anchor = picked[picked.length - 1] || null;
    // Shown even when the widget isn't selected
    const widgets = new Set(picked.map((rule) => ruleObject(rule)?.widget));
    if (!state.rules.all && !ruleWidgets().some((widget) => widgets.has(widget.name))) {
      const paths = allWidgets().filter(({ widget }) => widgets.has(widget.name)).map(({ path }) => path);
      if (paths.length) state.selection = widgetSelection(paths);
    }
  }
  state.rules.focused = true;
  render();
}

function closeRules() {
  state.rules.open = false;
  state.rules.focused = false;
  state.broadcast = null;
  renderRules();
}

// ---- several rules changed as one

// Paths of the values that differ between two rules: a message's fields, a link's value...
// (event values, conditions and lists count as one value)
function leafPaths(a, b, path = [], found = []) {
  const leaf = (value) => value === null || typeof value !== 'object' || Array.isArray(value) || 'source' in value || 'if' in value;
  if (a !== undefined && b !== undefined && !leaf(a) && !leaf(b)) {
    for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) leafPaths(a[key], b[key], [...path, key], found);
  } else if (JSON.stringify(a) !== JSON.stringify(b)) {
    found.push(path);
  }
  return found;
}

function getPath(object, path) {
  return path.reduce((value, key) => value?.[key], object);
}

function setPath(object, path, value) {
  let parent = object;
  for (const key of path.slice(0, -1)) {
    if (parent[key] === null || typeof parent[key] !== 'object') parent[key] = {};
    parent = parent[key];
  }
  const last = path[path.length - 1];
  if (value === undefined) delete parent[last];
  else parent[last] = JSON.parse(JSON.stringify(value));
}

// Make the change `rep` went through (from `before`) to `others` too, where it fits them: an
// event their widget has, a field their message type has, a value for the same option
function spreadChange(kind, before, rep, others) {
  const order = (path) => (path[1] === 'type' ? 0 : ['target', 'option', 'action', 'output'].includes(path[0]) ? 1 : 2);
  const paths = leafPaths(before, rep).filter((path) => path[0] !== 'widget').sort((a, b) => order(a) - order(b));
  if (!paths.length) return;
  for (const other of others) {
    const events = state.catalog.widgets[widgetNamed(other.widget)?.type]?.events || [];
    for (const path of paths) {
      const value = getPath(rep, path);
      if (path[0] === 'on' && value !== undefined && !events.includes(value)) continue;
      if (kind === 'mapping' && path[0] === 'message' && path[1] !== 'type') {
        const fields = state.catalog.messages[other.message?.type]?.fields || [];
        if (!fields.some((field) => field.name === path[1])) continue;
      }
      if (kind === 'link' && ['value', 'min', 'max', 'change'].includes(path[0])
        && (other.option !== rep.option || other.action !== rep.action)) continue;
      setPath(other, path, value);
    }
    if (kind === 'mapping') {
      // Fields another message type had
      const fields = state.catalog.messages[other.message?.type]?.fields;
      if (fields) for (const key of Object.keys(other.message)) if (key !== 'type' && !fields.some((field) => field.name === key)) delete other.message[key];
      if (!other.on) other.feedback = true;
    }
  }
}

// Marks the editors of values that differ between the picked rules
function markMixed(card, kind, index, rep, others) {
  const prefix = `${kind}-${index}-`;
  const ids = new Set();
  for (const other of others) {
    for (const path of leafPaths(rep, other)) {
      if (path[0] === 'widget') continue;
      if (kind === 'mapping') ids.add(path[0] === 'message' ? (path[1] === 'type' ? 'type' : path[1] === 'args' ? 'arg0' : path[1]) : path[0]);
      else ids.add(path[0] === 'action' ? 'option' : path[0]);
    }
  }
  for (const id of ids) {
    const node = card.querySelector(`#${CSS.escape(prefix + id)}-pick`) || card.querySelector(`#${CSS.escape(prefix + id)}`);
    if (!node) continue;
    const target = node.closest('.control') || node;
    target.classList.add('mixed');
    target.title = 'Differs between the picked ones: each keeps its own until this is changed';
  }
}

// ---- adding, copying, pasting

// New messages for a widget (a Sequencer's notes come with their note-offs)
function newMappings(widget) {
  const output = outputsOf()[0];
  const info = outputInfo(output);
  // Macro buttons: a momentary button fires a shortcut on presses (it changes on releases too)
  const momentary = widget.type === 'Button' && (widget.options?.mode || 'Button') !== 'Switch';
  const on = momentary && info?.messages.includes('Hotkey') ? 'Pressed' : defaultEvent(widget);
  const rules = [{ widget: widget.name, on, output: output.name, message: defaultMessage(widget, on, info) }];
  // A Sequencer's notes end with their gates
  if (on === 'StepPlayed' && rules[0].message.type === 'NoteOn' && info?.messages.includes('NoteOff')) {
    rules.push({ widget: widget.name, on: 'StepEnded', output: output.name, message: defaultMessage(widget, 'StepEnded', info) });
  }
  return rules;
}

function newLink(widget) {
  // A momentary button acts on presses (it changes on releases too)
  const momentary = widget.type === 'Button' && (widget.options?.mode || 'Button') !== 'Switch';
  const on = momentary ? 'Pressed' : defaultEvent(widget);
  // Another widget if there is one
  const target = allWidgets().map((item) => item.widget).find((candidate) => candidate !== widget) || widget;
  const link = { widget: widget.name, on, target: target.name, option: 'visible' };
  defaultLinkValue(link);
  return link;
}

// Add rules made by `make(widget)` (one or a list) to each widget, and pick them
function addRules(kind, widgets, make) {
  if (!widgets.length) return;
  const added = [];
  change((layout) => {
    const list = kind === 'mapping' ? (layout.mappings ||= []) : (layout.links ||= []);
    for (const widget of widgets) {
      for (const rule of [make(widget)].flat()) {
        list.push(rule);
        added.push({ kind, index: list.length - 1 });
      }
    }
    state.rules.picked = added;
    state.rules.anchor = added[added.length - 1];
  });
  openRules();
}

function copyRules(cut = false) {
  const picked = pickedRules();
  if (!picked.length) return;
  const clip = {
    format: RULES_CLIPBOARD,
    mappings: picked.filter((rule) => rule.kind === 'mapping').map(ruleObject),
    links: picked.filter((rule) => rule.kind === 'link').map(ruleObject),
  };
  const text = JSON.stringify(clip);
  state.ruleClipboard = clip;
  try {
    localStorage.setItem(RULES_CLIPBOARD, text);
  } catch {
    // This page only
  }
  navigator.clipboard?.writeText(text).catch(() => {});
  if (cut) deleteRules();
  setStatus(`${cut ? 'Cut' : 'Copied'} ${picked.length} message${picked.length > 1 ? 's and links' : ' or link'}`, 'ok');
}

function readRuleClipboard() {
  try {
    const stored = JSON.parse(localStorage.getItem(RULES_CLIPBOARD) || 'null');
    if (stored?.format === RULES_CLIPBOARD) return stored;
  } catch {
    // Use this page's
  }
  return state.ruleClipboard;
}

// A copied rule for `widget`: null when it can't be (no such output or target, no event it needs)
function adaptRule(kind, rule, widget) {
  const copy = { ...JSON.parse(JSON.stringify(rule)), widget: widget.name };
  const events = state.catalog.widgets[widget.type]?.events || [];
  const needs = kind === 'mapping' ? messageSources(copy.message)
    : [copy.value?.source, copy.value?.if?.source].filter(Boolean);
  if (kind === 'mapping' && !outputsOf().some((output) => output.name === copy.output)) return null;
  if (kind === 'link' && copy.target !== undefined) {
    // A link changing its own widget changes the new one
    if (copy.target === rule.widget) copy.target = widget.name;
    else if (!widgetNamed(copy.target)) return null;
  }
  if (copy.on && !events.includes(copy.on)) {
    const fits = events.find((name) => needs.every((source) => sourceNames(name).includes(source)));
    if (!fits) return null;
    copy.on = events.includes(defaultEvent(widget)) && needs.every((source) => sourceNames(defaultEvent(widget)).includes(source)) ? defaultEvent(widget) : fits;
  }
  return copy;
}

// Paste onto every selected widget (or, with none selected, the widgets they came from)
function pasteRules(clip = readRuleClipboard(), widgets = selectedWidgets()) {
  const rules = [...(clip?.mappings || []).map((rule) => ['mapping', rule]), ...(clip?.links || []).map((rule) => ['link', rule])];
  if (!rules.length) return setStatus('Nothing to paste: copy messages or links first (Ctrl+C in this window)', 'error');
  let pasted = 0, dropped = 0;
  const added = [];
  change((layout) => {
    for (const [kind, rule] of rules) {
      const targets = widgets.length ? widgets : [widgetNamed(rule.widget)].filter(Boolean);
      if (!targets.length) dropped++;
      for (const widget of targets) {
        const copy = adaptRule(kind, rule, widget);
        if (!copy) {
          dropped++;
          continue;
        }
        const list = kind === 'mapping' ? (layout.mappings ||= []) : (layout.links ||= []);
        list.push(copy);
        added.push({ kind, index: list.length - 1 });
        pasted++;
      }
    }
    state.rules.picked = added;
    state.rules.anchor = added[added.length - 1] || null;
  });
  const count = `${pasted} message${pasted === 1 ? ' or link' : 's and links'}`;
  setStatus(dropped ? `Pasted ${count}; ${dropped} left out (their output, target or event isn't there)` : `Pasted ${count}`, dropped ? '' : 'ok');
}

function duplicateRules() {
  const picked = pickedRules();
  if (!picked.length) return;
  const added = [];
  change((layout) => {
    for (const rule of picked) {
      const list = rule.kind === 'mapping' ? layout.mappings : layout.links;
      list.push(JSON.parse(JSON.stringify(list[rule.index])));
      added.push({ kind: rule.kind, index: list.length - 1 });
    }
    state.rules.picked = added;
    state.rules.anchor = added[added.length - 1];
  });
}

function deleteRules() {
  const picked = pickedRules();
  if (!picked.length) return;
  const gone = new Set(picked.map(ruleKey));
  change((layout) => {
    setMappings(layout, (layout.mappings || []).filter((_, index) => !gone.has(`mapping:${index}`)));
    setLinks(layout, (layout.links || []).filter((_, index) => !gone.has(`link:${index}`)));
    state.rules.picked = [];
  });
}

// Keys while the window has the focus (not in a field): true when handled
function rulesKey(event) {
  const mod = event.ctrlKey || event.metaKey;
  const key = event.key.toLowerCase();
  const actions = {
    c: () => copyRules(), x: () => copyRules(true), v: () => pasteRules(), d: () => duplicateRules(),
    a: () => { state.rules.picked = ruleRows().map((row) => row.rule); renderRules(); },
  };
  if (mod && actions[key] && !(key === 'c' && window.getSelection()?.toString())) {
    event.preventDefault();
    actions[key]();
    return true;
  }
  if (mod) return false;
  if (key === 'delete' || key === 'backspace') {
    event.preventDefault();
    deleteRules();
    return true;
  }
  if (key === 'escape') {
    closeRules();
    return true;
  }
  return false;
}

// ---- the window

function buildRules() {
  const window_ = $('rules');
  const head = window_.querySelector('.window-head');
  // Dragged by its title bar; where it is and its size are remembered
  head.addEventListener('pointerdown', (event) => {
    if (event.target.closest('button, input, select') || event.button !== 0) return;
    event.preventDefault();
    const start = { x: event.clientX, y: event.clientY, left: window_.offsetLeft, top: window_.offsetTop };
    const move = (e) => {
      window_.style.left = `${clamp(start.left + e.clientX - start.x, 0, innerWidth - 80)}px`;
      window_.style.top = `${clamp(start.top + e.clientY - start.y, 0, innerHeight - 40)}px`;
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      saveRulesPlace();
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  });
  new ResizeObserver(() => { if (!window_.hidden) saveRulesPlace(); }).observe(window_);
  $('rules-close').onclick = closeRules;
  $('rules-selected').onclick = () => { state.rules.all = false; renderRules(); };
  $('rules-all').onclick = () => { state.rules.all = true; renderRules(); };
  $('rules-search').addEventListener('input', (e) => { state.rules.query = e.target.value; renderRules(); });
  $('rules-add-message').onclick = () => addRules('mapping', selectedWidgets(), newMappings);
  $('rules-add-link').onclick = () => addRules('link', selectedWidgets(), newLink);
  $('rules-copy').onclick = () => copyRules();
  $('rules-cut').onclick = () => copyRules(true);
  $('rules-paste').onclick = () => pasteRules();
  $('rules-duplicate').onclick = duplicateRules;
  $('rules-delete').onclick = deleteRules;
  $('rules-all-rows').onclick = () => { state.rules.picked = ruleRows().map((row) => row.rule); renderRules(); };
  // Which part of the page keys go to; changes spread to several picked rules only from their editor
  document.addEventListener('pointerdown', (event) => {
    state.rules.focused = state.rules.open && !!event.target.closest('#rules');
    if (!event.target.closest('.rule-editor.multi')) state.broadcast = null;
  }, true);
  document.addEventListener('focusin', (event) => {
    if (!event.target.closest('.rule-editor.multi')) state.broadcast = null;
  }, true);
}

function saveRulesPlace() {
  const window_ = $('rules');
  prefs.rulesWindow = { left: window_.offsetLeft, top: window_.offsetTop, width: window_.offsetWidth, height: window_.offsetHeight };
  savePrefs();
}

function placeRules() {
  const window_ = $('rules');
  const stage = $('stage').getBoundingClientRect();
  const place = prefs.rulesWindow || {
    width: Math.min(820, Math.max(480, stage.width - 32)), height: Math.min(560, Math.max(360, stage.height - 32)),
    left: stage.left + 16, top: stage.top + 16,
  };
  const width = Math.min(place.width, innerWidth - 16), height = Math.min(place.height, innerHeight - 16);
  Object.assign(window_.style, {
    width: `${width}px`, height: `${height}px`,
    left: `${clamp(place.left, 0, Math.max(0, innerWidth - width))}px`, top: `${clamp(place.top, 0, Math.max(0, innerHeight - height))}px`,
  });
}

function renderRules() {
  const window_ = $('rules');
  const open = state.rules.open;
  if (window_.hidden === open) {
    window_.hidden = !open;
    if (open) placeRules();
  }
  if (!open) return;
  const rules = state.rules;
  const widgets = ruleWidgets();
  const selected = selectedWidgets();
  const rows = ruleRows();
  rules.picked = pickedRules();
  const picked = rules.picked;
  $('rules-title').textContent = rules.all ? 'All widgets'
    : widgets.length === 1 ? widgets[0].name : widgets.length ? `${widgets.length} widgets` : 'No widget selected';
  $('rules-selected').classList.toggle('active', !rules.all);
  $('rules-all').classList.toggle('active', rules.all);
  const each = selected.length > 1 ? ' to each selected widget' : '';
  $('rules-add-message').disabled = !selected.length || !outputsOf().length;
  $('rules-add-message').title = !outputsOf().length ? 'Add an output first (Outputs, on the left)' : selected.length ? `Send an event${each} to an output` : 'Select a widget first';
  $('rules-add-link').disabled = !selected.length;
  $('rules-add-link').title = selected.length ? `Change an option of a widget on an event${each}` : 'Select a widget first';
  for (const id of ['rules-copy', 'rules-cut', 'rules-duplicate', 'rules-delete']) $(id).disabled = !picked.length;
  const clip = readRuleClipboard();
  const clipped = (clip?.mappings?.length || 0) + (clip?.links?.length || 0);
  $('rules-paste').disabled = !clipped;
  $('rules-paste').title = clipped ? `Paste ${clipped}${selected.length ? (selected.length > 1 ? ` onto each of the ${selected.length} selected widgets` : ` onto ${selected[0].name}`) : ' onto the widgets they came from'} (Ctrl/Cmd+V)` : 'Copy messages or links first (Ctrl/Cmd+C)';
  $('rules-all-rows').disabled = !rows.length;
  // The list, by widget
  const list = $('rules-list');
  const items = [];
  let last = null;
  for (const row of rows) {
    if (row.widget !== last && widgets.length > 1) {
      const own = rows.filter((other) => other.widget === row.widget).map((other) => other.rule);
      items.push(el('li', {
        class: 'rule-widget', title: 'Pick all of its messages and links',
        onclick: () => { rules.picked = own; rules.anchor = own[own.length - 1]; renderRules(); },
      }, row.widget.name, el('span', { class: 'type' }, row.widget.type)));
    }
    last = row.widget;
    const [when, to, what] = row.text;
    const object = ruleObject(row.rule);
    items.push(el('li', {
      class: `rule-row${isPicked(row.rule) ? ' picked' : ''}`, dataset: { rule: ruleKey(row.rule) },
      onclick: (event) => pickRule(row.rule, event),
    },
      el('input', {
        type: 'checkbox', checked: isPicked(row.rule), 'aria-label': 'Pick',
        onclick: (event) => { event.stopPropagation(); pickRule(row.rule, { toggle: true }); },
      }),
      el('span', { class: `rule-kind ${row.rule.kind}` }, row.rule.kind === 'mapping' ? 'msg' : 'link'),
      el('span', { class: 'rule-text' },
        el('span', { class: 'rule-line' }, el('b', {}, when), ' → ', to, row.rule.kind === 'mapping' && object.feedback ? el('span', { class: 'feedback', title: 'Feedback: the output updates the widget' }, ' ⇄') : null),
        el('span', { class: 'rule-what', title: what }, what))));
  }
  if (!rows.length) {
    items.push(el('li', { class: 'hint' }, rules.query ? `Nothing matches "${rules.query}".`
      : !widgets.length ? 'Select widgets on the grid or in Layers, or show All widgets.'
        : 'No messages or links yet: add one above.'));
  }
  list.replaceChildren(...items);
  fill($('rules-editor'), ruleEditor(picked));
}

function ruleEditor(picked) {
  if (!picked.length) {
    return el('p', { class: 'hint' }, 'Pick a message or link to edit it. Shift+click picks a range, Ctrl/Cmd+click one more: '
      + 'changes are then made to all of them. Ctrl/Cmd+C and V copy and paste them onto the selected widgets.');
  }
  const kinds = new Set(picked.map((rule) => rule.kind));
  if (kinds.size > 1) {
    return el('p', { class: 'hint' }, `${picked.length} picked. Messages and links are edited apart: pick only messages or only links to change them together. Copy, cut, duplicate and delete work on all of them.`);
  }
  const [first] = picked;
  const rep = ruleObject(first);
  const widget = widgetNamed(rep.widget);
  if (!widget) return el('p', { class: 'hint' }, `${rep.widget} isn't in the layout.`);
  const card = first.kind === 'mapping' ? mappingCard(widget, rep, first.index) : linkCard(widget, rep, first.index);
  if (picked.length === 1) {
    return el('div', { class: 'rule-editor' }, el('p', { class: 'rule-for' }, widget.name, el('span', { class: 'type' }, widget.type)), card);
  }
  const others = picked.slice(1).map(ruleObject);
  markMixed(card, first.kind, first.index, rep, others);
  const names = [...new Set([rep, ...others].map((object) => object.widget))];
  const editor = el('div', { class: 'rule-editor multi' },
    el('p', { class: 'rule-for' }, `${picked.length} ${first.kind === 'mapping' ? 'messages' : 'links'} of ${names.length > 3 ? `${names.length} widgets` : names.join(', ')}`),
    el('p', { class: 'hint note' }, 'A change here is made to all of them. Dashed fields differ: each keeps its own value until you change it.'),
    card);
  // Changes made in this editor spread to the other picked rules (see change())
  const arm = () => {
    const now = pickedRules();
    if (now.length > 1 && now[0].kind === first.kind) state.broadcast = { kind: first.kind, rep: ruleObject(now[0]), others: now.slice(1).map(ruleObject) };
  };
  for (const type of ['pointerdown', 'focusin', 'keydown', 'change']) editor.addEventListener(type, arm, true);
  return editor;
}

// The Behaviour group's list: a line per message and link, opening the window
function ruleSummary(widgets) {
  const names = new Set(widgets.map((widget) => widget.name));
  const rows = [];
  (state.layout.mappings || []).forEach((object, index) => { if (names.has(object.widget)) rows.push({ kind: 'mapping', index }); });
  (state.layout.links || []).forEach((object, index) => { if (names.has(object.widget)) rows.push({ kind: 'link', index }); });
  const single = widgets.length === 1;
  return [
    el('h4', {}, 'Messages and links'),
    outputsOf().length ? null : el('p', { class: 'hint' }, 'Add an output (a MIDI port, OSC, Mackie Control or HUI) to send events to other software.'),
    rows.length ? el('ul', { class: 'rule-summary' }, rows.slice(0, 10).map((rule) => {
      const [when, to, what] = ruleText(rule);
      return el('li', { onclick: () => openRules([rule]), title: 'Edit it' },
        el('span', { class: `rule-kind ${rule.kind}` }, rule.kind === 'mapping' ? 'msg' : 'link'),
        el('span', { class: 'rule-text' },
          el('span', { class: 'rule-line' }, single ? null : `${ruleObject(rule).widget}: `, el('b', {}, when), ' → ', to),
          el('span', { class: 'rule-what' }, what)));
    }), rows.length > 10 ? el('li', { class: 'more', onclick: () => openRules(rows), title: 'Edit them' }, `and ${rows.length - 10} more…`) : null)
      : el('p', { class: 'hint' }, 'Send events to outputs (messages), or change other widgets\' options when this one is used (links): show a group, switch a page, move a keyboard\'s octave, dim a color…'),
    el('div', { class: 'actions' },
      outputsOf().length ? el('button', { onclick: () => addRules('mapping', widgets, newMappings), title: single ? 'Send an event of this widget to an output' : 'Add one to each' }, single ? 'Add message' : 'Add message to each') : null,
      el('button', { onclick: () => addRules('link', widgets, newLink), title: single ? 'Change an option of a widget on an event of this one' : 'Add one to each' }, single ? 'Add link' : 'Add link to each'),
      el('button', { onclick: () => openRules(rows), title: 'Edit, copy and paste them in a window (M)' }, rows.length ? 'Edit…' : 'Open editor')),
  ];
}

// ---------------------------------------------------------------- the drawer: events, connections, Python, problems

const CLOCK_EVENTS = new Set(['StepPlayed', 'StepEnded', 'RowPlayed', 'ClipQueued', 'ClipStarted', 'ClipStopped', 'PageChanged']);

function drawerPrefs() {
  prefs.drawer ||= { open: true, tab: 'events', height: 230, filter: 'all', handlers: false, code: 'loader' };
  return prefs.drawer;
}

function openDrawer(tab) {
  const drawer = drawerPrefs();
  drawer.open = true;
  if (tab) drawer.tab = tab;
  savePrefs();
  renderDrawer();
}

function renderDrawer() {
  const drawer = drawerPrefs();
  $('drawer').classList.toggle('collapsed', !drawer.open);
  document.documentElement.style.setProperty('--drawer', `${drawer.height}px`);
  $('drawer-toggle').textContent = drawer.open ? '▾' : '▴';
  const problems = findProblems();
  const counts = { connections: connectionRows().length, problems: problems.length };
  for (const button of document.querySelectorAll('.tabs button')) {
    const tab = button.dataset.tab;
    button.classList.toggle('active', tab === drawer.tab && drawer.open);
    fill(button, button.dataset.label || (button.dataset.label = button.textContent),
      counts[tab] ? el('span', { class: 'count' }, counts[tab]) : null);
  }
  for (const panel of document.querySelectorAll('.drawer-body > [data-panel]')) panel.classList.toggle('shown', panel.dataset.panel === drawer.tab);
  if (drawer.tab === 'events') renderEvents();
  const tools = $('drawer-tools');
  if (drawer.tab === 'events') {
    fill(tools,
      el('select', {
        id: 'event-filter', title: 'Which events to show',
        onchange: (e) => { drawer.filter = e.target.value; savePrefs(); renderEvents(); },
      }, [['all', 'All events'], ['selected', 'Selected widget'], ['quiet', 'Without clock events'], ['debug', 'Only debug']].map(([value, label]) =>
        el('option', { value, selected: drawer.filter === value }, label))),
      el('button', {
        id: 'pause-events', class: state.eventsPaused ? 'active' : '', title: 'Pause the list (events are still kept)',
        onclick: () => { state.eventsPaused = !state.eventsPaused; renderDrawer(); renderEvents(); },
      }, state.eventsPaused ? 'Resume' : 'Pause'),
      el('button', { id: 'clear-events', class: 'link', onclick: () => { state.eventLog = []; renderEvents(); } }, 'clear'));
  } else if (drawer.tab === 'python') {
    fill(tools,
      el('div', { class: 'segmented', role: 'group', 'aria-label': 'Which code' },
        [['loader', 'Layout file', 'Load the layout file and run it'],
          ['standalone', 'Standalone', 'Build the same surface in code, without the layout file']].map(([value, label, title]) =>
          el('button', {
            id: `code-${value}`, class: (drawer.code || 'loader') === value ? 'active' : '', title,
            onclick: () => { drawer.code = value; savePrefs(); renderDrawer(); },
          }, label))),
      el('label', { title: 'Print each widget\'s main event' },
        el('input', { type: 'checkbox', id: 'code-handlers', checked: !!drawer.handlers, onchange: (e) => { drawer.handlers = e.target.checked; savePrefs(); renderCode(); } }),
        ' with handlers'),
      el('button', {
        id: 'copy-code', class: 'link',
        onclick: async () => {
          await navigator.clipboard?.writeText($('code').textContent);
          setStatus('Copied the Python snippet', 'ok');
        },
      }, 'copy'));
    renderCode();
  } else {
    tools.replaceChildren();
  }
  renderConnections();
  renderProblems(problems);
}

// Every link, message and binding: [kind, from, to, what, select]
function connectionRows() {
  const rows = [];
  (state.layout.links || []).forEach((link, index) => {
    const to = link.target || (link.action === 'debug' ? 'Debug log' : 'Transport');
    const what = link.action ? `${link.on} → ${link.action.replace(/^transport\./, '')}` : `${link.on} → ${(link.change || 'set').toLowerCase()} ${link.option}`;
    const value = describeValue(link);
    rows.push(['link', link.widget, to, value ? `${what} = ${value}` : what, () => openRules([{ kind: 'link', index }])]);
  });
  (state.layout.mappings || []).forEach((mapping, index) => {
    const message = mapping.message || {};
    const what = `${mapping.on || 'receive only'} → ${message.type}${message.name ? ` ${message.name}` : ''}${message.address ? ` ${message.address}` : ''}${mapping.feedback ? ' · feedback' : ''}`;
    rows.push(['message', mapping.widget, mapping.output, what, () => openRules([{ kind: 'mapping', index }])]);
  });
  for (const binding of state.layout.bindings || []) {
    const device = state.layout.devices[binding.device];
    const from = `${deviceInfo(device)?.model || device?.type} ${binding.control}`;
    rows.push(['binding', from, binding.widget || binding.action, binding.widget ? (binding.options?.takeover || '') : 'action', () => select({ kind: 'device', index: binding.device })]);
  }
  return rows;
}

function renderConnections() {
  const rows = connectionRows();
  fill($('connections'), rows.length
    ? el('table', {},
      el('tr', {}, ['', 'From', 'To', 'What'].map((head) => el('th', {}, head))),
      rows.map(([kind, from, to, what, go]) => el('tr', { class: 'connection', onclick: go, title: 'Select it' },
        el('td', { class: 'kind' }, kind), el('td', {}, from), el('td', {}, to), el('td', {}, what))))
    : el('p', { class: 'hint' }, 'No links, messages or bindings yet: add them on a widget, under Behaviour.'));
}

// Things that won't work as the layout is: [level ('error' or 'warning'), text, select]
// The event value a TrackParameter's parameter takes on an output (null: the event has none that fits)
function trackValueSource(parameter, info, sources) {
  const wanted = parameter === 'Volume' ? ['value']
    : parameter === 'Pan' ? [info?.parameter_value || 'delta']
    : ['state', 'value'];
  return wanted.find((name) => sources.includes(name)) || null;
}

function findProblems() {
  const problems = [];
  if (state.error) problems.push(['error', state.error, null]);
  for (const mapping of state.layout.mappings || []) {
    const message = mapping.message || {};
    if (message.type === 'PluginParameter' && !(message.track && message.plugin && message.parameter)) {
      problems.push(['warning', `${mapping.widget}: pick the track, plug-in and parameter it controls`, () => selectWidgetNamed(mapping.widget)]);
    }
    if (message.type === 'TrackParameter' && !message.track) {
      problems.push(['warning', `${mapping.widget}: pick the track it controls`, () => selectWidgetNamed(mapping.widget)]);
    }
  }
  if (state.hardware.sync?.error) problems.push(['warning', `Sync to a DAW: ${state.hardware.sync.error}`, () => select(null)]);
  const names = new Map(allWidgets().map(({ widget, path }) => [widget.name, { widget, path }]));
  const outputs = new Set(outputsOf().map((output) => output.name));
  for (const link of state.layout.links || []) {
    if (!names.has(link.widget)) problems.push(['error', `A link from a missing widget "${link.widget}"`, null]);
    else if (link.target && !names.has(link.target)) problems.push(['error', `${link.widget}: links to a missing widget "${link.target}"`, () => selectWidgetNamed(link.widget)]);
    else if (link.option && !linkOptions(names.get(link.target).widget).some((option) => option.name === link.option)) {
      problems.push(['error', `${link.widget}: ${link.target} has no option "${link.option}"`, () => selectWidgetNamed(link.widget)]);
    }
  }
  for (const mapping of state.layout.mappings || []) {
    if (!outputs.has(mapping.output)) problems.push(['error', `${mapping.widget}: sends to a missing output "${mapping.output}"`, () => selectWidgetNamed(mapping.widget)]);
  }
  outputsOf().forEach((output, index) => {
    const info = outputInfo(output);
    if (info?.midi && !output.virtual && !output.input && !output.output) {
      problems.push(['warning', `Output ${output.name} has no port: give it a virtual port name, or input/output ports`, () => select({ kind: 'output', index })]);
    }
    const status = state.hardware.outputs?.[index];
    if (status && !status.connected && status.error) problems.push(['warning', `Output ${output.name}: ${status.error}`, () => select({ kind: 'output', index })]);
    if (status?.warning) problems.push(['warning', `Output ${output.name}: ${status.warning}`, () => select({ kind: 'output', index })]);
  });
  state.layout.devices.forEach((device, index) => {
    const status = state.hardware.devices?.[index];
    if (status && !status.connected && status.error && !device.type.startsWith('virtual.')) {
      problems.push(['warning', `${deviceInfo(device)?.model || device.type}: ${status.error}`, () => select({ kind: 'device', index })]);
    }
  });
  const { width, height } = state.layout.surface;
  for (const { widget, path } of allWidgets()) {
    if (path.length === 1 && ((widget.x || 0) + widget.width > width || (widget.y || 0) + widget.height > height)) {
      problems.push(['warning', `${widget.name} reaches past the surface`, () => select(widgetSelection([path]))]);
    }
  }
  return problems;
}

function renderProblems(problems = findProblems()) {
  fill($('problem-list'), problems.length
    ? problems.map(([level, text, go]) => el('li', { class: level, onclick: go || null, title: go ? 'Show it' : null }, text))
    : el('li', { class: 'none' }, 'No problems found.'));
  const badge = $('problems');
  badge.hidden = !problems.length;
  badge.classList.toggle('error', problems.some(([level]) => level === 'error'));
  badge.textContent = `⚠ ${problems.length}`;
  badge.title = `${problems.length} problem${problems.length === 1 ? '' : 's'} in the layout`;
}

function renderEvents() {
  if (state.eventsPaused) return;
  const filter = drawerPrefs().filter;
  const selected = state.selection?.kind === 'widget' ? new Set(selectedPaths().map((path) => widgetAt(path)?.name)) : new Set();
  const shown = state.eventLog.filter((event) => filter === 'all'
    || (filter === 'quiet' && !CLOCK_EVENTS.has(event.event))
    || (filter === 'debug' && event.event === 'Debug')
    || (filter === 'selected' && selected.has(event.widget)));
  fill($('events'), shown.slice(-200).reverse().map((event) => {
    const debug = event.event === 'Debug';
    const fields = debug ? event.text : Object.entries(event)
      .filter(([key]) => !['id', 'widget', 'event'].includes(key))
      .map(([key, value]) => `${key}=${Array.isArray(value) ? `[${value}]` : value}`)
      .join(' ');
    return el('li', { class: debug ? 'debug' : null, title: `${event.widget} ${event.event} ${fields}` },
      el('b', {}, event.widget), ' ', el('span', { class: 'kind' }, event.event), ' ', fields);
  }));
}

function bindDrawer() {
  for (const button of document.querySelectorAll('.tabs button')) {
    button.onclick = () => {
      const drawer = drawerPrefs();
      drawer.open = !(drawer.open && drawer.tab === button.dataset.tab);
      drawer.tab = button.dataset.tab;
      savePrefs();
      renderDrawer();
    };
  }
  $('drawer-toggle').onclick = () => {
    drawerPrefs().open = !drawerPrefs().open;
    savePrefs();
    renderDrawer();
  };
  // Drag the bar to make the drawer taller or shorter
  $('drawer').querySelector('.drawer-bar').addEventListener('pointerdown', (event) => {
    if (event.target.closest('button, select, input, label') || !drawerPrefs().open) return;
    const startY = event.clientY;
    const startHeight = drawerPrefs().height;
    const move = (e) => {
      drawerPrefs().height = clamp(startHeight - (e.clientY - startY), 80, Math.round(window.innerHeight * 0.7));
      document.documentElement.style.setProperty('--drawer', `${drawerPrefs().height}px`);
      renderBoard();
      renderOverlay();
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      savePrefs();
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  });
}

// ---------------------------------------------------------------- panels and help

function renderPanels() {
  prefs.panels ||= { left: true, right: true, leftWidth: 290, rightWidth: 360 };
  const panels = prefs.panels;
  document.body.classList.toggle('no-left', !panels.left);
  document.body.classList.toggle('no-right', !panels.right);
  document.documentElement.style.setProperty('--left', `${panels.leftWidth}px`);
  document.documentElement.style.setProperty('--right', `${panels.rightWidth}px`);
  $('toggle-left').classList.toggle('active', panels.left);
  $('toggle-right').classList.toggle('active', panels.right);
}

function togglePanel(side, shown = !prefs.panels[side]) {
  prefs.panels[side] = shown;
  savePrefs();
  renderPanels();
  renderBoard();
  renderOverlay();
}

// The grid alone (F), or back to the panels as they were
function toggleFocus() {
  const panels = prefs.panels;
  if (panels.left || panels.right) {
    panels.before = { left: panels.left, right: panels.right };
    panels.left = panels.right = false;
  } else {
    Object.assign(panels, panels.before || { left: true, right: true });
  }
  savePrefs();
  renderPanels();
  renderBoard();
  renderOverlay();
}

function bindSplitters() {
  for (const [id, side, sign] of [['split-left', 'leftWidth', 1], ['split-right', 'rightWidth', -1]]) {
    $(id).addEventListener('pointerdown', (event) => {
      event.preventDefault();
      const startX = event.clientX;
      const start = prefs.panels[side];
      $(id).classList.add('active');
      const move = (e) => {
        prefs.panels[side] = clamp(start + sign * (e.clientX - startX), 200, 560);
        renderPanels();
        renderBoard();
        renderOverlay();
      };
      const up = () => {
        $(id).classList.remove('active');
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', up);
        savePrefs();
      };
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
    });
  }
}

const SHORTCUTS = [
  ['E / T', 'Edit or Try mode'],
  ['Alt + click', 'press a pad while editing'],
  ['Space', 'play or stop the transport'],
  ['Ctrl/Cmd + Z, Ctrl/Cmd + Shift + Z', 'undo, redo'],
  ['Ctrl/Cmd + S', 'save'],
  ['Ctrl/Cmd + C, X, V', 'copy, cut and paste widgets (also between layouts)'],
  ['Ctrl/Cmd + D', 'duplicate'],
  ['Ctrl/Cmd + A', 'select everything in the group'],
  ['Shift + click, drag on empty pads', 'select several on the grid'],
  ['Shift + click, Ctrl/Cmd + click in Layers', 'select a range of layers, add or remove one'],
  ['Ctrl/Cmd + G, Ctrl/Cmd + Shift + G', 'group, ungroup'],
  ['Arrows, Shift + arrows', 'move, resize'],
  ['Delete', 'delete'],
  ['Wheel, Ctrl/Cmd + + / − / 0', 'zoom (the toolbar sets whether the wheel zooms or scrolls)'],
  ['Middle button drag, Shift + wheel', 'move around the grid'],
  ['[ and ]', 'show or hide the left or right panel'],
  ['F', 'the grid alone (again: back)'],
  ['`', 'show or hide the drawer'],
  ['M', 'the messages and links window'],
  ['In that window: click, Shift + click, Ctrl/Cmd + click', 'pick one, a range, one more (picked ones are edited together)'],
  ['In that window: Ctrl/Cmd + C, X, V, D, A, Delete', 'copy, cut, paste onto the selected widgets, duplicate, pick all, delete'],
  ['Escape', 'select nothing (in the window: close it)'],
  ['?', 'this list'],
];

function showShortcuts() {
  const dialog = newDialog();
  fill(dialog,
    el('h3', {}, 'Keyboard shortcuts'),
    el('table', { class: 'keys' }, SHORTCUTS.map(([keys, what]) => el('tr', {},
      el('td', {}, keys.split(', ').map((key, i) => [i ? ', ' : null, el('kbd', {}, key)])), el('td', {}, what)))),
    el('div', { class: 'buttons' }, el('button', { onclick: () => dialog.close() }, 'Close')));
  dialog.showModal();
}

// ---------------------------------------------------------------- history and sync

function change(mutate) {
  state.history.push(JSON.stringify(state.layout));
  if (state.history.length > 300) state.history.shift();
  state.future = [];
  const broadcast = state.broadcast;
  const before = broadcast && JSON.parse(JSON.stringify(broadcast.rep));
  mutate(state.layout);
  if (broadcast) spreadChange(broadcast.kind, before, broadcast.rep, broadcast.others);
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
    const exists = (path) => { try { return !!widgetAt(path); } catch { return false; } };
    const paths = selection.paths.filter(exists);
    state.selection = widgetSelection(paths, exists(selection.path) ? selection.path : undefined);
  } else if (selection?.kind === 'device' && !state.layout.devices[selection.index]) {
    state.selection = null;
  } else if (selection?.kind === 'output' && !outputsOf()[selection.index]) {
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
    if (frame.playing !== state.playing || frame.synced !== state.synced) {
      state.playing = frame.playing;
      state.synced = !!frame.synced;
      renderToolbar();
    }
    state.bpm = frame.bpm;
    if ($('sync-status')) $('sync-status').textContent = syncStatus();
    $('position').textContent = frame.position ? `bar ${frame.position}` : '';
    if (JSON.stringify(frame.hardware) !== JSON.stringify(state.hardware)) {
      state.hardware = frame.hardware;
      renderToolbar();
      renderDevices();
      renderOutputs();
      renderDrawer();
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
  for (const event of events) {
    state.lastEvent = Math.max(state.lastEvent, event.id);
    state.eventLog.push(event);
  }
  if (state.eventLog.length > 500) state.eventLog.splice(0, state.eventLog.length - 500);
  renderEvents();
}

// Input goes in order, and after any pending layout change: rebuilding the preview resets widget state
let inputs = Promise.resolve();
function sendInput(x, y, velocity) {
  inputs = inputs.then(flushSync).then(() => api('POST', '/api/input', { x, y, velocity })).catch(() => {});
}

const held = new Map();
function padDown(event) {
  if (state.mode !== 'try' && !event.altKey) return startMarquee(event);
  pressAt(event);
}

// Press the pad under the pointer (Try mode, or Alt + click while editing) until it's released
function pressAt(event) {
  const pad = document.elementsFromPoint(event.clientX, event.clientY).find((node) => node.classList?.contains('pad'));
  if (!pad) return;
  event.preventDefault();
  event.stopPropagation();
  const x = Number(pad.dataset.x), y = Number(pad.dataset.y);
  held.set(event.pointerId, [x, y]);
  const up = (e) => {
    if (e.pointerId !== event.pointerId) return;
    window.removeEventListener('pointerup', up);
    window.removeEventListener('pointercancel', up);
    padUp(e);
  };
  window.addEventListener('pointerup', up);
  window.addEventListener('pointercancel', up);
  sendInput(x, y, 1.0);
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
  renderOutputs();
  renderProperties();
  renderCode();
  renderToolbar();
  renderDirty();
  renderDrawer();
  renderWelcome();
  renderRules();
}

function step() {
  const style = getComputedStyle(document.documentElement);
  return parseFloat(style.getPropertyValue('--pad')) + parseFloat(style.getPropertyValue('--gap'));
}

function renderBoard() {
  const { width, height } = state.layout.surface;
  const stage = $('stage');
  const gap = 4;
  // Pads as big as the stage allows (the board's frame and the stage's padding around them)
  const fit = (space, count) => (space - 80 - gap * (count - 1)) / count;
  const fitted = Math.max(16, Math.min(200, fit(stage.clientWidth, width), fit(stage.clientHeight - 40, height)));
  state.fitted = fitted;
  // In the browser's layout units (1/64 px), so pad positions add up exactly
  const pad = Math.round(clamp(fitted * state.zoom, 6, 320) * 64) / 64;
  document.documentElement.style.setProperty('--pad', `${pad}px`);
  document.documentElement.style.setProperty('--step', `${pad + gap}px`);
  zoomLabel();
  positionBoard();
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
  positionBoard();
}

// The board in the middle of the stage (above the status line), moved by `state.pan`; at least
// a corner of it stays in view
function positionBoard() {
  const stage = $('stage'), board = $('board');
  const width = board.offsetWidth, height = board.offsetHeight;
  const room = [stage.clientWidth, stage.clientHeight - 40];
  const keep = 80;
  const pan = state.pan;
  const centre = [(room[0] - width) / 2, (room[1] - height) / 2];
  pan.x = clamp(pan.x, keep - width - centre[0], room[0] - keep - centre[0]);
  pan.y = clamp(pan.y, keep - height - centre[1], room[1] - keep - centre[1]);
  board.style.left = `${Math.round(centre[0] + pan.x)}px`;
  board.style.top = `${Math.round(centre[1] + pan.y)}px`;
}

function panBy(dx, dy) {
  state.pan.x += dx;
  state.pan.y += dy;
  positionBoard();
}

// Zooming eases towards `target` a frame at a time; the pad under `anchor` (client x, y) stays put
const zooming = { target: null, anchor: null, frame: null };

// The zoom it is going to
function zoomLabel() {
  const shown = zooming.target ?? state.zoom;
  $('zoom-fit').textContent = Math.abs(shown - 1) < 0.005 ? 'Fit' : `${Math.round(shown * 100)}%`;
}

function setZoom(zoom, anchor = null) {
  zooming.target = clamp(zoom, 0.25, 8);
  zooming.centre = zoom === 1 && !anchor;
  zooming.anchor = anchor ? { x: anchor.clientX, y: anchor.clientY } : null;
  zoomLabel();
  if (zooming.frame === null) zooming.frame = requestAnimationFrame(zoomFrame);
}

function zoomFrame() {
  zooming.frame = null;
  const target = zooming.target;
  if (target === null) return;
  // A third of the way each frame, evenly on a log scale
  const next = Math.abs(Math.log(target / state.zoom)) < 0.004 ? target : state.zoom * (target / state.zoom) ** 0.35;
  if (zooming.centre) {
    // Fitting also brings the board back to the middle
    const left = next === target ? 0 : 0.65;
    state.pan.x *= left;
    state.pan.y *= left;
  }
  zoomNow(next, zooming.centre ? null : zooming.anchor);
  if (next === target && !(zooming.centre && (state.pan.x || state.pan.y))) zooming.target = null;
  else zooming.frame = requestAnimationFrame(zoomFrame);
  if (zooming.target === null) renderBoard();
}

// Zoom at once, keeping the point at `anchor` (else the stage's middle) over the same spot of the grid
function zoomNow(zoom, anchor = null) {
  const stage = $('stage');
  const bounds = stage.getBoundingClientRect();
  const point = anchor || { x: bounds.left + stage.clientWidth / 2, y: bounds.top + stage.clientHeight / 2 };
  const before = $('pads').getBoundingClientRect();
  const u = (point.x - before.left) / before.width, v = (point.y - before.top) / before.height;
  state.zoom = zoom;
  renderBoard();
  const after = $('pads').getBoundingClientRect();
  panBy(point.x - (after.left + u * after.width), point.y - (after.top + v * after.height));
}

// Outlines follow --step, so zooming doesn't redraw them
function place(node, x, y, width, height) {
  const surfaceHeight = state.layout.surface.height;
  node.style.left = `calc(${x} * var(--step) - 2px)`;
  node.style.top = `calc(${surfaceHeight - y - height} * var(--step) - 2px)`;
  node.style.width = `calc(${width} * var(--step))`;
  node.style.height = `calc(${height} * var(--step))`;
}

// Links between widgets: the widgets `name` changes, and the ones changing it
function relations(name) {
  const links = state.layout.links || [];
  return {
    affects: new Set(links.filter((link) => link.widget === name && link.target && link.target !== name).map((link) => link.target)),
    affectedBy: new Set(links.filter((link) => link.target === name && link.widget !== name).map((link) => link.widget)),
  };
}

function renderOverlay() {
  const overlay = $('overlay');
  overlay.replaceChildren();
  // Devices at the same place (e.g. a Launchpad mirrored in a browser) share one tag
  const places = new Map();
  state.layout.devices.forEach((device, index) => {
    const key = `${device.x || 0},${device.y || 0}`;
    if (!places.has(key)) places.set(key, []);
    places.get(key).push(index);
  });
  state.layout.devices.forEach((device, index) => {
    const [width, height] = deviceSize(device);
    const selected = state.selection?.kind === 'device' && state.selection.index === index;
    const together = places.get(`${device.x || 0},${device.y || 0}`);
    const tag = together[0] === index ? el('span', { class: 'tag' },
      together.map((other, i) => [
        i ? el('span', { class: 'mirror' }, '+') : null,
        el('span', {
          title: 'Drag to move the device on the surface',
          onpointerdown: (event) => startDeviceDrag(event, other),
        }, deviceInfo(state.layout.devices[other])?.model || state.layout.devices[other].type),
      ]),
      together.length > 1 ? el('span', { class: 'mirror', title: 'They show the same pads' }, '· mirrored') : null) : null;
    const outline = el('div', { class: `outline device${selected ? ' selected' : ''}`, dataset: { device: index } }, tag);
    place(outline, device.x || 0, device.y || 0, width, height);
    overlay.append(outline);
  });
  const paths = selectedPaths();
  const single = paths.length === 1;
  const related = single ? relations(widgetAt(paths[0]).name) : { affects: new Set(), affectedBy: new Set() };
  const hiddenHere = viewSet('hidden');
  const locked = viewSet('locked');
  for (const { widget, path } of allWidgets()) {
    const [x, y] = absolute(path);
    const selected = isSelected(path);
    // Widgets on other pages of a Pages aren't shown
    if (hiddenBy(path).length && !selected) continue;
    const hidden = widget.options?.visible === false;
    const classes = ['outline', 'widget'];
    if (isGroup(widget)) classes.push('group');
    if (selected) classes.push('selected');
    if (related.affects.has(widget.name)) classes.push('affects');
    if (related.affectedBy.has(widget.name)) classes.push('affected-by');
    if (locked.has(widget.name)) classes.push('locked');
    if (hiddenHere.has(widget.name) && !selected) classes.push('hidden-here');
    const role = related.affects.has(widget.name) ? ' · changed by the selection' : related.affectedBy.has(widget.name) ? ' · changes the selection' : '';
    const outline = el('div', {
      class: classes.join(' '),
      title: `${widget.name} (${widget.type})${role}`,
      dataset: { path: path.join('.') },
      onpointerdown: (event) => startDrag(event, path, 'move'),
    }, el('span', { class: 'tag' }, widget.name));
    if (hidden) outline.style.opacity = 0.35;
    if (selected && single) outline.append(el('div', { class: 'handle', onpointerdown: (event) => startDrag(event, path, 'resize') }));
    place(outline, x, y, widget.width, widget.height);
    overlay.append(outline);
  }
}

// Calls move(dx, dy) in pads while the pointer drags, then done(dx, dy)
function dragPads(event, move, done) {
  const start = [event.clientX, event.clientY];
  let delta = [0, 0];
  const onMove = (e) => {
    delta = [Math.round((e.clientX - start[0]) / step()), -Math.round((e.clientY - start[1]) / step())];
    move(...delta);
  };
  const onUp = () => {
    window.removeEventListener('pointermove', onMove);
    window.removeEventListener('pointerup', onUp);
    done(...delta);
  };
  window.addEventListener('pointermove', onMove);
  window.addEventListener('pointerup', onUp);
}

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

// The furthest every widget of `paths` can move together while staying in its parent
function moveLimits(paths) {
  const limits = { dx: [-Infinity, Infinity], dy: [-Infinity, Infinity] };
  for (const path of paths) {
    const widget = widgetAt(path);
    const [parentWidth, parentHeight] = containerSize(path);
    const x = widget.x || 0, y = widget.y || 0;
    limits.dx = [Math.max(limits.dx[0], -x), Math.min(limits.dx[1], parentWidth - widget.width - x)];
    limits.dy = [Math.max(limits.dy[0], -y), Math.min(limits.dy[1], parentHeight - widget.height - y)];
  }
  return limits;
}

function startDrag(event, path, kind) {
  if (event.altKey && state.mode === 'edit') return pressAt(event);
  if (state.mode !== 'edit' || event.button !== 0) return;
  event.stopPropagation();
  event.preventDefault();
  if (event.shiftKey || event.ctrlKey || event.metaKey) return toggleSelected(path);
  if (!isSelected(path)) {
    state.selection = widgetSelection([path]);
    render();
  }
  if (kind === 'resize') {
    const widget = widgetAt(path);
    const [parentWidth, parentHeight] = containerSize(path);
    const x = widget.x || 0, y = widget.y || 0;
    const node = $('overlay').querySelector(`.outline.widget[data-path="${path.join('.')}"]`);
    const size = (dx, dy) => [clamp(widget.width + dx, 1, parentWidth - x), clamp(widget.height + dy, 1, parentHeight - y)];
    return dragPads(event,
      (dx, dy) => place(node, ...absolute(path), ...size(dx, dy)),
      (dx, dy) => {
        const [width, height] = size(dx, dy);
        if (width !== widget.width || height !== widget.height) change(() => Object.assign(widget, { width, height }));
      });
  }
  // Move every selected widget (a selected group carries its children)
  const paths = topSelected();
  const limits = moveLimits(paths);
  const nodes = paths.map((p) => [p, $('overlay').querySelector(`.outline.widget[data-path="${p.join('.')}"]`)]);
  const offset = (dx, dy) => [clamp(dx, ...limits.dx), clamp(dy, ...limits.dy)];
  dragPads(event,
    (dx, dy) => {
      const [ox, oy] = offset(dx, dy);
      for (const [p, node] of nodes) {
        const [x, y] = absolute(p);
        if (node) place(node, x + ox, y + oy, widgetAt(p).width, widgetAt(p).height);
      }
    },
    (dx, dy) => {
      const [ox, oy] = offset(dx, dy);
      if (!ox && !oy) return;
      const widgets = paths.map(widgetAt);
      change(() => widgets.forEach((widget) => Object.assign(widget, { x: (widget.x || 0) + ox, y: (widget.y || 0) + oy })));
    });
}

function startDeviceDrag(event, index) {
  if (state.mode !== 'edit' || event.button !== 0) return;
  event.stopPropagation();
  event.preventDefault();
  if (!(state.selection?.kind === 'device' && state.selection.index === index)) select({ kind: 'device', index });
  const device = state.layout.devices[index];
  const [width, height] = deviceSize(device);
  const { width: surfaceWidth, height: surfaceHeight } = state.layout.surface;
  const x = device.x || 0, y = device.y || 0;
  // Inside the surface; one bigger than the surface can only shift over it
  const position = (dx, dy) => [
    clamp(x + dx, Math.min(0, surfaceWidth - width), Math.max(0, surfaceWidth - width)),
    clamp(y + dy, Math.min(0, surfaceHeight - height), Math.max(0, surfaceHeight - height)),
  ];
  const node = $('overlay').querySelector(`.outline.device[data-device="${index}"]`);
  dragPads(event,
    (dx, dy) => place(node, ...position(dx, dy), width, height),
    (dx, dy) => {
      const [nx, ny] = position(dx, dy);
      if (nx !== x || ny !== y) change(() => Object.assign(device, { x: nx, y: ny }));
    });
}

// Widgets inside a rectangle of pads (x0, y0 inclusive, x1, y1 exclusive): a group that
// doesn't fit offers its children instead
function widgetsIn(x0, y0, x1, y1) {
  const found = [];
  const visit = (list, prefix) => list.forEach((widget, index) => {
    const path = [...prefix, index];
    if (hiddenBy(path).length) return;
    const [x, y] = absolute(path);
    // Locked and hidden-here widgets aren't picked on the grid
    const skipped = viewSet('locked').has(widget.name) || viewSet('hidden').has(widget.name);
    if (!skipped && x >= x0 && y >= y0 && x + widget.width <= x1 && y + widget.height <= y1) found.push(path);
    else if (widget.widgets) visit(widget.widgets, path);
  });
  visit(state.layout.widgets, []);
  return found;
}

// Dragging on empty space draws a selection rectangle; a click there selects the surface
function startMarquee(event) {
  if (state.mode !== 'edit' || event.button !== 0) return;
  event.preventDefault();
  const overlay = $('overlay');
  const bounds = overlay.getBoundingClientRect();
  const adding = event.shiftKey || event.ctrlKey || event.metaKey;
  const kept = adding ? selectedPaths() : [];
  const start = [event.clientX - bounds.left, event.clientY - bounds.top];
  const box = el('div', { class: 'marquee' });
  let moved = false;
  const move = (e) => {
    const end = [e.clientX - bounds.left, e.clientY - bounds.top];
    if (!moved && Math.hypot(end[0] - start[0], end[1] - start[1]) < 4) return;
    if (!moved) overlay.append(box);
    moved = true;
    const [left, right] = [Math.min(start[0], end[0]), Math.max(start[0], end[0])];
    const [top, bottom] = [Math.min(start[1], end[1]), Math.max(start[1], end[1])];
    Object.assign(box.style, { left: `${left}px`, top: `${top}px`, width: `${right - left}px`, height: `${bottom - top}px` });
    // Pads whose centre is inside
    const size = step();
    const centre = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--pad')) / 2;
    const first = (from) => Math.ceil((from - centre) / size), after = (to) => Math.floor((to - centre) / size) + 1;
    const height = state.layout.surface.height;
    const [x0, x1] = [first(left), after(right)];
    const rows = [first(top), after(bottom)];
    const found = x1 > x0 && rows[1] > rows[0] ? widgetsIn(x0, height - rows[1], x1, height - rows[0]) : [];
    for (const node of overlay.querySelectorAll('.outline.widget')) {
      const path = node.dataset.path.split('.').map(Number);
      node.classList.toggle('selected', [...kept, ...found].some((p) => samePath(p, path)));
    }
    box.dataset.found = JSON.stringify(found);
  };
  const up = () => {
    window.removeEventListener('pointermove', move);
    window.removeEventListener('pointerup', up);
    box.remove();
    if (!moved) {
      if (!adding) select(null);
      return;
    }
    const found = JSON.parse(box.dataset.found || '[]').filter((path) => !kept.some((p) => samePath(p, path)));
    select(widgetSelection([...kept, ...found]));
  };
  window.addEventListener('pointermove', move);
  window.addEventListener('pointerup', up);
}

const ICONS = {
  eye: '<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z" fill="none" stroke="currentColor" stroke-width="1.4"/><circle cx="8" cy="8" r="2" fill="currentColor"/></svg>',
  eyeOff: '<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M2 14L14 2" stroke="currentColor" stroke-width="1.6"/></svg>',
  lock: '<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><rect x="3" y="7" width="10" height="7" rx="1.5" fill="currentColor"/><path d="M5 7V5a3 3 0 0 1 6 0v2" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>',
};

function icon(name) {
  const span = el('span', { class: 'svg' });
  span.innerHTML = ICONS[name];
  return span;
}

function renderTree() {
  const collapsed = viewSet('collapsed');
  const hiddenHere = viewSet('hidden');
  const locked = viewSet('locked');
  const query = $('layer-search').value.trim().toLowerCase();
  const matches = (widget) => !query || widget.name.toLowerCase().includes(query) || widget.type.toLowerCase().includes(query)
    || (widget.widgets || []).some(matches);
  // Groups around the selection open up, without being remembered as open
  const open = new Set(selectedPaths().flatMap((path) => path.slice(0, -1).map((_, i) => widgetAt(path.slice(0, i + 1)).name)));
  const toggle = (kind, name, on, titles, icons) => el('button', {
    class: `toggle ${kind}${on ? ' on' : ''}`, title: on ? titles[1] : titles[0], 'aria-label': on ? titles[1] : titles[0],
    onclick: (event) => {
      event.stopPropagation();
      toggleView(kind, name);
    },
  }, icon(on ? icons[1] : icons[0]));
  const build = (list, prefix) => el('ul', {}, [...list.entries()].reverse().filter(([, widget]) => matches(widget)).map(([index, widget]) => {
    const path = [...prefix, index];
    const selected = isSelected(path);
    const children = widget.widgets?.length;
    const folded = children && collapsed.has(widget.name) && !query && !open.has(widget.name);
    const offPage = widget.type !== undefined && prefix.length && widgetAt(prefix).type === 'Pages' && index !== currentPage(widgetAt(prefix));
    const here = hiddenHere.has(widget.name);
    return el('li', {},
      el('div', {
        class: `node${selected ? ' selected' : ''}${offPage ? ' off-page' : ''}${here ? ' hidden-here' : ''}`,
        title: offPage ? 'Another page: selecting it shows that page' : 'Drag to reorder, or onto a group to move it inside',
        draggable: 'true',
        dataset: { path: path.join('.') },
        ondragstart: (event) => {
          // Dragging a selected layer moves the whole selection
          state.layerDrag = isSelected(path) ? topSelected() : [path];
          event.dataTransfer.setData('text/plain', widget.name);
          event.dataTransfer.effectAllowed = 'move';
        },
        ondragend: () => { state.layerDrag = null; clearDropMarks(); },
        ondragover: (event) => layerDragOver(event, path),
        ondrop: (event) => layerDrop(event, path),
        onclick: (event) => {
          // From the layer clicked before (unless the selection changed elsewhere since), else the widget picked last
          const anchor = state.layerAnchor && state.layerAnchor.selection === state.selection ? state.layerAnchor.path : state.selection?.path;
          const remember = (from) => { state.layerAnchor = { path: from, selection: state.selection }; };
          if (event.shiftKey && anchor) {
            selectLayerRange(anchor, path);
            return remember(anchor);
          }
          if (event.shiftKey || event.ctrlKey || event.metaKey) {
            toggleSelected(path);
            return remember(path);
          }
          const hidden = hiddenBy(path);
          if (!hidden.length) {
            select(widgetSelection([path]));
            return remember(path);
          }
          // Show the page the widget is on
          change(() => {
            for (const [pagesPath, page] of hidden) setOption(widgetAt(pagesPath), 'page', page || undefined);
            state.selection = widgetSelection([path]);
          });
          remember(path);
        },
      },
        el('button', {
          class: `caret${children ? '' : ' none'}`, title: folded ? 'Show what is inside' : 'Fold', 'aria-label': folded ? 'Expand' : 'Collapse',
          onclick: (event) => {
            event.stopPropagation();
            if (children) toggleView('collapsed', widget.name);
          },
        }, folded ? '▸' : '▾'),
        el('span', { class: 'name' }, widget.name),
        el('span', { class: 'type' }, folded ? `${widget.type} · ${children}` : widget.type),
        toggle('hidden', widget.name, here, ['Hide in the designer (the layout keeps it)', 'Show in the designer'], ['eye', 'eyeOff']),
        toggle('locked', widget.name, locked.has(widget.name), ['Lock: no dragging it on the grid', 'Unlock'], ['lock', 'lock'])),
      children && !folded ? build(widget.widgets, path) : null);
  }));
  const tree = $('tree');
  tree.replaceChildren(...build(state.layout.widgets, []).children);
  if (!state.layout.widgets.length) tree.append(el('li', { class: 'hint' }, 'No widgets yet.'));
  else if (!tree.children.length) tree.append(el('li', { class: 'hint' }, `Nothing matches "${query}".`));
}

// Shift+click in Layers: every layer shown between the one clicked before and this one
function selectLayerRange(from, to) {
  const shown = [...$('tree').querySelectorAll('.node')].map((node) => node.dataset.path.split('.').map(Number));
  const start = shown.findIndex((path) => samePath(path, from));
  const end = shown.findIndex((path) => samePath(path, to));
  if (start < 0 || end < 0) return toggleSelected(to);
  const range = shown.slice(Math.min(start, end), Math.max(start, end) + 1);
  select(widgetSelection(range, to));
}

// ---------------------------------------------------------------- reordering layers

function clearDropMarks() {
  for (const node of $('tree').querySelectorAll('.drop-above, .drop-below, .drop-into')) {
    node.classList.remove('drop-above', 'drop-below', 'drop-into');
  }
}

// The group a layer dropped into ``path`` goes in: a group, or the shown page of a Pages
function dropContainer(path) {
  const widget = widgetAt(path);
  if (widget.type === 'Pages') {
    const page = widget.widgets?.[currentPage(widget)];
    return page && isGroup(page) ? [...path, currentPage(widget)] : null;
  }
  return isGroup(widget) ? path : null;
}

// Where a drop on the layer at ``path`` puts the dragged ones: above or below it (the
// tree lists the topmost first), or into it when it's a group and the pointer is in the middle
function layerZone(event, path) {
  const dragged = state.layerDrag || [];
  // Not onto itself or inside itself
  if (dragged.some((from) => samePath(from, path) || isInside(path, from))) return null;
  const bounds = event.currentTarget.getBoundingClientRect();
  const at = (event.clientY - bounds.top) / bounds.height;
  const container = dropContainer(path);
  if (container && !dragged.some((from) => samePath(from, container) || isInside(container, from)) && at > 0.25 && at < 0.75) return 'into';
  return at < 0.5 ? 'above' : 'below';
}

function layerDragOver(event, path) {
  if (!state.layerDrag) return;
  const zone = layerZone(event, path);
  clearDropMarks();
  if (!zone) return;
  event.preventDefault();
  event.stopPropagation();
  event.dataTransfer.dropEffect = 'move';
  event.currentTarget.classList.add(`drop-${zone}`);
}

function layerDrop(event, path) {
  const paths = state.layerDrag;
  const zone = paths && layerZone(event, path);
  clearDropMarks();
  state.layerDrag = null;
  if (!zone) return;
  event.preventDefault();
  event.stopPropagation();
  moveLayers(paths, path, zone);
}

// Move the widgets at ``paths`` above or below the one at ``target``, or into it. They
// keep their place on the grid when they fit in the new group, else move inside it.
function moveLayers(paths, target, zone) {
  // In drawing order, so they stay in it
  const widgets = [...paths].sort(comparePaths).map(widgetAt);
  const placed = new Map(widgets.map((widget, i) => [widget, absolute(pathsOf([widget])[0])]));
  const anchor = widgetAt(target);
  const container = zone === 'into' ? widgetAt(dropContainer(target)) : null;
  change((layout) => {
    for (const widget of widgets) {
      const list = childrenOf(pathsOf([widget])[0]);
      list.splice(list.indexOf(widget), 1);
    }
    let parent, list, index;
    if (container) {
      parent = pathsOf([container])[0];
      container.widgets = container.widgets || [];
      list = container.widgets;
      // On top of what's in it
      index = list.length;
    } else {
      const at = pathsOf([anchor])[0];
      parent = at.slice(0, -1);
      list = childrenOf(at);
      index = list.indexOf(anchor) + (zone === 'above' ? 1 : 0);
    }
    const [ox, oy] = parent.length ? absolute(parent) : [0, 0];
    const [width, height] = parent.length ? [widgetAt(parent).width, widgetAt(parent).height] : [layout.surface.width, layout.surface.height];
    for (const widget of widgets) {
      const [ax, ay] = placed.get(widget);
      widget.width = Math.min(widget.width, width);
      widget.height = Math.min(widget.height, height);
      widget.x = clamp(ax - ox, 0, width - widget.width);
      widget.y = clamp(ay - oy, 0, height - widget.height);
    }
    list.splice(index, 0, ...widgets);
    state.selection = widgetSelection(pathsOf(widgets));
  });
}

function comparePaths(a, b) {
  for (let i = 0; i < Math.min(a.length, b.length); i++) if (a[i] !== b[i]) return a[i] - b[i];
  return a.length - b.length;
}

// Dropped below the last layer: topmost on the surface
function treeDragOver(event) {
  if (!state.layerDrag || event.target.closest('.node')) return;
  event.preventDefault();
  clearDropMarks();
}

function treeDrop(event) {
  if (!state.layerDrag || event.target.closest('.node')) return;
  event.preventDefault();
  const paths = state.layerDrag;
  state.layerDrag = null;
  // Above the topmost surface widget that isn't being dragged
  const roots = state.layout.widgets.map((_, index) => index).reverse();
  const top = roots.find((index) => !paths.some((path) => samePath(path, [index])));
  if (top !== undefined) moveLayers(paths, [top], 'above');
}

function renderDevices() {
  const list = $('devices');
  list.replaceChildren(...state.layout.devices.map((device, index) => {
    const selected = state.selection?.kind === 'device' && state.selection.index === index;
    return el('li', { class: selected ? 'selected' : '', onclick: () => select({ kind: 'device', index }) },
      el('span', { class: 'swatch-device' }),
      el('span', { class: 'label' },
        el('span', { class: 'name' }, deviceInfo(device)?.model || device.type),
        el('span', { class: 'type' }, `at ${device.x || 0}, ${device.y || 0}`),
        // A browser grid: where to open it
        state.hardware.devices?.[index]?.url ? el('a', {
          class: 'type url', href: state.hardware.devices[index].url, target: '_blank', title: 'Open it in a browser on this network',
          onclick: (e) => e.stopPropagation(),
        }, state.hardware.devices[index].url) : null),
      hardwareDot(index),
      connectButton('devices', index));
  }));
  if (!state.layout.devices.length) list.append(el('li', { class: 'hint' }, 'Preview only. Add the hardware the layout runs on.'));
}

function hardwareDot(index, list = 'devices') {
  const status = state.hardware[list]?.[index];
  if (!status) return el('span', { class: 'dot', title: 'Connecting…' });
  if (!status.connected && !status.error) return el('span', { class: 'dot idle', title: 'Not connected' });
  return el('span', {
    class: `dot ${status.connected ? 'on' : 'off'}`,
    title: status.connected ? (list === 'devices' ? 'Connected: mirrors the preview, pads work the widgets' : 'Connected: sends and receives messages') : status.error,
  });
}

// Connects or disconnects a layout device or output (an on-screen device can't be)
function connectButton(kind, index) {
  const entry = (kind === 'devices' ? state.layout.devices : outputsOf())[index];
  if (entry?.type?.startsWith('virtual.')) return null;
  const connected = !!state.hardware[kind]?.[index]?.connected;
  return el('button', {
    class: `connect${connected ? ' on' : ''}`,
    title: connected ? 'Disconnect' : (state.hardware[kind]?.[index]?.error || 'Connect'),
    onclick: (event) => {
      event.stopPropagation();
      setConnected(kind, index, !connected);
    },
  }, connected ? 'Disconnect' : 'Connect');
}

async function setConnected(kind, index, connected) {
  // The server connects what's in the layout it has
  await flushSync();
  const reply = await api('POST', '/api/connect', { kind, index, connected });
  if (!reply.ok) return setStatus(reply.error, 'error');
  state.hardware = { devices: reply.devices, outputs: reply.outputs };
  renderDevices();
  renderOutputs();
  const status = state.hardware[kind][index];
  if (connected && !status?.connected) setStatus(`Couldn't connect: ${status?.error}`, 'error');
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

// A labelled editor for one option from the catalog schema. `prefix` keeps element ids
// apart; `apply(value)` replaces setting the option on `target` (e.g. on several widgets).
function optionField(target, option, prefix = 'option', apply = null) {
  if (option.kind === 'frames') return [];
  const options = target.options || {};
  const set = option.name in options;
  const value = set ? options[option.name] : option.default;
  const commit = (newValue) => change(() => (apply ? apply(newValue) : setOption(target, option.name, newValue)));
  const id = `${prefix}-${option.name}`;
  const [control, suggestions] = optionControl(option, value, commit, id);
  return [
    el('label', { for: id, class: set ? 'changed' : '', title: option.name }, option.name.replace(/_/g, ' ')),
    el('div', { class: 'control' }, control, suggestions,
      el('button', { class: 'link reset', title: `Reset to ${JSON.stringify(option.default)}`, onclick: () => commit(undefined) }, 'reset')),
  ];
}

// The input for one option kind (and a datalist of suggestions for rates), with element id `id`
function optionControl(option, value, commit, id) {
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
      const picker = el('input', { type: 'color', value: rgb, title: 'Color' });
      const slider = el('input', { type: 'range', min: 0, max: 255, value: alpha, title: 'Opacity', 'aria-label': 'Opacity' });
      const shown = el('span', { class: 'alpha', title: 'Opacity' }, `${Math.round(alpha / 2.55)}%`);
      const update = () => commit(picker.value + (Number(slider.value) === 255 ? '' : Number(slider.value).toString(16).padStart(2, '0')));
      picker.addEventListener('change', update);
      slider.addEventListener('input', () => { shown.textContent = `${Math.round(slider.value / 2.55)}%`; });
      slider.addEventListener('change', update);
      control = el('div', { class: 'color' }, picker, slider, shown);
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
    case 'rate': {
      // Any note value is accepted; the list only suggests common ones. Some also take seconds.
      const parse = (text) => (option.seconds && /^\d*\.?\d+$/.test(text) ? Number(text) : text || undefined);
      control = el('input', {
        type: 'text', value: value ?? '', list: `${id}-rates`,
        placeholder: value == null ? 'off' : null,
        title: option.seconds ? 'A note value (1/8, bar…) or seconds (0.5)' : 'A note value (1/16, 1/8., beat, bar…)',
        onchange: (e) => commit(parse(e.target.value.trim())),
      });
      suggestions = el('datalist', { id: `${id}-rates` }, option.choices.map((choice) => el('option', { value: choice })));
      break;
    }
    default:
      control = el('input', { type: 'text', value: value ?? '', onchange: (e) => commit(e.target.value) });
  }
  control.id = id;
  return [control, suggestions];
}

// The animation of one or more widgets (several only show one they share)
function animationFields(widgets) {
  const entries = widgets.map((widget) => widget.animation);
  const same = entries.every((entry) => JSON.stringify(entry) === JSON.stringify(entries[0]));
  const type = same ? (entries[0]?.type ?? '') : null;
  const info = type ? state.catalog.animations[type] : null;
  const select = el('select', {
    id: 'animation-type',
    onchange: (e) => change(() => widgets.forEach((widget) => {
      if (e.target.value) widget.animation = { type: e.target.value, options: {} };
      else delete widget.animation;
    })),
  },
  type === null ? el('option', { value: 'mixed', selected: true, disabled: true }, 'mixed') : null,
  el('option', { value: '', selected: type === '' }, 'None'),
  Object.keys(state.catalog.animations).map((name) => el('option', { value: name, selected: name === type }, name)));
  return [
    el('div', { class: 'fields' },
      el('label', { for: 'animation-type', title: 'Changes how the widget looks over time; note values follow the transport' }, 'type'),
      el('div', { class: 'control' }, select),
      info ? info.options.flatMap((option) => optionField(entries[0], option, 'animation',
        widgets.length > 1 ? (value) => widgets.forEach((widget) => setOption(widget.animation, option.name, value)) : null)) : null),
    info ? el('p', { class: 'hint note' }, info.doc.replace(/``/g, '')) : null,
  ];
}

// ---------------------------------------------------------------- sprite frames

// A Sprite's frames sized to the widget: rows from the top, each a list of colors or null.
// Stored frames of another size keep their bottom-left, like the Sprite does.
function spriteFrames(widget) {
  const frames = widget.options?.frames?.length ? widget.options.frames : [[]];
  return frames.map((rows) => Array.from({ length: widget.height }, (_, top) => {
    const row = rows[rows.length - widget.height + top] || [];
    return Array.from({ length: widget.width }, (_, x) => row[x] ?? null);
  }));
}

function setFrames(widget, frames) {
  const blank = frames.length === 1 && frames[0].every((row) => row.every((color) => color === null));
  setOption(widget, 'frames', blank ? undefined : frames);
}

function spriteEditor(widget) {
  if (state.spriteFor !== widget.name) {
    state.spriteFor = widget.name;
    state.spriteFrame = 0;
  }
  const frames = spriteFrames(widget);
  const index = state.spriteFrame = clamp(state.spriteFrame, 0, frames.length - 1);
  const paint = state.paint;
  const edit = (mutate) => change(() => {
    const copy = spriteFrames(widget);
    mutate(copy);
    setFrames(widget, copy);
  });
  const showFrame = (i) => { state.spriteFrame = i; renderProperties(); };

  // A stroke paints cells as the pointer passes over them, then changes the layout once
  let stroke = null;
  const paintCell = (cell) => {
    if (!stroke || !cell?.classList.contains('cell')) return;
    const color = stroke.erase ? null : paint.color;
    stroke.frame[Number(cell.dataset.top)][Number(cell.dataset.x)] = color;
    cell.style.backgroundColor = color || '';
    cell.classList.toggle('empty', !color);
  };
  const size = clamp(Math.floor(266 / Math.max(widget.width, widget.height * 0.75)) - 2, 6, 28);
  const grid = el('div', {
    class: 'sprite-grid', id: 'sprite-grid', style: `grid-template-columns: repeat(${widget.width}, ${size}px)`,
    oncontextmenu: (e) => e.preventDefault(),
    onpointerdown: (e) => {
      e.preventDefault();
      grid.setPointerCapture(e.pointerId);
      stroke = { erase: paint.erase || e.button === 2, frame: frames[index].map((row) => [...row]) };
      paintCell(e.target);
    },
    // Captured: find the cell under the pointer
    onpointermove: (e) => paintCell(document.elementFromPoint(e.clientX, e.clientY)),
    onpointerup: () => {
      const done = stroke;
      stroke = null;
      if (done && JSON.stringify(done.frame) !== JSON.stringify(frames[index])) edit((copy) => { copy[index] = done.frame; });
    },
  }, frames[index].map((row, top) => row.map((color, x) => el('div', {
    class: `cell${color ? '' : ' empty'}`, dataset: { top, x },
    style: `width: ${size}px; height: ${size}px;${color ? ` background-color: ${color}` : ''}`,
  }))));

  const blankFrame = () => Array.from({ length: widget.height }, () => Array(widget.width).fill(null));
  const swatches = SWATCHES.filter((name) => state.catalog.colors[name]).map((name) => [name, state.catalog.colors[name]]);
  return [
    el('div', { class: 'frames' },
      frames.map((_, i) => el('button', { class: i === index ? 'active' : '', onclick: () => showFrame(i), title: `Paint frame ${i + 1}` }, String(i + 1))),
      el('button', { title: 'Add a blank frame after this one', onclick: () => { state.spriteFrame = index + 1; edit((copy) => copy.splice(index + 1, 0, blankFrame())); } }, '+')),
    el('div', { class: 'paint' },
      el('input', {
        type: 'color', value: paint.color, title: 'Paint color',
        onchange: (e) => { Object.assign(paint, { color: e.target.value, erase: false }); renderProperties(); },
      }),
      el('div', { class: 'swatches' }, swatches.map(([name, text]) => el('button', {
        class: `swatch${!paint.erase && paint.color === text ? ' active' : ''}`, title: name, style: `background-color: ${text}`,
        onclick: () => { Object.assign(paint, { color: text, erase: false }); renderProperties(); },
      }))),
      el('button', {
        class: paint.erase ? 'active' : '', title: 'Paint transparent cells (or drag with the right button)',
        onclick: () => { paint.erase = !paint.erase; renderProperties(); },
      }, 'Eraser')),
    grid,
    el('div', { class: 'actions' },
      el('button', { title: 'Paint the whole frame', onclick: () => edit((copy) => { copy[index] = copy[index].map((row) => row.map(() => (paint.erase ? null : paint.color))); }) }, 'Fill'),
      el('button', { title: 'Copy this frame after it', onclick: () => { state.spriteFrame = index + 1; edit((copy) => copy.splice(index + 1, 0, copy[index].map((row) => [...row]))); } }, 'Copy'),
      el('button', { title: 'Move earlier', disabled: index === 0, onclick: () => { state.spriteFrame = index - 1; edit((copy) => copy.splice(index - 1, 0, ...copy.splice(index, 1))); } }, '◀'),
      el('button', { title: 'Move later', disabled: index === frames.length - 1, onclick: () => { state.spriteFrame = index + 1; edit((copy) => copy.splice(index + 1, 0, ...copy.splice(index, 1))); } }, '▶'),
      el('button', {
        class: 'danger', title: frames.length > 1 ? 'Delete this frame' : 'Clear this frame',
        onclick: () => edit((copy) => (copy.length > 1 ? copy.splice(index, 1) : copy.splice(0, 1, blankFrame()))),
      }, frames.length > 1 ? 'Delete' : 'Clear')),
    el('p', { class: 'hint note' }, frames.length > 1
      ? 'Left-drag paints, right-drag erases. Set a rate to play the frames.'
      : 'Left-drag paints, right-drag erases. Add frames to animate it.'),
  ];
}

// Several widgets: their shared options and animation, and what can be done to all
function multiProperties(panel, paths) {
  const widgets = paths.map(widgetAt);
  const types = [...new Set(widgets.map((widget) => widget.type))];
  const optionsOf = (type) => state.catalog.widgets[type]?.options || [];
  const shared = optionsOf(types[0]).filter((option) => option.kind !== 'frames'
    && types.every((type) => optionsOf(type).some((other) => other.name === option.name && other.kind === option.kind)));
  // Shows a value when every widget has it
  const common = { options: {} };
  for (const option of shared) {
    const values = widgets.map((widget) => widget.options?.[option.name]);
    if (values[0] !== undefined && values.every((value) => JSON.stringify(value) === JSON.stringify(values[0]))) common.options[option.name] = values[0];
  }
  fill(panel,
    el('div', { class: 'props-head' },
      el('h3', {}, `${widgets.length} widgets`),
      el('div', { class: 'actions' },
        el('button', { onclick: () => duplicate(), title: 'Duplicate (Ctrl+D)' }, 'Duplicate'),
        el('button', { onclick: () => groupSelection(), title: 'Put them in a new Group (Ctrl+G)' }, 'Group'),
        el('button', { class: 'danger', onclick: () => removeSelection(), title: 'Delete (Del)' }, 'Delete'))),
    el('p', { class: 'doc' }, widgets.map((widget) => widget.name).join(', ')),
    shared.length ? [
      el('h4', {}, types.length > 1 ? 'Shared options' : 'Options'),
      el('div', { class: 'fields' }, shared.flatMap((option) => optionField(common, option, 'option',
        (value) => widgets.forEach((widget) => setOption(widget, option.name, value))))),
    ] : null,
    group('behaviour', 'Behaviour', ruleSummary(widgets)),
    group('animation', 'Animation', animationFields(widgets)),
    el('p', { class: 'hint note' }, 'Drag one or use the arrow keys to move them together. Shift+click adds or removes a widget; drag on empty pads to select an area; Shift+click in Layers selects a range.'),
  );
}

function numberInput(label, value, onchange, attrs = {}) {
  return el('label', {}, label, el('input', { type: 'number', value, step: 1, ...attrs, onchange: (e) => onchange(parseInt(e.target.value, 10)) }));
}

// Options most layouts leave alone: shown under "More options"
// Mackie Control's plug-in mode buttons too
const ADVANCED = new Set(['visible', 'propagation', 'interactive', 'held_time', 'double_press_time',
  'plugin_button', 'channel_button', 'next_page', 'previous_page']);

// A collapsible group of the properties panel; open or closed is remembered in this browser
function group(key, title, children, { count = null, open = true } = {}) {
  prefs.groups ||= {};
  const details = el('details', { class: 'group', dataset: { group: key } },
    el('summary', {}, title, count ? el('span', { class: 'count' }, count) : null),
    children);
  details.open = prefs.groups[key] ?? open;
  details.addEventListener('toggle', () => {
    prefs.groups[key] = details.open;
    savePrefs();
  });
  return details;
}

// Option fields, the rarely changed ones folded away (open when one of them is set)
function optionFields(target, options, prefix = 'option') {
  const main = options.filter((option) => !ADVANCED.has(option.name));
  const more = options.filter((option) => ADVANCED.has(option.name));
  const changed = more.some((option) => option.name in (target.options || {}));
  return [
    main.flatMap((option) => optionField(target, option, prefix)),
    more.length ? el('details', { class: 'more', open: changed },
      el('summary', {}, `More options (${more.map((option) => option.name.replace(/_/g, ' ')).join(', ')})`),
      el('div', { class: 'fields' }, more.flatMap((option) => optionField(target, option, prefix)))) : null,
  ];
}

// What changes a widget from elsewhere: links of other widgets, device controls, outputs' feedback
function controlledBy(widget) {
  const items = [];
  for (const link of state.layout.links || []) {
    if (link.target !== widget.name || link.widget === widget.name) continue;
    const what = link.action ? `${link.on} → ${link.action}` : `${link.on} → ${(link.change || 'set').toLowerCase()} ${link.option}`;
    const value = describeValue(link);
    items.push({ from: link.widget, what: value ? `${what} = ${value}` : what, go: () => selectWidgetNamed(link.widget) });
  }
  for (const binding of state.layout.bindings || []) {
    if (binding.widget !== widget.name) continue;
    const device = state.layout.devices[binding.device];
    items.push({ from: deviceInfo(device)?.model || device?.type || 'device', what: `control ${binding.control}`, go: () => select({ kind: 'device', index: binding.device }) });
  }
  for (const mapping of state.layout.mappings || []) {
    if (mapping.widget !== widget.name || !mapping.feedback) continue;
    const index = outputsOf().findIndex((output) => output.name === mapping.output);
    items.push({ from: mapping.output, what: `feedback: ${mapping.message?.type}${mapping.message?.name ? ` ${mapping.message.name}` : ''}`, go: () => select({ kind: 'output', index }) });
  }
  return items;
}

function selectWidgetNamed(name) {
  const found = allWidgets().find(({ widget }) => widget.name === name);
  if (found) select(widgetSelection([found.path]));
}

function renderProperties() {
  const panel = $('properties');
  const selection = state.selection;
  if (selection?.kind === 'widget' && selection.paths.length > 1) return multiProperties(panel, selection.paths);
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
    const incoming = controlledBy(widget);
    const behaviour = (state.layout.mappings || []).filter((mapping) => mapping.widget === widget.name).length
      + (state.layout.links || []).filter((link) => link.widget === widget.name).length + incoming.length;
    fill(panel,
      el('div', { class: 'props-head' },
        el('h3', { title: widget.name }, widget.type),
        el('div', { class: 'actions' },
          el('button', { onclick: () => reorder(path, 1), title: 'Raise: draw above the next widget', 'aria-label': 'Raise' }, '▲'),
          el('button', { onclick: () => reorder(path, -1), title: 'Lower: draw below the previous widget', 'aria-label': 'Lower' }, '▼'),
          el('button', { onclick: () => duplicate(), title: 'Duplicate (Ctrl+D)' }, 'Duplicate'),
          el('button', { class: 'danger', onclick: () => removeSelection(), title: 'Delete (Del)' }, 'Delete'))),
      el('p', { class: 'doc' }, (info?.doc || '').replace(/``/g, '')),
      group('properties', 'Properties', [
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
            renameInViews(widget.name, name);
            change((layout) => {
              for (const binding of layout.bindings || []) if (binding.widget === widget.name) binding.widget = name;
              for (const mapping of layout.mappings || []) if (mapping.widget === widget.name) mapping.widget = name;
              for (const link of layout.links || []) {
                if (link.widget === widget.name) link.widget = name;
                if (link.target === widget.name) link.target = name;
              }
              widget.name = name;
            });
          },
        })),
        optionFields(widget, (info?.options || []).filter((option) => !ADVANCED.has(option.name))),
        info?.bindable ? bindingFields(widget) : null),
      optionFields(widget, (info?.options || []).filter((option) => ADVANCED.has(option.name))),
      widget.type === 'Group' ? el('div', { class: 'actions' }, el('button', { onclick: () => ungroup(path), title: 'Move its widgets out (Ctrl+Shift+G)' }, 'Ungroup')) : null,
      widget.type === 'Pages' ? [
        el('p', { class: 'hint' }, `Page ${currentPage(widget) + 1} of ${widget.widgets?.length || 0} shown. Widgets added from the palette go on it; select a widget in Layers to show its page.`),
        el('div', { class: 'actions' }, el('button', { onclick: () => addPage(path) }, 'Add page')),
      ] : isGroup(widget) ? el('p', { class: 'hint' }, 'Widgets added from the palette go inside this group.') : null,
      ]),
      widget.type === 'Sprite' ? group('frames', 'Frames', spriteEditor(widget)) : null,
      group('behaviour', 'Behaviour', [
        el('h4', {}, 'Changed by'),
        incoming.length
          ? el('ul', { class: 'controlled' }, incoming.map((item) => el('li', { onclick: item.go, title: 'Select it' },
            el('span', { class: 'from' }, item.from), el('span', { class: 'what' }, item.what))))
          : el('p', { class: 'hint' }, 'Nothing changes this widget: links of other widgets, device controls and output feedback show up here.'),
        ruleSummary([widget]),
      ], { count: behaviour || null }),
      group('animation', 'Animation', animationFields([widget]), { count: widget.animation ? widget.animation.type : null }),
    );
    return;
  }
  if (selection?.kind === 'output') return outputProperties(panel, selection.index);
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
        optionFields(device, (info?.options || []).filter((option) => !ADVANCED.has(option.name)))),
      optionFields(device, (info?.options || []).filter((option) => ADVANCED.has(option.name))),
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
    el('p', { class: 'hint' }, 'Select a widget to edit it; Shift+click or drag on empty pads to select several. Drag a device by its name. In Try mode, click pads to press them; hold for a Held event.'),
    syncFields(),
    el('h4', {}, 'Transport controls'),
    transportControls(),
  );
}

// The transport following a DAW's MIDI clock (transport.sync): a virtual port or an input port
function syncFields() {
  const transport = state.layout.transport || {};
  const sync = transport.sync || null;
  const kind = sync ? ('virtual' in sync ? 'virtual' : 'input') : 'off';
  const setSync = (value) => change((layout) => {
    const next = { ...(layout.transport || {}) };
    if (value) next.sync = value;
    else delete next.sync;
    layout.transport = next;
  });
  if (kind === 'input' && !state.ports) {
    state.ports = { inputs: [], outputs: [] };
    api('GET', '/api/ports').then((ports) => { state.ports = ports; if (!state.selection) renderProperties(); });
  }
  return el('div', { class: 'sync' },
    el('h4', {}, 'Sync to a DAW'),
    el('div', { class: 'row' },
      el('select', {
        id: 'sync-kind', 'aria-label': 'Sync',
        onchange: (e) => setSync(e.target.value === 'off' ? null
          : e.target.value === 'virtual' ? { virtual: 'PyxelWidgets Clock' } : { input: state.ports?.inputs?.[0] || 'IAC Driver Bus 1' }),
      }, [['off', 'Off: its own tempo'], ['virtual', 'Virtual port'], ['input', 'MIDI input port']].map(([value, label]) =>
        el('option', { value, selected: kind === value }, label))),
      kind === 'off' ? null : el('input', {
        id: 'sync-port', type: 'text', value: sync[kind], 'aria-label': 'Port name', list: kind === 'input' ? 'sync-ports' : null,
        title: kind === 'virtual' ? 'The name of the port the DAW sends its clock to' : 'The MIDI input the DAW\'s clock comes in through',
        onchange: (e) => { const name = e.target.value.trim(); if (name) setSync({ [kind]: name }); else render(); },
      })),
    kind === 'input' ? el('datalist', { id: 'sync-ports' }, (state.ports?.inputs || []).map((name) => el('option', { value: name }))) : null,
    kind === 'off' ? null : el('p', { id: 'sync-status', class: 'hint sync-status' }, syncStatus()),
    el('p', { class: 'hint' }, kind === 'off'
      ? 'Follow a DAW\'s MIDI clock: its tempo, play, stop and position. Sequencers and Trackers then play with the DAW.'
      : kind === 'virtual'
        ? 'In the DAW, send MIDI clock (and song position) to this port, then play from the DAW. The tempo above is used until the clock arrives.'
        : 'Route the DAW\'s MIDI clock to this input (on macOS the IAC Driver, on Windows loopMIDI), then play from the DAW.'));
}

function syncStatus() {
  const status = state.hardware.sync;
  if (!status) return '';
  if (!status.connected) return status.error || 'Not connected';
  if (!state.playing) return `Connected${state.bpm ? ` · ${state.bpm} bpm` : ''} · waiting for the DAW to play`;
  return `Following the DAW · ${state.bpm} bpm`;
}

// The Python tab's code comes from the server (pyxelwidgets.codegen): both versions for the layout as it is
const code = { key: null, data: null, timer: null };

function renderCode() {
  const drawer = drawerPrefs();
  if (!drawer.open || drawer.tab !== 'python') return;
  const file = state.file ? state.file.split(/[\\/]/).pop() : 'layout.json';
  const key = JSON.stringify([state.layout, file, !!drawer.handlers]);
  const show = () => {
    const data = code.data;
    if (!data) return;
    $('code').textContent = data.ok ? data[drawer.code === 'standalone' ? 'standalone' : 'loader'] : `# The layout has a problem, so there's no code for it:\n# ${data.error}`;
  };
  if (key === code.key) {
    show();
    return;
  }
  code.key = key;
  clearTimeout(code.timer);
  code.timer = setTimeout(async () => {
    const data = await api('POST', '/api/python', { layout: state.layout, file, handlers: !!drawer.handlers });
    if (code.key !== key) return;
    code.data = data;
    show();
  }, 150);
}

function renderToolbar() {
  $('mode-edit').classList.toggle('active', state.mode === 'edit');
  $('mode-try').classList.toggle('active', state.mode === 'try');
  document.body.classList.toggle('try', state.mode === 'try');
  $('undo').disabled = !state.history.length;
  $('redo').disabled = !state.future.length;
  $('save').title = state.file ? `Save to ${state.file} (Ctrl+S)` : 'Save: choose where to keep it (Ctrl+S)';
  const play = $('play');
  play.textContent = state.playing ? '■ Stop' : '▶ Play';
  play.classList.toggle('on', state.playing);
  // Following a DAW: it plays and stops
  play.disabled = !!state.synced;
  play.title = state.synced ? 'The DAW plays and stops it (Sync on the Surface panel)' : 'Play the transport so Sequencers and Trackers play (Space)';
  if (!state.playing) $('position').textContent = '';
  $('palette-hint').textContent = targetGroup() ? `into ${widgetAt(targetGroup()).name}` : '';
  $('device-count').textContent = state.layout.devices.length || '';
  $('output-count').textContent = outputsOf().length || '';
  const wheel = $('wheel-mode');
  wheel.textContent = prefs.wheel === 'scroll' ? 'Wheel scrolls' : 'Wheel zooms';
  wheel.title = prefs.wheel === 'scroll'
    ? 'The mouse wheel scrolls the grid; Ctrl/Cmd + wheel zooms. Click: the wheel zooms'
    : 'The mouse wheel zooms around the pointer (Shift + wheel scrolls, middle button drags). Click: the wheel scrolls';
}

function renderDirty() {
  const dirty = JSON.stringify(state.layout) !== state.saved;
  $('file').classList.toggle('dirty', dirty);
  $('file').textContent = state.file ? state.file.split(/[\\/]/).pop() : 'Unsaved layout';
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

// Adds a widget into ``group`` (a path, or null for the surface) at ``x``, ``y`` in it
function addWidget(type, group = targetGroup(), x = 0, y = 0) {
  const [maxWidth, maxHeight] = group ? [widgetAt(group).width, widgetAt(group).height] : [state.layout.surface.width, state.layout.surface.height];
  // Containers fill the space; widgets of your own (parser.register) start at 2x2
  const [width, height] = DEFAULT_SIZE[type] || (state.catalog.widgets[type]?.container ? [maxWidth, maxHeight] : [2, 2]);
  const widget = { type, name: uniqueName(type), x, y, width: Math.min(width, maxWidth - x), height: Math.min(height, maxHeight - y), options: {} };
  if (state.catalog.widgets[type].container) widget.widgets = [];
  change((layout) => {
    const list = group ? widgetAt(group).widgets : layout.widgets;
    list.push(widget);
    state.selection = widgetSelection([[...(group || []), list.length - 1]]);
  });
}

// ---------------------------------------------------------------- dragging widgets onto the grid

// Where a dragged widget would go: the pad under the pointer is its top-left; inside the
// innermost group (or shown page) it fits in, else on the surface
function dropPlace(event, type) {
  const bounds = $('overlay').getBoundingClientRect();
  const size = step();
  const { width: surfaceWidth, height: surfaceHeight } = state.layout.surface;
  const column = Math.floor((event.clientX - bounds.left) / size);
  const row = Math.floor((event.clientY - bounds.top) / size);
  if (column < 0 || row < 0 || column >= surfaceWidth || row >= surfaceHeight) return null;
  const [defaultWidth, defaultHeight] = DEFAULT_SIZE[type] || (state.catalog.widgets[type]?.container ? [surfaceWidth, surfaceHeight] : [2, 2]);
  const width = Math.min(defaultWidth, surfaceWidth), height = Math.min(defaultHeight, surfaceHeight);
  // Top-left at the pointer, moved back inside the surface
  const x = clamp(column, 0, surfaceWidth - width);
  const y = clamp(surfaceHeight - 1 - row - height + 1, 0, surfaceHeight - height);
  let group = null;
  for (const { widget, path } of allWidgets()) {
    if (!isGroup(widget) || widget.type === 'Pages' || hiddenBy(path).length || widget.options?.visible === false) continue;
    const [gx, gy] = absolute(path);
    if (x >= gx && y >= gy && x + width <= gx + widget.width && y + height <= gy + widget.height && (!group || path.length > group.length)) group = path;
  }
  const [gx, gy] = group ? absolute(group) : [0, 0];
  return { group, x: x - gx, y: y - gy, absolute: [x, y, width, height] };
}

function clearGhost() {
  $('overlay').querySelector('.ghost')?.remove();
}

function dragOver(event) {
  if (!state.dragType) return;
  const spot = dropPlace(event, state.dragType);
  if (!spot) return clearGhost();
  event.preventDefault();
  event.dataTransfer.dropEffect = 'copy';
  let ghost = $('overlay').querySelector('.ghost');
  if (!ghost) {
    ghost = el('div', { class: 'outline ghost' });
    $('overlay').append(ghost);
  }
  place(ghost, ...spot.absolute);
}

function drop(event) {
  const type = state.dragType || event.dataTransfer.getData('text/plain');
  clearGhost();
  state.dragType = null;
  if (!state.catalog.widgets[type]) return;
  const spot = dropPlace(event, type);
  if (!spot) return;
  event.preventDefault();
  if (state.mode !== 'edit') setMode('edit');
  addWidget(type, spot.group, spot.x, spot.y);
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
  if (selection.kind === 'output') return removeOutput(selection.index);
  change((layout) => {
    let bindings = layout.bindings || [];
    if (selection.kind === 'widget') {
      const widgets = topSelected().map(widgetAt);
      for (const widget of widgets) {
        const list = childrenOf(pathsOf([widget])[0]);
        list.splice(list.indexOf(widget), 1);
      }
      const names = new Set(allWidgets().map(({ widget }) => widget.name));
      bindings = bindings.filter((binding) => binding.widget === undefined || names.has(binding.widget));
      setMappings(layout, (layout.mappings || []).filter((mapping) => names.has(mapping.widget)));
      setLinks(layout, (layout.links || []).filter((link) => names.has(link.widget) && (link.target === undefined || names.has(link.target))));
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
    state.selection = widgetSelection([[...path.slice(0, -1), target]]);
  });
}

// Copies of the selected widgets, each above its original, with their messages and links;
// the copies get selected
function duplicate() {
  const originals = topSelected().map(widgetAt);
  if (!originals.length) return;
  const taken = new Set();
  const renames = new Map();
  const rename = (widget) => {
    const name = uniqueName(widget.type, taken);
    renames.set(widget.name, name);
    widget.name = name;
    taken.add(name);
    (widget.widgets || []).forEach(rename);
  };
  change((layout) => {
    const copies = originals.map((original) => {
      const copy = JSON.parse(JSON.stringify(original));
      rename(copy);
      const list = childrenOf(pathsOf([original])[0]);
      list.splice(list.indexOf(original) + 1, 0, copy);
      return copy;
    });
    copyBehaviour(layout, renames);
    state.selection = widgetSelection(pathsOf(copies));
  });
}

// Messages and links of renamed (copied) widgets, for the copies: links between copies stay between copies
function copyBehaviour(layout, renames, links = layout.links || [], mappings = layout.mappings || [], outputs = null) {
  const names = new Set(allWidgets().map(({ widget }) => widget.name));
  let dropped = 0;
  const newLinks = [];
  for (const link of links) {
    if (!renames.has(link.widget)) continue;
    const copy = { ...link, widget: renames.get(link.widget) };
    if (link.target !== undefined) {
      if (renames.has(link.target)) copy.target = renames.get(link.target);
      else if (!names.has(link.target)) {
        dropped++;
        continue;
      }
    }
    newLinks.push(copy);
  }
  const known = new Set(outputsOf(layout).map((output) => output.name));
  const newMappings = [];
  for (const mapping of mappings) {
    if (!renames.has(mapping.widget)) continue;
    if (!known.has(mapping.output)) {
      dropped++;
      continue;
    }
    newMappings.push({ ...JSON.parse(JSON.stringify(mapping)), widget: renames.get(mapping.widget) });
  }
  setLinks(layout, [...(layout.links || []), ...newLinks]);
  setMappings(layout, [...(layout.mappings || []), ...newMappings]);
  return dropped;
}

// ---------------------------------------------------------------- copy and paste

const CLIPBOARD_KEY = 'pyxelwidgets.clipboard';

// The selected widgets with their messages and links, for pasting here or in another layout
function copySelection(cut = false) {
  if (state.selection?.kind !== 'widget') return;
  const widgets = topSelected().map(widgetAt);
  const names = new Set();
  const collect = (widget) => {
    names.add(widget.name);
    (widget.widgets || []).forEach(collect);
  };
  widgets.forEach(collect);
  const clip = {
    format: 'pyxelwidgets.clipboard',
    widgets: widgets.map((widget) => ({ widget: JSON.parse(JSON.stringify(widget)), at: absolute(pathsOf([widget])[0]) })),
    links: (state.layout.links || []).filter((link) => names.has(link.widget)),
    mappings: (state.layout.mappings || []).filter((mapping) => names.has(mapping.widget)),
  };
  const text = JSON.stringify(clip);
  state.clipboard = clip;
  try {
    localStorage.setItem(CLIPBOARD_KEY, text);
  } catch {
    // This page only
  }
  navigator.clipboard?.writeText(text).catch(() => {});
  const count = `${widgets.length} widget${widgets.length > 1 ? 's' : ''}`;
  if (cut) removeSelection();
  setStatus(`${cut ? 'Cut' : 'Copied'} ${count}`, 'ok');
}

function readClipboard() {
  try {
    const stored = JSON.parse(localStorage.getItem(CLIPBOARD_KEY) || 'null');
    if (stored?.format === 'pyxelwidgets.clipboard') return stored;
  } catch {
    // Use this page's
  }
  return state.clipboard;
}

// Paste into the selected group (or next to the selected widget, or on the surface), on top,
// where they were; names stay unless taken
function pasteWidgets(clip = readClipboard(), into = targetGroup()) {
  if (!clip?.widgets?.length) return setStatus('Nothing to paste: copy widgets first (Ctrl+C)', 'error');
  const existing = new Set(allWidgets().map(({ widget }) => widget.name));
  const taken = new Set();
  const renames = new Map();
  const rename = (widget) => {
    const name = existing.has(widget.name) || taken.has(widget.name) ? uniqueName(widget.type, taken) : widget.name;
    renames.set(widget.name, name);
    widget.name = name;
    taken.add(name);
    (widget.widgets || []).forEach(rename);
  };
  let dropped = 0;
  change((layout) => {
    const container = into ? widgetAt(into) : null;
    const list = container ? (container.widgets ||= []) : layout.widgets;
    const [ox, oy] = into ? absolute(into) : [0, 0];
    const [width, height] = container ? [container.width, container.height] : [layout.surface.width, layout.surface.height];
    const pasted = clip.widgets.map(({ widget, at }) => {
      const copy = JSON.parse(JSON.stringify(widget));
      rename(copy);
      copy.width = Math.min(copy.width, width);
      copy.height = Math.min(copy.height, height);
      copy.x = clamp(at[0] - ox, 0, width - copy.width);
      copy.y = clamp(at[1] - oy, 0, height - copy.height);
      list.push(copy);
      return copy;
    });
    dropped = copyBehaviour(layout, renames, clip.links || [], clip.mappings || []);
    state.selection = widgetSelection(pathsOf(pasted));
  });
  const count = `${clip.widgets.length} widget${clip.widgets.length > 1 ? 's' : ''}`;
  setStatus(dropped ? `Pasted ${count}; ${dropped} message${dropped > 1 ? 's or links' : ' or link'} left out (their output or target isn't in this layout)` : `Pasted ${count}`, dropped ? '' : 'ok');
}

// Move the selected widgets into a new Group around them (they must share a parent)
function groupSelection() {
  const paths = topSelected();
  const parent = paths[0].slice(0, -1);
  if (!paths.every((path) => samePath(path.slice(0, -1), parent))) {
    return setStatus('Only widgets in the same group can be grouped', 'error');
  }
  if (parent.length && widgetAt(parent).type === 'Pages') return setStatus('Add a page to group widgets on a Pages', 'error');
  const widgets = paths.map(widgetAt);
  const x0 = Math.min(...widgets.map((w) => w.x || 0)), y0 = Math.min(...widgets.map((w) => w.y || 0));
  const x1 = Math.max(...widgets.map((w) => (w.x || 0) + w.width)), y1 = Math.max(...widgets.map((w) => (w.y || 0) + w.height));
  change((layout) => {
    const list = parent.length ? widgetAt(parent).widgets : layout.widgets;
    const index = Math.min(...widgets.map((widget) => list.indexOf(widget)));
    // Keep their drawing order
    const ordered = list.filter((widget) => widgets.includes(widget));
    const group = {
      type: 'Group', name: uniqueName('Group'), x: x0, y: y0, width: x1 - x0, height: y1 - y0, options: {},
      widgets: ordered.map((widget) => ({ ...widget, x: (widget.x || 0) - x0, y: (widget.y || 0) - y0 })),
    };
    const rest = list.filter((widget) => !widgets.includes(widget));
    rest.splice(index, 0, group);
    list.splice(0, list.length, ...rest);
    state.selection = widgetSelection(pathsOf([group]));
  });
}

// Move the group's widgets out to its parent, where the group was
function ungroup(path) {
  const group = widgetAt(path);
  change(() => {
    const list = childrenOf(path);
    const children = (group.widgets || []).map((widget) => ({ ...widget, x: (widget.x || 0) + (group.x || 0), y: (widget.y || 0) + (group.y || 0) }));
    list.splice(list.indexOf(group), 1, ...children);
    state.selection = widgetSelection(pathsOf(children));
  });
}

function selectAll() {
  // The selected widget's siblings, or everything on the surface
  const scope = state.selection?.kind === 'widget' ? state.selection.path.slice(0, -1) : [];
  const list = scope.length ? widgetAt(scope).widgets : state.layout.widgets;
  select(widgetSelection(list.map((_, index) => [...scope, index]).filter((path) => !hiddenBy(path).length)));
}

function nudge(dx, dy, resize) {
  const paths = topSelected();
  if (!paths.length) return;
  if (resize) {
    return change(() => paths.forEach((path) => {
      const widget = widgetAt(path);
      const [parentWidth, parentHeight] = containerSize(path);
      widget.width = clamp(widget.width + dx, 1, parentWidth - (widget.x || 0));
      widget.height = clamp(widget.height + dy, 1, parentHeight - (widget.y || 0));
    }));
  }
  // Together, as far as all of them can go
  const limits = moveLimits(paths);
  const [ox, oy] = [clamp(dx, ...limits.dx), clamp(dy, ...limits.dy)];
  if (!ox && !oy) return;
  const widgets = paths.map(widgetAt);
  change(() => widgets.forEach((widget) => Object.assign(widget, { x: (widget.x || 0) + ox, y: (widget.y || 0) + oy })));
}

// ---------------------------------------------------------------- files

function dirty() {
  return JSON.stringify(state.layout) !== state.saved;
}

function addRecent(file) {
  if (!file) return;
  prefs.recent = [file, ...(prefs.recent || []).filter((other) => other !== file)].slice(0, 8);
  savePrefs();
}

// A layout the server loaded (opened, new, saved as): it becomes the current one
function useLayout(reply) {
  state.layout = reply.layout;
  state.layout.devices = state.layout.devices || [];
  state.layout.widgets = state.layout.widgets || [];
  state.file = reply.file;
  state.saved = JSON.stringify(state.layout);
  state.history = [];
  state.future = [];
  state.selection = null;
  state.frameSize = [0, 0];
  addRecent(reply.file);
  render();
  sendHidden();
}

// A modal dialog of its own, removed once closed
function newDialog() {
  const dialog = el('dialog');
  dialog.addEventListener('close', () => dialog.remove());
  document.body.append(dialog);
  return dialog;
}

// A small dialog: resolves with the value of `fields` (by name) on OK, or null
function ask({ title, text = null, fields = [], ok = 'OK', extra = null }) {
  const dialog = newDialog();
  return new Promise((resolve) => {
    const inputs = fields.map((field) => el('input', { type: 'text', id: `ask-${field.name}`, value: field.value ?? '', placeholder: field.placeholder || '' }));
    const finish = (value) => {
      dialog.onclose = null;
      dialog.close();
      resolve(value);
    };
    fill(dialog,
      el('h3', {}, title),
      text ? el('p', { class: 'hint' }, text) : null,
      fields.length ? el('div', { class: 'fields' }, fields.map((field, i) => [
        el('label', { for: `ask-${field.name}` }, field.label), el('div', { class: 'control' }, inputs[i])])) : null,
      extra ? extra(finish) : null,
      el('div', { class: 'buttons' },
        el('button', { onclick: () => finish(null) }, 'Cancel'),
        el('button', { class: 'primary', id: 'ask-ok', onclick: () => finish(Object.fromEntries(fields.map((field, i) => [field.name, inputs[i].value.trim()]))) }, ok)));
    dialog.onclose = () => resolve(null);
    for (const input of inputs) input.addEventListener('keydown', (e) => { if (e.key === 'Enter') $('ask-ok').click(); });
    dialog.showModal();
    inputs[0]?.select();
  });
}

async function confirmDiscard() {
  if (!dirty() || (!state.file && !state.layout.widgets.length && !state.layout.devices.length)) return true;
  return !!(await ask({ title: 'Discard unsaved changes?', text: `${state.file || 'This layout'} has changes that aren't saved.`, ok: 'Discard' }));
}

async function save() {
  if (!state.file) return saveAs();
  const reply = await api('POST', '/api/save', { layout: state.layout });
  if (reply.ok) {
    state.saved = JSON.stringify(state.layout);
    renderDirty();
    setStatus(`Saved ${state.file}`, 'ok');
  } else {
    setStatus(reply.error, 'error');
  }
}

async function saveAs() {
  const suggestion = state.file || `${prefs.lastDirectory || ''}layout.json`;
  const answer = await ask({ title: 'Save as', fields: [{ name: 'path', label: 'file', value: suggestion, placeholder: 'folder/name.json' }], ok: 'Save' });
  if (!answer?.path) return;
  await flushSync();
  const reply = await api('POST', '/api/save', { layout: state.layout, path: answer.path });
  if (!reply.ok) return setStatus(reply.error, 'error');
  prefs.lastDirectory = reply.file.replace(/[^\\/]*$/, '');
  state.file = reply.file;
  state.saved = JSON.stringify(state.layout);
  addRecent(reply.file);
  render();
  setStatus(`Saved ${reply.file}`, 'ok');
}

async function openPath(path) {
  if (!(await confirmDiscard())) return;
  const reply = await api('POST', '/api/open', { path });
  if (!reply.ok) return setStatus(`Can't open ${path}: ${reply.error}`, 'error');
  useLayout(reply);
  setStatus(`Opened ${reply.file}`, 'ok');
}

async function newLayout(template = null) {
  if (!(await confirmDiscard())) return;
  const reply = await api('POST', '/api/new', { template });
  if (!reply.ok) return setStatus(reply.error, 'error');
  useLayout(reply);
  setStatus(template ? `New layout from the ${template} template: Save asks where to keep it` : 'New layout', 'ok');
}

async function templates() {
  state.templates ||= (await api('GET', '/api/templates')).templates || [];
  return state.templates;
}

async function showNew() {
  const list = await templates();
  const dialog = newDialog();
  fill(dialog,
    el('h3', {}, 'New layout'),
    el('div', { class: 'choices' },
      el('button', { onclick: () => { dialog.close(); newLayout(); } }, el('b', {}, 'Empty'), el('small', {}, 'A 9x9 grid, nothing on it')),
      list.map((template) => el('button', { dataset: { template: template.name }, onclick: () => { dialog.close(); newLayout(template.name); } },
        el('b', {}, template.title), el('small', {}, template.doc)))),
    el('div', { class: 'buttons' }, el('button', { onclick: () => dialog.close() }, 'Cancel')));
  dialog.showModal();
}

async function showOpen() {
  const recent = prefs.recent || [];
  const answer = await ask({
    title: 'Open a layout',
    fields: [{ name: 'path', label: 'file', value: state.file || '', placeholder: 'folder/name.json' }],
    ok: 'Open',
    extra: (finish) => [
      recent.length ? [el('p', { class: 'hint' }, 'Recent'), el('ul', { class: 'recent-list' }, recent.map((file) =>
        el('li', { title: file, onclick: () => finish({ path: file }) }, file)))] : null,
      el('p', { class: 'hint' }, el('button', { class: 'link', onclick: () => { finish(null); $('open-file').click(); } },
        'Or import one from this computer (Save then asks where to keep it)…')),
    ],
  });
  if (answer?.path) openPath(answer.path);
}

function download() {
  const blob = new Blob([JSON.stringify(state.layout, null, 2) + '\n'], { type: 'application/json' });
  const link = el('a', { href: URL.createObjectURL(blob), download: state.file ? state.file.split(/[\\/]/).pop() : 'layout.json' });
  link.click();
  URL.revokeObjectURL(link.href);
}

// A layout file from this computer: no path on the server, so Save asks where to keep it
async function importFile(file) {
  try {
    const layout = JSON.parse(await file.text());
    if (!(await confirmDiscard())) return;
    const reply = await api('POST', '/api/new', { layout });
    if (!reply.ok) throw new Error(reply.error);
    useLayout(reply);
    setStatus(`Imported ${file.name}: Save asks where to keep it`, 'ok');
  } catch (error) {
    setStatus(`Can't open ${file.name}: ${error.message}`, 'error');
  }
}

function showFileMenu() {
  const list = $('file-list');
  if (!list.hidden) return (list.hidden = true);
  const item = (label, action, keys = null, attrs = {}) => el('button', { role: 'menuitem', ...attrs, onclick: () => { list.hidden = true; action(); } },
    label, keys ? el('span', { class: 'keys' }, keys) : null);
  const recent = (prefs.recent || []).filter((file) => file !== state.file);
  fill(list,
    item('New…', showNew, null, { id: 'menu-new' }),
    item('Open…', showOpen, null, { id: 'menu-open' }),
    recent.length ? [el('div', { class: 'head' }, 'Recent'), recent.map((file) => item(file, () => openPath(file), null, { class: 'recent', title: file }))] : null,
    el('hr'),
    item('Save', save, 'Ctrl+S'),
    item('Save as…', saveAs, 'Ctrl+Shift+S', { id: 'menu-save-as' }),
    el('hr'),
    item('Download', download),
    item('Import from this computer…', () => $('open-file').click()));
  list.hidden = false;
  setTimeout(() => window.addEventListener('pointerdown', function close(event) {
    if (!event.target.closest('.menu-wrap')) list.hidden = true;
    window.removeEventListener('pointerdown', close);
  }), 0);
}

// ---------------------------------------------------------------- starting out

async function detectDevices() {
  const { devices } = await api('GET', '/api/detect');
  return devices || [];
}

function addDeviceOfType(type) {
  change((layout) => {
    layout.devices.push({ type, x: 0, y: 0, options: {} });
    state.selection = { kind: 'device', index: layout.devices.length - 1 };
  });
}

async function showDetect() {
  const found = await detectDevices();
  const dialog = newDialog();
  fill(dialog,
    el('h3', {}, 'Devices plugged in'),
    found.length
      ? el('div', { class: 'choices' }, found.map((device) => el('button', { onclick: () => { dialog.close(); addDeviceOfType(device.type); } },
        el('b', {}, device.model), el('small', {}, `Add it (${device.type})`))))
      : el('p', { class: 'hint' }, 'None found. Plug one in, or pick one from the list next to Add.'),
    el('div', { class: 'buttons' }, el('button', { onclick: () => dialog.close() }, 'Close')));
  dialog.showModal();
}

// An empty layout invites a template, the device you play on, or the palette
async function renderWelcome() {
  const empty = !state.layout.widgets.length && !state.layout.devices.length && state.mode === 'edit' && !state.welcomeClosed;
  let card = document.querySelector('.welcome');
  if (!empty) return card?.remove();
  if (card) return;
  card = el('div', { class: 'welcome' });
  $('stage').append(card);
  const list = await templates();
  fill(card, el('div', { class: 'card' },
    el('div', { class: 'props-head' }, el('h3', {}, 'Start a layout'),
      el('button', { class: 'link', title: 'Close', onclick: () => { state.welcomeClosed = true; card.remove(); } }, '✕')),
    el('p', { class: 'hint' }, 'From a template:'),
    el('div', { class: 'choices' }, list.map((template) => el('button', { dataset: { template: template.name }, onclick: () => newLayout(template.name) },
      el('b', {}, template.title), el('small', {}, template.doc)))),
    el('p', { class: 'hint' }, 'Or add the device you play on, then drag widgets from the palette onto the grid.'),
    el('div', { class: 'found' }, el('button', {
      id: 'welcome-detect',
      onclick: async (event) => {
        const found = await detectDevices();
        event.target.replaceWith(found.length
          ? el('div', { class: 'found' }, found.map((device) => el('button', { onclick: () => addDeviceOfType(device.type) }, `Add ${device.model}`)))
          : el('p', { class: 'hint' }, 'No device found: plug one in, or pick one under Devices.'));
      },
    }, 'Detect connected devices'))));
}



function setMode(mode) {
  state.mode = mode;
  for (const pointer of held.keys()) padUp({ pointerId: pointer });
  if (mode === 'try') openDrawer('events');
  renderToolbar();
}

// ---------------------------------------------------------------- startup

function bindToolbar() {
  $('mode-edit').onclick = () => setMode('edit');
  $('mode-try').onclick = () => setMode('try');
  const board = $('board');
  board.addEventListener('dragover', dragOver);
  board.addEventListener('drop', drop);
  board.addEventListener('dragleave', (event) => { if (!board.contains(event.relatedTarget)) clearGhost(); });
  $('play').onclick = async () => {
    if (state.synced) return;
    state.playing = !state.playing;
    renderToolbar();
    await api('POST', '/api/play', { playing: state.playing });
  };
  $('tree').addEventListener('dragover', treeDragOver);
  $('tree').addEventListener('drop', treeDrop);
  $('zoom-in').onclick = () => setZoom((zooming.target ?? state.zoom) * 1.25);
  $('zoom-out').onclick = () => setZoom((zooming.target ?? state.zoom) / 1.25);
  $('zoom-fit').onclick = () => setZoom(1);
  $('wheel-mode').onclick = () => {
    prefs.wheel = prefs.wheel === 'scroll' ? 'zoom' : 'scroll';
    savePrefs();
    renderToolbar();
  };
  bindStage();
  $('undo').onclick = undo;
  $('redo').onclick = redo;
  $('save').onclick = save;
  $('file-menu').onclick = showFileMenu;
  $('detect-devices').onclick = showDetect;
  $('open-file').onchange = (e) => { if (e.target.files[0]) importFile(e.target.files[0]); e.target.value = ''; };
  $('add-device').onclick = addDevice;
  $('add-output').onclick = addOutput;
  $('toggle-left').onclick = () => togglePanel('left');
  $('toggle-right').onclick = () => togglePanel('right');
  $('help').onclick = showShortcuts;
  $('problems').onclick = () => openDrawer('problems');
  $('layer-search').addEventListener('input', renderTree);
  bindFolds();
  bindDrawer();
  bindSplitters();
  window.addEventListener('beforeunload', (event) => {
    if (state.file && JSON.stringify(state.layout) !== state.saved) event.preventDefault();
  });
  window.addEventListener('keydown', (event) => {
    if (event.target.closest('input, select, textarea')) return;
    if (event.target.closest('dialog')) return;
    if (state.rules.open && state.rules.focused && rulesKey(event)) return;
    const mod = event.ctrlKey || event.metaKey;
    const key = event.key.toLowerCase();
    if (mod && key === 'z') { event.preventDefault(); return event.shiftKey ? redo() : undo(); }
    if (mod && key === 'y') { event.preventDefault(); return redo(); }
    if (mod && (key === '=' || key === '+')) { event.preventDefault(); return setZoom((zooming.target ?? state.zoom) * 1.25); }
    if (mod && key === '-') { event.preventDefault(); return setZoom((zooming.target ?? state.zoom) / 1.25); }
    if (mod && key === '0') { event.preventDefault(); return setZoom(1); }
    if (mod && key === 's') { event.preventDefault(); return event.shiftKey ? saveAs() : save(); }
    if (mod && key === 'o') { event.preventDefault(); return showOpen(); }
    if (mod && key === 'd' && state.selection?.kind === 'widget') { event.preventDefault(); return duplicate(); }
    if (mod && key === 'c' && state.selection?.kind === 'widget' && !window.getSelection()?.toString()) { event.preventDefault(); return copySelection(); }
    if (mod && key === 'x' && state.selection?.kind === 'widget' && state.mode === 'edit') { event.preventDefault(); return copySelection(true); }
    if (mod && key === 'v' && state.mode === 'edit') { event.preventDefault(); return pasteWidgets(); }
    if (mod && key === 'a' && state.mode === 'edit') { event.preventDefault(); return selectAll(); }
    if (mod && key === 'g' && state.selection?.kind === 'widget') {
      event.preventDefault();
      const widget = widgetAt(state.selection.path);
      return event.shiftKey ? (widget.type === 'Group' && ungroup(state.selection.path)) : groupSelection();
    }
    if (mod) return;
    if (key === '?' ) return showShortcuts();
    if (key === '[') return togglePanel('left');
    if (key === ']') return togglePanel('right');
    if (key === 'f') return toggleFocus();
    if (key === '`') { drawerPrefs().open = !drawerPrefs().open; savePrefs(); return renderDrawer(); }
    if (key === 'm') return state.rules.open ? closeRules() : openRules();
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

// The grid fills the stage (refitted when panels, the drawer or the window change size), the
// wheel zooms around the pointer (or moves the grid, by the toolbar's choice; Ctrl/Cmd + wheel
// and pinches always zoom), Shift + wheel and the middle button move it
function bindStage() {
  const stage = $('stage');
  new ResizeObserver(() => renderBoard()).observe(stage);
  stage.addEventListener('wheel', (event) => {
    const pinch = event.ctrlKey || event.metaKey;
    event.preventDefault();
    const scale = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? stage.clientHeight : 1;
    if (!pinch && (prefs.wheel === 'scroll' || event.shiftKey)) {
      // Shift + wheel: sideways
      const [dx, dy] = event.shiftKey && !event.deltaX ? [event.deltaY, 0] : [event.deltaX, event.deltaY];
      return panBy(-dx * scale, -dy * scale);
    }
    const pixels = event.deltaY * scale;
    // Pinches send small steps, wheels about 100 a notch
    setZoom((zooming.target ?? state.zoom) * Math.exp(-pixels * (event.ctrlKey && Math.abs(pixels) < 50 ? 0.01 : 0.002)), event);
  }, { passive: false });
  stage.addEventListener('pointerdown', (event) => {
    if (event.button === 1) return panStage(event);
    if (event.target.id === 'stage' || event.target.id === 'board') startMarquee(event);
  });
  // No autoscroll circle on middle clicks
  stage.addEventListener('mousedown', (event) => { if (event.button === 1) event.preventDefault(); });
}

function panStage(event) {
  event.preventDefault();
  const stage = $('stage');
  let last = { x: event.clientX, y: event.clientY };
  stage.classList.add('panning');
  const move = (e) => {
    panBy(e.clientX - last.x, e.clientY - last.y);
    last = { x: e.clientX, y: e.clientY };
  };
  const up = () => {
    window.removeEventListener('pointermove', move);
    window.removeEventListener('pointerup', up);
    stage.classList.remove('panning');
  };
  window.addEventListener('pointermove', move);
  window.addEventListener('pointerup', up);
}

// A widget drawn small (rows from the top of colors, null where transparent), or null
function thumb(preview) {
  if (!preview) return null;
  const rows = preview.length;
  const columns = preview[0].length;
  const cell = Math.max(3, Math.floor((30 - (Math.max(rows, columns) - 1)) / Math.max(rows, columns)));
  return el('span', { class: 'thumb', style: `grid-template-columns: repeat(${columns}, ${cell}px); grid-auto-rows: ${cell}px` },
    preview.flat().map((color) => el('i', { style: `background: ${color || '#0c0d10'}` })));
}

function buildCatalog() {
  $('palette').replaceChildren(...Object.entries(state.catalog.widgets).map(([type, info]) =>
    el('button', {
      title: `${(info.doc || type).replace(/``/g, '')}\nClick to add, or drag onto the grid.`, onclick: () => addWidget(type), dataset: { type },
      draggable: 'true',
      ondragstart: (event) => {
        state.dragType = type;
        document.body.classList.add('dragging');
        event.dataTransfer.setData('text/plain', type);
        event.dataTransfer.effectAllowed = 'copy';
      },
      ondragend: () => { state.dragType = null; document.body.classList.remove('dragging'); clearGhost(); },
    },
      thumb(info.preview) || el('span', { class: 'glyph' }, type === 'ButtonGroup' ? 'BG' : type.slice(0, 2)),
      el('span', { class: 'label' }, type))));
  const groups = {};
  for (const device of state.catalog.devices) (groups[device.vendor || 'Other'] ||= []).push(device);
  $('device-type').replaceChildren(...Object.entries(groups).map(([vendor, devices]) =>
    el('optgroup', { label: vendor }, devices.map((device) => el('option', { value: device.type }, device.model)))));
  $('output-type').replaceChildren(...state.catalog.outputs.map((output) => el('option', { value: output.type }, output.model)));
}

// Sections of the left panel fold away; remembered in this browser
function bindFolds() {
  prefs.folds ||= {};
  for (const section of document.querySelectorAll('.fold')) {
    const name = section.dataset.fold;
    section.classList.toggle('collapsed', !!prefs.folds[name]);
    section.querySelector('.fold-head').addEventListener('click', (event) => {
      if (event.target.closest('button, input, select')) return;
      prefs.folds[name] = !prefs.folds[name];
      section.classList.toggle('collapsed', prefs.folds[name]);
      savePrefs();
    });
  }
}

async function start() {
  const [catalog, current] = await Promise.all([api('GET', '/api/catalog'), api('GET', '/api/layout')]);
  state.catalog = catalog;
  state.layout = current.layout;
  state.layout.devices = state.layout.devices || [];
  state.layout.widgets = state.layout.widgets || [];
  state.file = current.file;
  state.saved = JSON.stringify(state.layout);
  addRecent(state.file);
  buildCatalog();
  renderPanels();
  bindToolbar();
  buildRules();
  render();
  sendHidden();
  poll();
}

start();
