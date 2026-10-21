// The device list and the properties panel: option editors, animation, the toolbar

import { state, $, fill, el, api, appWindow } from './core.js';
import { renderPlayHere } from './screen.js';
import { prefs, savePrefs } from './prefs.js';
import { widgetAt, containerSize, allWidgets, deviceInfo, bindingFields, transportControls, deviceSize,
  isGroup, currentPage, addPage, widgetSelection, deviceControls, controlSelect, controlOwners, ruleLabel, selectOwner } from './model.js';
import { outputsOf, outputInfo, renderOutputs, outputProperties } from './mappings.js';
import { describeValue, linkOptions } from './links.js';
import { ruleSummary, pickedControl } from './rules.js';
import { learnButton } from './learn.js';
import { drawerPrefs } from './drawer.js';
import { change, flushSync, setStatus } from './history.js';
import { openCheck } from './check.js';
import { render } from './board.js';
import { renameWidget } from './layers.js';
import { spriteEditor } from './sprite.js';
import { targetGroup, removeSelection, reorder, duplicate, groupSelection, ungroup } from './editing.js';

export function renderDevices() {
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

export function hardwareDot(index, list = 'devices') {
  const status = state.hardware[list]?.[index];
  if (!status) return el('span', { class: 'dot', title: 'Connecting…' });
  if (!status.connected && !status.error) return el('span', { class: 'dot idle', title: 'Not connected' });
  return el('span', {
    class: `dot ${status.connected ? 'on' : 'off'}`,
    title: status.connected ? (list === 'devices' ? 'Connected: mirrors the preview, pads work the widgets' : 'Connected: sends and receives messages') : status.error,
  });
}

// Connects or disconnects a layout device or output (an on-screen device can't be)
export function connectButton(kind, index) {
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
  if (state.selection?.kind === 'device') renderProperties();
  const status = state.hardware[kind][index];
  if (connected && !status?.connected) setStatus(`Couldn't connect: ${status?.error}`, 'error');
}

export function select(selection) {
  state.selection = selection;
  render();
}

export function setOption(target, name, value) {
  target.options = target.options || {};
  if (value === undefined) delete target.options[name];
  else target.options[name] = value;
}

// A labelled editor for one option from the catalog schema. `prefix` keeps element ids
// apart; `apply(value)` replaces setting the option on `target` (e.g. on several widgets).
export function optionField(target, option, prefix = 'option', apply = null) {
  if (option.kind === 'frames') return [];
  const options = target.options || {};
  const set = option.name in options;
  const value = set ? options[option.name] : option.default;
  const commit = (newValue) => change(() => (apply ? apply(newValue) : setOption(target, option.name, newValue)));
  const id = `${prefix}-${option.name}`;
  // Widget options can be formulas (text options take {formulas} in the text itself)
  const formulas = !!state.catalog.widgets[target.type] && !['json', 'point', 'str'].includes(option.kind);
  const computed = formulas && isFormula(value);
  const [control, suggestions] = computed ? formulaControl(value, commit, id) : optionControl(option, value, commit, id);
  return [
    // What the option is for (from the constructor's docstring) shows on hover
    el('label', { for: id, class: [set ? 'changed' : '', option.doc ? 'documented' : ''].join(' ').trim(), title: option.doc ? `${option.name}: ${option.doc}` : option.name },
      option.name.replace(/_/g, ' ')),
    el('div', { class: 'control' }, control, suggestions,
      formulas ? el('button', {
        class: `link formula${computed ? ' on' : ''}`, id: `${id}-formula`,
        title: computed ? 'Back to a constant' : 'Compute it from other widgets\' options: a formula such as {roll.steps - roll.width}',
        onclick: () => commit(computed ? undefined : `{${formulaSeed(option.kind, value)}}`),
      }, 'ƒ') : null,
      el('button', { class: 'link reset', title: `Reset to ${JSON.stringify(option.default)}`, onclick: () => commit(undefined) }, 'reset')),
  ];
}

// Text holding one {formula}
export function isFormula(value) {
  return typeof value === 'string' && /^\s*\{[^{}]*\}\s*$/.test(value);
}

// A formula giving what a constant field has now: {8}, {true}, {'Page'}
export function formulaSeed(kind, value) {
  if (value == null || value === '') return kind === 'bool' ? 'false' : '0';
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return `'${String(value).replace(/'/g, "\\'")}'`;
}

export const FORMULA_HELP = 'A formula in braces: other widgets\' options (roll.steps - roll.width), self (this widget), '
  + 'transport (bpm, playing, bar…), numbers, + - * / // %, comparisons, and/or/not, a if test else b, and min, max, round, clamp…';

// A text input for a {formula}, suggesting names it can use: event values (``sources``), widgets' options, the transport
export function formulaControl(value, commit, id, sources = []) {
  const input = el('input', {
    type: 'text', class: 'formula', id, value: value ?? '', list: `${id}-names`, spellcheck: false, title: FORMULA_HELP,
    onchange: (e) => {
      const text = e.target.value.trim();
      commit(text === '' ? undefined : (isFormula(text) ? text : `{${text.replace(/^\{|\}$/g, '')}}`));
    },
  });
  return [input, el('datalist', { id: `${id}-names` }, formulaNames(sources).map((name) => el('option', { value: `{${name}}` })))];
}

const FORMULA_WORDS = new Set(['and', 'or', 'not', 'if', 'else', 'true', 'false', 'True', 'False', 'none', 'None', 'pi', 'self', 'transport']);

// The event values a formula uses: names that aren't widgets (before a dot), functions or words
export function formulaSources(text) {
  const widgets = new Set(allWidgets().map(({ widget }) => widget.name));
  const bare = text.replace(/'[^']*'|"[^"]*"/g, ' ');
  const found = [];
  for (const match of bare.matchAll(/(^|[^.\w])([A-Za-z_]\w*)(?=\s*([.(]?))/g)) {
    const [, , name, next] = match;
    if (next || FORMULA_WORDS.has(name) || widgets.has(name)) continue;
    found.push(name);
  }
  return found;
}

function formulaNames(sources) {
  const names = [...sources];
  for (const { widget } of allWidgets()) {
    if (!/^[A-Za-z_]\w*$/.test(widget.name)) continue;
    const info = state.catalog.widgets[widget.type];
    for (const option of linkOptions(widget)) names.push(`${widget.name}.${option.name}`);
    for (const property of info?.properties || []) names.push(`${widget.name}.${property}`);
  }
  for (const name of state.catalog.expression?.transport || []) names.push(`transport.${name}`);
  return names;
}

// The input for one option kind (and a datalist of suggestions for rates), with element id `id`
export function optionControl(option, value, commit, id) {
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
// Options people rarely set by hand, under "More options": starting states that playing and links change
// (values, steps, view positions), feel tweaks with good defaults, and input details
export const ADVANCED = new Set(['visible', 'propagation', 'interactive', 'held_time', 'double_press_time',
  'plugin_button', 'channel_button', 'next_page', 'previous_page',
  'value', 'selected', 'step', 'bar', 'column', 'running', 'velocity_curve', 'fixed_velocity', 'velocity_random',
  'gate_random', 'current_active_color', 'blink_rate', 'resolution', 'slew', 'hold', 'falloff', 'repeat', 'rest',
  'taps', 'timeout', 'reseed', 'density', 'max_notes', 'send', 'save']);

// The same for one widget type only: elsewhere these are main options (Pages' page, a Stepper's range)
const ADVANCED_BY_TYPE = {
  Sequencer: new Set(['page', 'row']), PianoRoll: new Set(['page']), Tracker: new Set(['page']),
  TapTempo: new Set(['minimum', 'maximum']), Pages: new Set(['background']),
};

export function isAdvanced(target, name) {
  return ADVANCED.has(name) || !!ADVANCED_BY_TYPE[target?.type]?.has(name);
}

// A collapsible group of the properties panel; open or closed is remembered in this browser
export function group(key, title, children, { count = null, open = true } = {}) {
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
export function optionFields(target, options, prefix = 'option') {
  const main = options.filter((option) => !isAdvanced(target, option.name));
  const more = options.filter((option) => isAdvanced(target, option.name));
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
    items.push({ from: ruleLabel(link), what: value ? `${what} = ${value}` : what, go: () => selectOwner(link) });
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

export function selectWidgetNamed(name) {
  const found = allWidgets().find(({ widget }) => widget.name === name);
  if (found) select(widgetSelection([found.path]));
}

export function renderProperties() {
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
          onchange: (e) => renameWidget(widget, e.target.value),
        })),
        optionFields(widget, (info?.options || []).filter((option) => !isAdvanced(widget, option.name))),
        info?.bindable ? bindingFields(widget) : null),
      optionFields(widget, (info?.options || []).filter((option) => isAdvanced(widget, option.name))),
      widget.type === 'Group' ? el('div', { class: 'actions' }, el('button', { onclick: () => ungroup(path), title: 'Move its widgets out (Ctrl+Shift+G)' }, 'Ungroup')) : null,
      widget.type === 'Pages' ? [
        el('p', { class: 'hint' }, `Page ${currentPage(widget) + 1} of ${widget.widgets?.length || 0} shown. Widgets added from the palette go on it; select a widget in Layers to show its page.`),
        el('div', { class: 'actions' }, el('button', { onclick: () => addPage(path) }, 'Add page')),
      ] : isGroup(widget) ? el('p', { class: 'hint' }, 'Widgets added from the palette go inside this group.') : null,
      widget.type === 'Presets' ? presetsFields(widget) : null,
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
      el('label', { for: `device-${key}-pick` }, label),
      portPicker(`device-${key}`, device[key], `${key}s`, 'Find by name',
        (name) => change(() => { if (name) device[key] = name; else delete device[key]; })),
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
        optionFields(device, (info?.options || []).filter((option) => !isAdvanced(device, option.name)))),
      optionFields(device, (info?.options || []).filter((option) => isAdvanced(device, option.name))),
      deviceRules(selection.index),
      el('div', { class: 'actions' },
        device.type.startsWith('virtual.') || device.type.startsWith('web.') ? null : el('button', {
          id: 'device-check', disabled: !state.hardware.devices[selection.index]?.connected,
          title: state.hardware.devices[selection.index]?.connected ? 'Test patterns and questions, then a report for the developers' : 'Connect the device to check it',
          onclick: () => openCheck(selection.index),
        }, 'Check this device…'),
        el('button', { class: 'danger', onclick: () => removeSelection() }, 'Remove device')),
      el('p', { class: 'hint' }, 'Only the Launchpad Mini MK3 is tested on hardware by the author: checking yours helps make it right.'),
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
    clockFields(),
    el('h4', {}, 'Transport and surface controls'),
    transportControls(),
  );
}

// Messages and links starting from the device's controls: the control new ones start from, and every one there is
function deviceRules(index) {
  const device = state.layout.devices[index];
  const controls = deviceControls(device);
  if (!controls.length) return null;
  const owners = controlOwners(index);
  const picked = pickedControl();
  const pick = (control) => {
    state.deviceControls[index] = control;
    render();
  };
  const count = [...(state.layout.mappings || []), ...(state.layout.links || [])].filter((object) => object.widget === undefined && object.device === index).length;
  return group('controls', 'Messages and links', [
    el('p', { class: 'hint' }, `Controls: ${controls.map((c) => c.name).join(', ')}`),
    el('div', { class: 'fields' },
      el('label', { for: 'device-control', title: 'The control new messages and links start from' }, 'control'),
      el('div', { class: 'control learnable' },
        controlSelect('device-control', picked ? { device: index, control: picked.control } : null, (_, control) => pick(control), false, index),
        learnButton('device-control', 'control', (event) => {
          // Another device's control: show that one
          if (event._device !== index) state.selection = { kind: 'device', index: event._device };
          state.deviceControls[event._device] = event.control;
          render();
        }))),
    ruleSummary(owners, picked ? [picked] : []).slice(1),
  ], { count: count || null });
}

// What a Presets group stored (kept in the layout while its save option is on), and a way to forget it
function presetsFields(widget) {
  const slots = Object.keys(widget.options?.presets || {}).length;
  const save = widget.options?.save ?? true;
  return [
    el('p', { class: 'hint', id: 'presets-stored' }, slots
      ? `${slots} stored preset${slots === 1 ? '' : 's'} kept in the layout.`
      : save ? 'Presets stored in Try mode (or on a device) are kept in the layout.' : 'Stored presets are not kept in the layout (save is off).'),
    slots ? el('div', { class: 'actions' }, el('button', {
      id: 'presets-clear',
      onclick: () => change(() => {
        const { presets, ...options } = widget.options;
        widget.options = options;
      }),
    }, 'Clear stored presets')) : null,
  ];
}

// The MIDI ports Scan found (GET /api/ports), {inputs, outputs}; scanned once when a port picker first shows
function scanPorts(announce = true) {
  state.ports = { inputs: state.ports?.inputs || [], outputs: state.ports?.outputs || [], scanning: true };
  return api('GET', '/api/ports').then((ports) => {
    state.ports = ports;
    if (announce) setStatus(`Found ${ports.inputs.length} MIDI input${ports.inputs.length === 1 ? '' : 's'} and ${ports.outputs.length} output${ports.outputs.length === 1 ? '' : 's'}`, 'ok');
    renderProperties();
  }, () => { state.ports.scanning = false; renderProperties(); });
}

const CUSTOM_PORT = '\u0000custom';

// A MIDI port field: the ports found by Scan, `empty` (none chosen; null leaves it out) and Custom… (a typed name,
// element id `id`, also shown for a name that isn't among the found ports). `direction` is 'inputs' or 'outputs';
// `set` gets the name, or null for none
export function portPicker(id, value, direction, empty, set) {
  if (!state.ports) scanPorts(false);
  // Not the virtual ports this layout makes itself
  const own = new Set([...(state.layout.outputs || []).map((output) => output.virtual), state.layout.transport?.sync?.virtual]);
  const found = (state.ports[direction] || []).filter((name) => !own.has(name));
  const custom = state.customPorts.has(id) || (!!value && !found.includes(value)) || (!value && empty === null);
  return el('div', { class: 'control port' },
    el('select', {
      id: `${id}-pick`, 'aria-label': `${direction === 'inputs' ? 'Input' : 'Output'} port`,
      onchange: (e) => {
        if (e.target.value === CUSTOM_PORT) {
          state.customPorts.add(id);
          renderProperties();
          $(id)?.focus();
          return;
        }
        state.customPorts.delete(id);
        set(e.target.value || null);
      },
    },
    empty === null ? null : el('option', { value: '', selected: !value && !custom }, empty),
    found.map((name) => el('option', { value: name, selected: !custom && name === value }, name)),
    el('option', { value: CUSTOM_PORT, selected: custom }, 'Custom…')),
    el('button', {
      type: 'button', id: `${id}-scan`, disabled: !!state.ports.scanning,
      title: 'Look again for the MIDI ports on this computer', onclick: () => scanPorts(),
    }, state.ports.scanning ? 'Scanning…' : 'Scan'),
    custom ? el('input', {
      type: 'text', id, value: value || '', placeholder: 'port name',
      onchange: (e) => set(e.target.value.trim() || null),
    }) : null);
}

// The transport following a DAW's MIDI clock (transport.sync): a virtual port, an input port or an output the DAW connects to
function syncFields() {
  const transport = state.layout.transport || {};
  const sync = transport.sync || null;
  const kind = sync ? ['virtual', 'output'].find((key) => key in sync) || 'input' : 'off';
  // Outputs a clock can come in through (Bluetooth and network MIDI, MIDI ports)
  const clocked = outputsOf().filter((output) => outputInfo(output)?.clock).map((output) => output.name);
  const setSync = (value) => change((layout) => {
    const next = { ...(layout.transport || {}) };
    if (value) next.sync = value;
    else delete next.sync;
    layout.transport = next;
  });
  return el('div', { class: 'sync' },
    el('h4', {}, 'Sync to a DAW'),
    el('div', { class: 'row' },
      el('select', {
        id: 'sync-kind', 'aria-label': 'Sync',
        onchange: (e) => setSync(e.target.value === 'off' ? null
          : e.target.value === 'virtual' ? { virtual: 'PyxelWidgets Clock' }
          : e.target.value === 'output' ? { output: clocked[0] } : { input: state.ports?.inputs?.[0] || 'IAC Driver Bus 1' }),
      }, [['off', 'Off: its own tempo'], ['virtual', 'Virtual port'], ['input', 'MIDI input port'], ['output', 'An output (Bluetooth, network MIDI)']]
        .filter(([value]) => value !== 'output' || clocked.length || kind === 'output')
        .map(([value, label]) => el('option', { value, selected: kind === value }, label))),
      kind !== 'output' ? null : el('select', {
        id: 'sync-output', 'aria-label': 'Output',
        onchange: (e) => setSync({ output: e.target.value }),
      }, [...new Set([...clocked, sync.output])].map((name) => el('option', { value: name, selected: name === sync.output }, name))),
      kind !== 'virtual' ? null : el('input', {
        id: 'sync-port', type: 'text', value: sync[kind], 'aria-label': 'Port name',
        title: 'The name of the port the DAW sends its clock to',
        onchange: (e) => { const name = e.target.value.trim(); if (name) setSync({ [kind]: name }); else render(); },
      })),
    kind === 'input' ? portPicker('sync-port', sync.input, 'inputs', null, (name) => { if (name) setSync({ input: name }); else render(); }) : null,
    kind === 'off' ? null : el('p', { id: 'sync-status', class: 'hint sync-status' }, syncStatus()),
    el('p', { class: 'hint' }, kind === 'off'
      ? 'Follow a DAW\'s MIDI clock: its tempo, play, stop and position. Sequencers and Trackers then play with the DAW.'
      : kind === 'virtual'
        ? 'In the DAW, send MIDI clock (and song position) to this port, then play from the DAW. The tempo above is used until the clock arrives.'
        : kind === 'output'
          ? 'In the DAW, send MIDI clock (and song position) to this output\'s port (the Bluetooth or network MIDI device it connected to), then play from the DAW.'
          : 'Route the DAW\'s MIDI clock to this input (on macOS the IAC Driver, on Windows loopMIDI), then play from the DAW.'));
}

// The transport's MIDI clock sent out through outputs (transport.clock), so a DAW or drum machine follows
function clockFields() {
  const clock = state.layout.transport?.clock || [];
  // Outputs sending MIDI: MIDI ports, Mackie/HUI, Bluetooth and network MIDI
  const midi = outputsOf().filter((output) => outputInfo(output)?.midi || outputInfo(output)?.clock).map((output) => output.name);
  const set = (name, on) => change((layout) => {
    const next = { ...(layout.transport || {}) };
    const names = (next.clock || []).filter((each) => each !== name);
    if (on) names.push(name);
    if (names.length) next.clock = names;
    else delete next.clock;
    layout.transport = next;
  });
  return el('div', { class: 'sync clock-out' },
    el('h4', {}, 'Send MIDI clock'),
    midi.length ? midi.map((name) => el('label', { class: 'check' },
      el('input', { type: 'checkbox', id: `clock-${name}`, checked: clock.includes(name), onchange: (e) => set(name, e.target.checked) }), ` ${name}`))
      : el('p', { class: 'hint' }, 'Add a MIDI output to send the clock through.'),
    el('p', { class: 'hint' }, 'While playing, the transport\'s tempo, play, stop and position go out as MIDI clock: set the DAW (or a drum machine) to follow it.'));
}

export function syncStatus() {
  const status = state.hardware.sync;
  if (!status) return '';
  if (!status.connected) return status.error || 'Not connected';
  if (!state.playing) return `Connected${state.bpm ? ` · ${state.bpm} bpm` : ''} · waiting for the DAW to play`;
  return `Following the DAW · ${state.bpm} bpm`;
}

// The Python tab's code comes from the server (pyxelwidgets.codegen): both versions for the layout as it is
export const code = { key: null, data: null, timer: null };

export function renderCode() {
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

export function renderToolbar() {
  renderPlayHere();
  $('mode-edit').classList.toggle('active', state.mode === 'edit');
  $('mode-try').classList.toggle('active', state.mode === 'try');
  $('mode-perform').classList.toggle('active', state.mode === 'perform');
  document.body.classList.toggle('try', state.mode === 'try');
  document.body.classList.toggle('perform', state.mode === 'perform');
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
    ? 'The mouse wheel scrolls the grid; Ctrl/Cmd + wheel and pinches zoom. Click: the wheel zooms'
    : 'The mouse wheel zooms around the pointer (Shift + wheel, two-finger scrolls and dragging around the grid move it). Click: the wheel scrolls';
}

export function renderDirty() {
  const dirty = JSON.stringify(state.layout) !== state.saved;
  $('file').classList.toggle('dirty', dirty);
  $('file').textContent = state.file ? state.file.split(/[\\/]/).pop() : 'Unsaved layout';
  $('file').title = state.file || '';
  document.title = `${dirty ? '• ' : ''}PyxelWidgets Designer`;
  // The window's title, and whether closing it asks first
  if (appWindow() && (dirty !== state.windowDirty || state.file !== state.windowFile)) {
    state.windowDirty = dirty;
    state.windowFile = state.file;
    appWindow().changed(dirty, state.file || null);
  }
}
